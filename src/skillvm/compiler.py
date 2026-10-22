"""compiler.py -- deterministic SKILL.md -> WorkflowIR compiler."""
from __future__ import annotations

import re
from typing import Any

from skillvm.diag import (
    POSTCONDITION_KINDS, VACUOUS_KINDS, CompileStatus, Diagnostic, Severity, d,
)
from skillvm.ir import (
    ApprovalNode, CompileResult, ConditionNode, Edge, EffectType,
    InputNode, LlmNode, NodeType, OutputNode, ToolNode, TransformNode,
    TypedField, VerifyNode, WorkflowIR,
)
from skillvm.parse import ParsedSkill, parse_skill
from skillvm.registry import TOOLS

_AMBIGUOUS = re.compile(
    r"\b(maybe|somehow|or\s+(write|read|do)|thing|stuff|something|unclear|unspecified)\b", re.I
)
_SUBJECTIVE = re.compile(
    r"\b(good\s+summary|nice\s+output|properly|appropriately|correct(ly)?)\b", re.I
)
_TOOL_HINTS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bfs\.read\b|\bread\b.*\bfs\b|\bfs\b.*\bread\b", re.I), "fs.read"),
    (re.compile(r"\bfs\.list\b|\blist\b.*\bfs\b|\bfs\b.*\blist\b", re.I), "fs.list"),
    (re.compile(r"\bfs\.write\b|\bwrite\b.*\bfs\b|\bfs\b.*\bwrite\b", re.I), "fs.write"),
    (re.compile(r"\bjson\.parse\b|\bparse\b.*\bjson\b|\bjson\b.*\bparse\b", re.I), "json.parse"),
    (re.compile(r"\bdata\.transform\b|\btransform\b", re.I), "data.transform"),
    (re.compile(r"\bverify\.run\b|\bverify\b|\bcheck\b.*result", re.I), "verify.run"),
    (re.compile(r"\bread\b.*`[^`]+`", re.I), "fs.read"),
    (re.compile(r"\bwrite\b.*`[^`]+`", re.I), "fs.write"),
]
_PATH_HINT = re.compile(r"`([^`]+)`")


def _infer_tool(step_text: str) -> str | None:
    for pat, name in _TOOL_HINTS:
        if pat.search(step_text):
            return name
    return None


def _path_from_step(step_text: str) -> str:
    m = _PATH_HINT.search(step_text)
    return m.group(1) if m else "path"


def _has_cycle(nodes: list, edges: list[Edge]) -> bool:
    adj: dict[str, list[str]] = {n.id: [] for n in nodes}
    for e in edges:
        adj.setdefault(e.src, []).append(e.dst)
    visited: set[str] = set()
    in_stack: set[str] = set()

    def dfs(v: str) -> bool:
        visited.add(v); in_stack.add(v)
        for w in adj.get(v, []):
            if w not in visited:
                if dfs(w): return True
            elif w in in_stack:
                return True
        in_stack.discard(v)
        return False

    return any(dfs(s) for s in list(adj) if s not in visited)


def _validate_ir(ir: WorkflowIR) -> list[Diagnostic]:
    diags: list[Diagnostic] = []
    nmap = ir.node_map()
    valid_types = {t.value for t in NodeType}
    for n in ir.nodes:
        if n.type not in valid_types:
            diags.append(d("SV1005", f"Unsupported node type '{n.type}'"))
        if n.type == "tool" and n.tool not in TOOLS:
            diags.append(d("SV2001", f"Unknown tool '{n.tool}' in node '{n.id}'"))
        if n.type == "llm":
            if not getattr(n, "output_schema", None):
                diags.append(d("SV2006", f"LLM node '{n.id}' missing output_schema"))
            vn = getattr(n, "verify_node", "")
            if not vn:
                diags.append(d("SV2007", f"LLM node '{n.id}' missing verify_node"))
            elif vn not in nmap:
                diags.append(d("SV2007", f"LLM node '{n.id}' verify_node '{vn}' not found"))
            elif nmap[vn].type != "verify":
                diags.append(d("SV2007", f"LLM node '{n.id}' verify_node must point to a verify node"))

    # Build input type map: ir.inputs (from meta) takes priority over node default
    input_types: dict[str, str] = {n.name: n.value_type for n in ir.nodes if n.type == "input"}
    for f in ir.inputs:
        input_types[f.name] = f.type  # override with declared type (may differ from node default "string")
    # Also map by node-id for $bind resolution
    input_id_types: dict[str, str] = {}
    for n in ir.nodes:
        if n.type == "input":
            declared = input_types.get(n.name, n.value_type)
            input_id_types[n.id] = declared

    for n in ir.nodes:
        if n.type == "tool":
            spec = TOOLS.get(n.tool)
            if spec:
                for arg_name, arg_val in n.args.items():
                    if isinstance(arg_val, dict) and "$bind" in arg_val:
                        src_node = arg_val["$bind"]
                        if src_node and src_node in nmap and nmap[src_node].type == "input":
                            src_type = input_id_types.get(src_node, "string")
                            expected = spec.arg_types.get(arg_name, "any")
                            if expected != "any" and src_type != expected:
                                diags.append(d("SV2002", f"Type mismatch: '{arg_name}' expects {expected}, got {src_type}"))
        for dep in n.depends_on:
            if dep not in {x.id for x in ir.nodes}:
                diags.append(d("SV2003", f"Node '{n.id}' depends_on unknown '{dep}'"))

    if _has_cycle(ir.nodes, ir.edges):
        diags.append(d("SV2004", "Dependency graph contains a cycle"))
    return diags


