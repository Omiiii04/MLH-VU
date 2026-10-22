"""test_llm_compile.py -- model-assisted compilation tests (all mocked, no network)."""
from __future__ import annotations

import json
import pytest

from skillvm.ir import CompileStatus
from skillvm.llm_compile import compile_with_llm
from skillvm.providers import FakeProvider, ProviderError, ProviderManager


SIMPLE_SKILL = """\
---
id: llm-test
inputs:
  - name: p
    type: string
permissions: [fs.read, verify.run]
postconditions:
  - kind: file_exists
    path: "{p}"
---
# LLM test
## Steps
1. Read `p` with fs.read
"""

VALID_IR_JSON = json.dumps({
    "skill_id": "llm-test",
    "inputs": [{"name": "p", "type": "string", "required": True}],
    "outputs": [],
    "nodes": [
        {"id": "in_p", "type": "input", "name": "p", "value_type": "string", "depends_on": []},
        {"id": "step_1", "type": "tool", "tool": "fs.read",
         "args": {"path": {"$bind": "in_p"}}, "effect": "read",
         "idempotent": True, "permissions": ["fs.read"], "depends_on": ["in_p"]},
        {"id": "verify_0", "type": "verify", "check": "file_exists",
         "args": {"path": "{p}"}, "required": True, "depends_on": ["step_1"]},
    ],
    "edges": [
        {"src": "in_p", "dst": "step_1"},
        {"src": "step_1", "dst": "verify_0"},
    ],
    "permissions": ["fs.read", "verify.run"],
    "fallback_steps": 0,
    "total_steps": 1,
})


def _mgr(*providers):
    return ProviderManager(providers=list(providers), settings=None)


def test_valid_llm_output_compiles():
    p = FakeProvider(responses=[VALID_IR_JSON])
    result = compile_with_llm(SIMPLE_SKILL, _mgr(p))
    assert result.status == CompileStatus.COMPILED
    assert result.ir is not None
    assert result.ir.skill_id == "llm-test"


def test_malformed_ir_triggers_repair_then_valid():
    """First response is garbage JSON, second (repair) is valid."""
    p = FakeProvider(responses=["not json at all!!!", VALID_IR_JSON])
    result = compile_with_llm(SIMPLE_SKILL, _mgr(p))
    assert result.status == CompileStatus.COMPILED
    assert len(p.calls) == 2  # initial + one repair


def test_malformed_ir_both_attempts_falls_back_to_deterministic():
    """Both LLM attempts produce bad JSON — falls back to deterministic compiler."""
    p = FakeProvider(responses=["bad", "still bad"])
    result = compile_with_llm(SIMPLE_SKILL, _mgr(p), fallback_to_deterministic=True)
    # Deterministic compiler should succeed for this skill
    assert result.status in (CompileStatus.COMPILED, CompileStatus.NEEDS_REVIEW)
    assert any(d.code == "SV9002" for d in result.diagnostics)


def test_provider_failure_falls_back_to_deterministic():
    p = FakeProvider(failures=[ProviderError("timeout")])
    result = compile_with_llm(SIMPLE_SKILL, _mgr(p), fallback_to_deterministic=True)
    assert result.status in (CompileStatus.COMPILED, CompileStatus.NEEDS_REVIEW)
    assert any(d.code == "SV9001" for d in result.diagnostics)


def test_provider_failure_no_fallback_rejects():
    p = FakeProvider(failures=[ProviderError("timeout")])
    result = compile_with_llm(SIMPLE_SKILL, _mgr(p), fallback_to_deterministic=False)
    assert result.status == CompileStatus.REJECTED


def test_llm_ir_passes_same_validator_as_deterministic():
    """A valid-looking IR with a cycle must still be rejected."""
    cyclic_ir = json.dumps({
        "skill_id": "llm-test",
        "inputs": [], "outputs": [],
        "nodes": [
            {"id": "a", "type": "tool", "tool": "fs.read", "args": {"path": "x"},
             "effect": "read", "idempotent": True, "permissions": ["fs.read"], "depends_on": ["b"]},
            {"id": "b", "type": "tool", "tool": "fs.read", "args": {"path": "y"},
             "effect": "read", "idempotent": True, "permissions": ["fs.read"], "depends_on": ["a"]},
        ],
        "edges": [{"src": "a", "dst": "b"}, {"src": "b", "dst": "a"}],
        "permissions": ["fs.read"],
        "fallback_steps": 0, "total_steps": 2,
    })
    p = FakeProvider(responses=[cyclic_ir])
    result = compile_with_llm(SIMPLE_SKILL, _mgr(p), fallback_to_deterministic=False)
    assert result.status == CompileStatus.REJECTED
    assert any(d.code == "SV2004" for d in result.diagnostics)
