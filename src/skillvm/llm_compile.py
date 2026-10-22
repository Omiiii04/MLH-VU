"""llm_compile.py -- model-assisted compilation.

Takes a SKILL.md, sends it to an LLM provider, gets back IR JSON,
validates it through the same _validate_ir + _check_postconditions path.
One bounded repair attempt if the output is schema-invalid.

Constrained output strategy:
  - Gemini/OpenRouter: JSON schema mode (response_mime_type=application/json)
  - LM Studio (no JSON mode): schema-prompt in user turn + Pydantic repair attempt.

The provider that produced the IR is recorded in ir.provider, ir.model, ir.constrained_mode.
"""
from __future__ import annotations

import json
import re
from typing import Any

from skillvm import COMPILER_VERSION, IR_SCHEMA_VERSION, PROMPT_VERSION
from skillvm.compiler import _validate_ir, _check_postconditions, compile_skill
from skillvm.diag import CompileStatus, Diagnostic, Severity, d
from skillvm.ir import (
    CompileResult, Edge, EffectType, InputNode, ToolNode, TransformNode,
    TypedField, VerifyNode, WorkflowIR,
)
from skillvm.parse import parse_skill
from skillvm.providers import BaseProvider, FakeProvider, ProviderError, ProviderManager
from skillvm.redact import excerpt


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_SYSTEM = """\
You are a workflow compiler. Given a SKILL.md, produce a WorkflowIR JSON object.
Rules:
- node type must be one of: input, tool, transform, llm, condition, approval, verify, output
- tool must be one of: fs.read, fs.list, fs.write, json.parse, data.transform, verify.run
- effect must be one of: read, reversible_write, irreversible, external
- every llm node must have output_schema (non-empty dict) and verify_node (id of a verify node)
- no loops in depends_on
- return ONLY valid JSON, no commentary
"""

_NODE_SCHEMA_HINT = """
Schema:
{
  "skill_id": "string",
  "inputs": [{"name": "string", "type": "string"}],
  "outputs": [],
  "nodes": [
    // InputNode: {"id":"string","type":"input","name":"string","value_type":"string","depends_on":[]}
    // ToolNode:  {"id":"string","type":"tool","tool":"fs.read","args":{},"effect":"read","idempotent":true,"permissions":[],"depends_on":[]}
    // VerifyNode:{"id":"string","type":"verify","check":"file_exists","args":{},"required":true,"depends_on":[]}
    // ApprovalNode:{"id":"string","type":"approval","reason":"string","effect":"irreversible","depends_on":[]}
  ],
  "edges": [{"src":"string","dst":"string"}],
  "permissions": ["fs.read"],
  "fallback_steps": 0,
  "total_steps": 0
}
"""


def _build_prompt(source: str) -> tuple[str, str]:
    """Return (system, user) for the compile request."""
    user = f"{_NODE_SCHEMA_HINT}\n\nCompile this SKILL.md to WorkflowIR JSON:\n\n{source}"
    return _SYSTEM, user


# ---------------------------------------------------------------------------
# IR JSON → WorkflowIR (with repair)
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> str:
    """Pull first JSON object from text (handles markdown code fences)."""
    # Strip markdown fences
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    # Find first { ... }
    start = text.find("{")
    if start == -1:
        return text
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{": depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i+1]
    return text[start:]


def _parse_ir(text: str, source: str, provider: str, model: str, constrained_mode: str) -> WorkflowIR | None:
    raw = _extract_json(text)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    # Inject required metadata
    parsed = parse_skill(source)
    data.setdefault("content_hash", parsed.content_hash)
    data.setdefault("schema_version", IR_SCHEMA_VERSION)
    data.setdefault("compiler_version", COMPILER_VERSION)
    data["provider"] = provider
    data["model"] = model
    data["prompt_version"] = PROMPT_VERSION
    data["constrained_mode"] = constrained_mode
    try:
        return WorkflowIR.model_validate(data)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def compile_with_llm(
    source: str,
    manager: ProviderManager,
    *,
    fallback_to_deterministic: bool = True,
) -> CompileResult:
    """Compile via LLM; fall back to deterministic compiler if provider fails."""
    parsed = parse_skill(source)
    diags: list[Diagnostic] = list(parsed.diagnostics)

    if any(dd.severity == Severity.error for dd in diags):
        return CompileResult(status=CompileStatus.REJECTED, diagnostics=diags)

    system, user = _build_prompt(source)

    # Try with JSON schema hint first
    try:
        result = manager.generate(system=system, user=user, response_schema={"type": "object"})
    except ProviderError as e:
        if fallback_to_deterministic:
            det = compile_skill(source)
            det.diagnostics.insert(0, d("SV9001", f"LLM provider failed ({e}); used deterministic compiler", severity=Severity.warning))
            return det
        return CompileResult(status=CompileStatus.REJECTED, diagnostics=[d("SV9001", f"Provider failed: {e}")])

    # Determine constrained mode from provider result
    constrained_mode = "json_schema" if result.provider != "lmstudio" else "schema_prompt"

    ir = _parse_ir(result.text, source, result.provider, result.model, constrained_mode)

    # One repair attempt if parse failed
    if ir is None:
        repair_prompt = f"The previous response was not valid JSON. Return ONLY a JSON object matching this schema:\n{_NODE_SCHEMA_HINT}\n\nOriginal skill:\n{source}\n\nYour previous response (invalid):\n{excerpt(result.text, 300)}"
        try:
            result2 = manager.generate(system=system, user=repair_prompt)
            ir = _parse_ir(result2.text, source, result2.provider, result2.model, "schema_prompt_repaired")
        except ProviderError:
            ir = None

    if ir is None:
        if fallback_to_deterministic:
            det = compile_skill(source)
            det.diagnostics.insert(0, d("SV9002", "LLM output invalid after repair; used deterministic compiler", severity=Severity.warning))
            return det
        return CompileResult(status=CompileStatus.REJECTED, diagnostics=[d("SV9002", "LLM produced invalid IR after repair attempt")])

    # Run IDENTICAL validation pipeline as deterministic path
    meta = parsed.meta
    _check_postconditions(meta, diags)
    if any(dd.code == "SV3003" for dd in diags):
        return CompileResult(status=CompileStatus.REJECTED, diagnostics=diags)

    ir_diags = _validate_ir(ir)
    diags.extend(ir_diags)

    if any(dd.code == "SV2004" for dd in diags):
        return CompileResult(status=CompileStatus.REJECTED, diagnostics=diags)
    if any(dd.code in ("SV2006", "SV2007") for dd in diags):
        return CompileResult(status=CompileStatus.REJECTED, diagnostics=diags)
    if any(dd.code.startswith("SV2") for dd in diags):
        return CompileResult(status=CompileStatus.REJECTED, diagnostics=diags)
    if any(dd.code == "SV3001" for dd in diags):
        return CompileResult(status=CompileStatus.NEEDS_REVIEW, ir=None, diagnostics=diags,
                             fallback_steps=ir.fallback_steps, total_steps=ir.total_steps, executable=False)

    return CompileResult(
        status=CompileStatus.COMPILED, ir=ir, diagnostics=diags,
        fallback_steps=ir.fallback_steps, total_steps=ir.total_steps, executable=True,
    )