def _check_postconditions(meta: dict, diags: list[Diagnostic]) -> None:
    for pc in meta.get("postconditions", []):
        if not isinstance(pc, dict):
            diags.append(d("SV3002", "Postcondition must be a mapping")); continue
        kind = pc.get("kind", "")
        if kind in VACUOUS_KINDS:
            diags.append(d("SV3003", f"Vacuous postcondition '{kind}'"))
        elif kind not in POSTCONDITION_KINDS:
            diags.append(d("SV3002", f"Unknown postcondition kind '{kind}'"))


def _build_nodes(parsed: ParsedSkill, meta: dict, diags: list[Diagnostic]) -> tuple[list, list[Edge], int, int]:
    nodes: list = []
    edges: list[Edge] = []
    perms: list[str] = meta.get("permissions", [])
    effect_overrides: dict[str, str] = meta.get("effect_overrides", {}) or {}
    fallback = 0; total = 0

    input_node_ids: dict[str, str] = {}
    for inp in meta.get("inputs", []):
        name = inp.get("name", f"in_{len(nodes)}")
        nid = f"in_{name}"
        nodes.append(InputNode(id=nid, name=name, value_type=inp.get("type", "string")))
        input_node_ids[name] = nid

    prev_id: str | None = nodes[-1].id if nodes else None

    # Inline nodes from frontmatter
    if "nodes" in meta:
        raw_nodes = meta["nodes"]
        if isinstance(raw_nodes, list):
            for rn in raw_nodes:
                if not isinstance(rn, dict): continue
                ntype = rn.get("type", ""); nid = rn.get("id", f"node_{len(nodes)}")
                deps = rn.get("depends_on", [])
                if ntype == "input":
                    nodes.append(InputNode(id=nid, name=rn.get("name", nid), value_type=rn.get("value_type", "string"), depends_on=deps))
                elif ntype == "tool":
                    spec = TOOLS.get(rn.get("tool", ""))
                    eff = EffectType(effect_overrides.get(rn.get("tool",""), spec.effect.value if spec else "read"))
                    nodes.append(ToolNode(id=nid, tool=rn.get("tool",""), args=rn.get("args",{}), effect=eff, idempotent=rn.get("idempotent",False), permissions=list(spec.permissions) if spec else [], depends_on=deps))
                    total += 1
                elif ntype == "llm":
                    nodes.append(LlmNode(id=nid, prompt=rn.get("prompt",""), output_schema=rn.get("output_schema",{}), verify_node=rn.get("verify_node",""), depends_on=deps))
                elif ntype == "verify":
                    nodes.append(VerifyNode(id=nid, check=rn.get("check","file_exists"), args=rn.get("args",{}), depends_on=deps))
                elif ntype == "approval":
                    nodes.append(ApprovalNode(id=nid, reason=rn.get("reason","Approval required"), effect=EffectType(rn.get("effect","irreversible")), depends_on=deps))
                elif ntype == "condition":
                    nodes.append(ConditionNode(id=nid, predicate=rn.get("predicate","truthy"), depends_on=deps))
                elif ntype == "output":
                    nodes.append(OutputNode(id=nid, name=rn.get("name",nid), from_node=rn.get("from_node",""), depends_on=deps))
                elif ntype == "transform":
                    nodes.append(TransformNode(id=nid, op=rn.get("op","identity"), args=rn.get("args",{}), depends_on=deps))
        for n in nodes:
            for dep in n.depends_on:
                edges.append(Edge(src=dep, dst=n.id))
        return nodes, edges, fallback, total

    # Steps -> nodes
    for num, line_no, step_text in parsed.steps:
        total += 1
        if _AMBIGUOUS.search(step_text):
            diags.append(d("SV3001", f"Step {num} is ambiguous: '{step_text[:80]}'", severity=Severity.warning, line_start=line_no))
        if _SUBJECTIVE.search(step_text):
            nid = f"fallback_{num}"
            nodes.append(TransformNode(id=nid, op="passthrough_unverified", args={"description": step_text}, fallback=True, depends_on=[prev_id] if prev_id else []))
            if prev_id: edges.append(Edge(src=prev_id, dst=nid))
            prev_id = nid; fallback += 1; continue
        tool_name = _infer_tool(step_text)
        if not tool_name:
            nid = f"fallback_{num}"
            nodes.append(TransformNode(id=nid, op="passthrough_unverified", args={"description": step_text}, fallback=True, depends_on=[prev_id] if prev_id else []))
            if prev_id: edges.append(Edge(src=prev_id, dst=nid))
            prev_id = nid; fallback += 1; continue
        spec = TOOLS[tool_name]
        effect = EffectType(effect_overrides.get(tool_name, spec.effect.value))
        path = _path_from_step(step_text)
        args: dict[str, Any] = {}
        matched_input: str | None = None
        for inp_name, inp_id in input_node_ids.items():
            if f"`{inp_name}`" in step_text or inp_name == path:
                matched_input = inp_id; break
        if tool_name in ("fs.read", "fs.list", "fs.write"):
            args["path"] = {"$bind": matched_input} if matched_input else path
            if tool_name == "fs.write":
                args["content"] = {"$bind": prev_id} if prev_id else ""
        elif tool_name == "json.parse":
            args["text"] = {"$bind": prev_id} if prev_id else ""
        elif tool_name == "data.transform":
            args["op"] = "identity"; args["value"] = {"$bind": prev_id} if prev_id else ""
        elif tool_name == "verify.run":
            args["check"] = "file_exists"
        deps = [prev_id] if prev_id else []
        nid = f"step_{num}"
        if effect in (EffectType.irreversible, EffectType.external):
            appr_id = f"approve_{num}"
            nodes.append(ApprovalNode(id=appr_id, reason=f"Step {num} irreversible: {step_text[:60]}", effect=effect, depends_on=deps))
            if prev_id: edges.append(Edge(src=prev_id, dst=appr_id))
            edges.append(Edge(src=appr_id, dst=nid))
            nodes.append(ToolNode(id=nid, tool=tool_name, args=args, effect=effect, idempotent=spec.idempotent, permissions=list(spec.permissions), depends_on=[appr_id]))
        else:
            if prev_id: edges.append(Edge(src=prev_id, dst=nid))
            nodes.append(ToolNode(id=nid, tool=tool_name, args=args, effect=effect, idempotent=spec.idempotent, permissions=list(spec.permissions), depends_on=deps))
        prev_id = nid

    for i, pc in enumerate(meta.get("postconditions", [])):
        if not isinstance(pc, dict): continue
        kind = pc.get("kind", "")
        if kind in VACUOUS_KINDS or kind not in POSTCONDITION_KINDS: continue
        vargs = {k: v for k, v in pc.items() if k != "kind"}
        vid = f"verify_{i}"
        nodes.append(VerifyNode(id=vid, check=kind, args=vargs, depends_on=[prev_id] if prev_id else []))
        if prev_id: edges.append(Edge(src=prev_id, dst=vid))
        prev_id = vid

    return nodes, edges, fallback, total


