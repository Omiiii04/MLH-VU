"""runtime.py -- dependency-aware workflow executor.

Executes validated IR only. States: PENDING->READY->RUNNING->SUCCEEDED/FAILED/etc.
A run is VERIFIED_SUCCESS only if every required verify node was actually executed
and SUCCEEDED. A run with no required verify nodes (or no verify nodes at all)
yields SUCCEEDED_UNVERIFIED, never VERIFIED_SUCCESS.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from skillvm.ir import WorkflowIR, EffectType
from skillvm.tools import Sandbox, SandboxError, PermissionError_, execute_tool


class NodeState(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"
    BLOCKED = "BLOCKED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"


class RunState(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    VERIFIED_SUCCESS = "VERIFIED_SUCCESS"
    # At least one required verify node was NOT executed (e.g. no verify nodes, or
    # workflow completed via a path that skipped all verify nodes).
    SUCCEEDED_UNVERIFIED = "SUCCEEDED_UNVERIFIED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    NEEDS_APPROVAL = "NEEDS_APPROVAL"


# Allowed transitions: current_state -> set of valid next states
_ALLOWED: dict[NodeState, set[NodeState]] = {
    NodeState.PENDING: {NodeState.READY, NodeState.RUNNING, NodeState.SKIPPED, NodeState.CANCELLED, NodeState.AWAITING_APPROVAL},
    NodeState.READY: {NodeState.RUNNING, NodeState.CANCELLED},
    NodeState.RUNNING: {NodeState.SUCCEEDED, NodeState.FAILED, NodeState.BLOCKED, NodeState.AWAITING_APPROVAL, NodeState.CANCELLED},
    NodeState.SUCCEEDED: set(),   # terminal
    NodeState.FAILED: set(),      # terminal
    NodeState.SKIPPED: set(),     # terminal
    NodeState.CANCELLED: set(),   # terminal
    NodeState.BLOCKED: set(),     # terminal (blocked by permission)
    NodeState.AWAITING_APPROVAL: {NodeState.RUNNING, NodeState.CANCELLED},
}


@dataclass
class NodeRecord:
    node_id: str
    state: NodeState = NodeState.PENDING
    result: Any = None
    error: str | None = None
    started_at: float | None = None
    finished_at: float | None = None
    retries: int = 0
    approval_token: str | None = None

    def transition(self, new_state: NodeState) -> None:
        allowed = _ALLOWED.get(self.state, set())
        if new_state not in allowed:
            raise RuntimeError(f"Illegal transition {self.state} -> {new_state} for node '{self.node_id}'")
        self.state = new_state


@dataclass
class RunRecord:
    run_id: str
    skill_id: str
    state: RunState = RunState.PENDING
    node_records: dict[str, NodeRecord] = field(default_factory=dict)
    failed_evidence: list[dict] = field(default_factory=list)
    started_at: float | None = None
    finished_at: float | None = None
    idempotency_key: str | None = None


# Global run registry — prevents duplicate runs with same idempotency key
_RUN_REGISTRY: dict[str, str] = {}  # idempotency_key -> run_id


class DuplicateRunError(Exception):
    pass


def execute_ir(
    ir: WorkflowIR,
    inputs: dict[str, Any],
    workspace: Path,
    granted_permissions: list[str] | None = None,
    idempotency_key: str | None = None,
    pending_approvals: dict[str, str] | None = None,
    _fault_nodes: dict[str, Exception] | None = None,  # for testing: inject failures
) -> RunRecord:
    """Execute a compiled IR. Returns RunRecord with final state."""

    if idempotency_key:
        if idempotency_key in _RUN_REGISTRY:
            raise DuplicateRunError(f"Run with key '{idempotency_key}' already exists: {_RUN_REGISTRY[idempotency_key]}")
        _RUN_REGISTRY[idempotency_key] = (run_id := str(uuid.uuid4()))
    else:
        run_id = str(uuid.uuid4())

    perms = granted_permissions if granted_permissions is not None else list(ir.permissions)
    approvals = pending_approvals or {}
    faults = _fault_nodes or {}

    run = RunRecord(run_id=run_id, skill_id=ir.skill_id, state=RunState.RUNNING)
    run.started_at = time.monotonic()
    for n in ir.nodes:
        run.node_records[n.id] = NodeRecord(node_id=n.id)

    sandbox = Sandbox(workspace=workspace, authorized_root=workspace)

    # Snapshot before execution so reversible failures can be rolled back.
    _snapshot_taken = False
    _snapshot_restored = False
    _snapshot_restore_failed = False
    try:
        sandbox.snapshot()
        _snapshot_taken = True
    except Exception:
        pass  # snapshot is best-effort; non-fatal

    # Build adjacency: node -> list of dependents; and reverse: node -> dependencies
    nmap = ir.node_map()
    deps_of: dict[str, list[str]] = {n.id: list(n.depends_on) for n in ir.nodes}
    # Topological order (Kahn)
    in_degree: dict[str, int] = {n.id: len(n.depends_on) for n in ir.nodes}
    ready_queue: list[str] = [nid for nid, deg in in_degree.items() if deg == 0]
    topo_order: list[str] = []
    temp_in = dict(in_degree)
    adj: dict[str, list[str]] = {n.id: [] for n in ir.nodes}
    for n in ir.nodes:
        for dep in n.depends_on:
            adj.setdefault(dep, []).append(n.id)
    q = [nid for nid, d in temp_in.items() if d == 0]
    while q:
        v = q.pop(0)
        topo_order.append(v)
        for w in adj.get(v, []):
            temp_in[w] -= 1
            if temp_in[w] == 0:
                q.append(w)

    # Node results store
    results: dict[str, Any] = {}
    # Seed inputs
    for n in ir.nodes:
        if n.type == "input":
            val = inputs.get(n.name)
            results[n.id] = val

    verify_failures: list[dict] = []

    for nid in topo_order:
        n = nmap[nid]
        rec = run.node_records[nid]

        # Check if any required dep failed/was skipped
        dep_ok = all(
            run.node_records[dep].state in (NodeState.SUCCEEDED,)
            or nmap[dep].type == "input"
            for dep in n.depends_on
        )
        if not dep_ok:
            rec.transition(NodeState.SKIPPED)
            continue

        if n.type == "input":
            rec.transition(NodeState.READY)
            rec.transition(NodeState.RUNNING)
            rec.result = results.get(nid)
            rec.transition(NodeState.SUCCEEDED)
            continue

        if n.type == "approval":
            token = approvals.get(nid)
            valid_token = f"approved:{nid}"
            if token != valid_token:
                # No valid approval token — block
                rec.transition(NodeState.AWAITING_APPROVAL)
                run.state = RunState.NEEDS_APPROVAL
                run.finished_at = time.monotonic()
                return run
            rec.transition(NodeState.READY)
            rec.transition(NodeState.RUNNING)
            rec.result = {"approved": True, "token": token}
            rec.transition(NodeState.SUCCEEDED)
            results[nid] = rec.result
            continue

        if n.type == "verify":
            rec.transition(NodeState.READY)
            rec.transition(NodeState.RUNNING)
            rec.started_at = time.monotonic()
            check = n.check
            # Resolve args: substitute {input_name} templates and $bind refs
            vargs = {k: _resolve_template(v, inputs) for k, v in n.args.items()}
            # Inject fault?
            if nid in faults:
                rec.error = str(faults[nid])
                rec.transition(NodeState.FAILED)
                verify_failures.append({"node": nid, "error": rec.error})
                if n.required:
                    break
                continue
            try:
                vresult = execute_tool("verify.run", {"check": check, **vargs}, perms, sandbox)
                rec.result = vresult
                rec.finished_at = time.monotonic()
                if vresult.get("passed"):
                    rec.transition(NodeState.SUCCEEDED)
                    results[nid] = vresult
                else:
                    rec.transition(NodeState.FAILED)
                    verify_failures.append({"node": nid, "evidence": vresult.get("evidence", {})})
                    if n.required:
                        break
            except Exception as e:
                rec.error = str(e)
                rec.transition(NodeState.FAILED)
                verify_failures.append({"node": nid, "error": str(e)})
                if n.required:
                    break
            continue

        if n.type in ("transform",):
            rec.transition(NodeState.READY)
            rec.transition(NodeState.RUNNING)
            # Resolve $bind args
            resolved_args = _resolve_args(n.args, results, nmap)
            if nid in faults:
                rec.error = str(faults[nid])
                rec.transition(NodeState.FAILED)
                break
            try:
                result = execute_tool("data.transform", resolved_args, perms, sandbox)
                rec.result = result
                rec.transition(NodeState.SUCCEEDED)
                results[nid] = result
            except Exception as e:
                rec.error = str(e)
                rec.transition(NodeState.FAILED)
                break
            continue

        if n.type == "tool":
            rec.transition(NodeState.READY)
            rec.transition(NodeState.RUNNING)
            rec.started_at = time.monotonic()
            resolved_args = _resolve_args(n.args, results, nmap)
            # Inject fault?
            if nid in faults:
                rec.error = str(faults[nid])
                rec.transition(NodeState.FAILED)
                break
            # Retry only for read or idempotent
            max_retries = 1 if (n.effect == EffectType.read or n.idempotent) else 0
            last_err: Exception | None = None
            for attempt in range(max_retries + 1):
                try:
                    result = execute_tool(n.tool, resolved_args, perms, sandbox)
                    rec.result = result
                    rec.retries = attempt
                    rec.finished_at = time.monotonic()
                    rec.transition(NodeState.SUCCEEDED)
                    results[nid] = result
                    last_err = None
                    break
                except PermissionError_ as e:
                    rec.error = str(e)
                    rec.transition(NodeState.BLOCKED)
                    last_err = e
                    break
                except Exception as e:
                    last_err = e
                    if attempt == max_retries:
                        rec.error = str(e)
                        rec.transition(NodeState.FAILED)
            if last_err is not None:
                break
            continue

        # Other node types (llm, condition, output) — mark succeeded with pass-through
        rec.transition(NodeState.READY)
        rec.transition(NodeState.RUNNING)
        rec.result = results.get(list(n.depends_on)[0]) if n.depends_on else None
        rec.transition(NodeState.SUCCEEDED)
        results[nid] = rec.result

    run.finished_at = time.monotonic()

    if verify_failures:
        run.state = RunState.FAILED
        run.failed_evidence = verify_failures
        # Attempt rollback of reversible filesystem changes.
        if _snapshot_taken:
            try:
                sandbox.restore()
                _snapshot_restored = True
                run.failed_evidence.append({"snapshot": "restored"})
            except Exception as e:
                _snapshot_restore_failed = True
                run.failed_evidence.append({"snapshot": "restore_failed", "error": str(e)})
    elif any(r.state in (NodeState.FAILED, NodeState.BLOCKED) for r in run.node_records.values()):
        run.state = RunState.FAILED
        failed = [r for r in run.node_records.values() if r.state in (NodeState.FAILED, NodeState.BLOCKED)]
        run.failed_evidence = [{"node": r.node_id, "error": r.error} for r in failed]
        if _snapshot_taken:
            try:
                sandbox.restore()
                _snapshot_restored = True
                run.failed_evidence.append({"snapshot": "restored"})
            except Exception as e:
                _snapshot_restore_failed = True
                run.failed_evidence.append({"snapshot": "restore_failed", "error": str(e)})
    else:
        # Invariant: VERIFIED_SUCCESS requires >=1 required verify node to have
        # actually executed and reached SUCCEEDED.
        required_verify_nodes = [n for n in ir.nodes if n.type == "verify" and getattr(n, "required", True)]
        executed_required_successes = [
            nid for nid in (n.id for n in required_verify_nodes)
            if run.node_records.get(nid) and run.node_records[nid].state == NodeState.SUCCEEDED
        ]
        if required_verify_nodes and len(executed_required_successes) == len(required_verify_nodes):
            run.state = RunState.VERIFIED_SUCCESS
        else:
            # No required verify nodes executed successfully (or none exist).
            run.state = RunState.SUCCEEDED_UNVERIFIED

    if _snapshot_taken:
        try:
            sandbox.cleanup_snapshot()
        except Exception:
            pass

    return run


def _resolve_args(args: dict[str, Any], results: dict[str, Any], nmap: dict) -> dict[str, Any]:
    """Resolve $bind references in args."""
    out = {}
    for k, v in args.items():
        if isinstance(v, dict) and "$bind" in v:
            src = v["$bind"]
            bound = results.get(src)
            # If the result is a tool result dict, extract content
            if isinstance(bound, dict) and "content" in bound:
                out[k] = bound["content"]
            elif isinstance(bound, dict) and "value" in bound:
                out[k] = bound["value"]
            else:
                out[k] = bound
        else:
            out[k] = v
    return out


def _resolve_template(value, inputs):
    """Substitute {input_name} templates in string values using inputs."""
    if isinstance(value, str):
        try:
            return value.format(**inputs)
        except (KeyError, ValueError):
            return value
    return value