def compile_skill(source: str) -> CompileResult:
    parsed = parse_skill(source)
    diags: list[Diagnostic] = list(parsed.diagnostics)

    if any(dd.severity == Severity.error for dd in diags):
        return CompileResult(status=CompileStatus.REJECTED, diagnostics=diags)

    meta = parsed.meta
    sid = str(meta.get("id", "")).strip()
    if not sid:
        return CompileResult(status=CompileStatus.REJECTED, diagnostics=diags)

    _check_postconditions(meta, diags)
    if any(dd.code == "SV3003" for dd in diags):
        return CompileResult(status=CompileStatus.REJECTED, diagnostics=diags)

    for rn in (meta.get("nodes") or []):
        if isinstance(rn, dict):
            ntype = rn.get("type", "")
            if ntype and ntype not in {t.value for t in NodeType}:
                diags.append(d("SV1005", f"Unsupported node type '{ntype}'"))
    if any(dd.code == "SV1005" for dd in diags):
        return CompileResult(status=CompileStatus.REJECTED, diagnostics=diags)

    nodes, edges, fallback_count, total_count = _build_nodes(parsed, meta, diags)

    ir = WorkflowIR(
        skill_id=sid,
        content_hash=parsed.content_hash,
        inputs=[TypedField(name=i["name"], type=i.get("type","string")) for i in meta.get("inputs",[]) if isinstance(i, dict) and "name" in i],
        nodes=nodes, edges=edges,
        permissions=meta.get("permissions", []),
        fallback_steps=fallback_count,
        total_steps=total_count or len([n for n in nodes if n.type in ("tool","transform")]),
    )

    ir_diags = _validate_ir(ir)
    diags.extend(ir_diags)

    if any(dd.code == "SV2004" for dd in diags):
        return CompileResult(status=CompileStatus.REJECTED, diagnostics=diags)
    if any(dd.code in ("SV2006","SV2007") for dd in diags):
        return CompileResult(status=CompileStatus.REJECTED, diagnostics=diags)
    if any(dd.code.startswith("SV2") for dd in diags):
        return CompileResult(status=CompileStatus.REJECTED, diagnostics=diags)

    if any(dd.code == "SV3001" for dd in diags):
        return CompileResult(status=CompileStatus.NEEDS_REVIEW, ir=None, diagnostics=diags, fallback_steps=fallback_count, total_steps=ir.total_steps, executable=False)

    return CompileResult(status=CompileStatus.COMPILED, ir=ir, diagnostics=diags, fallback_steps=fallback_count, total_steps=ir.total_steps, executable=True)
