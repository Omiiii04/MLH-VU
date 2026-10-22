"""test_runtime.py -- runtime tests (mocked, no network)."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from skillvm.compiler import compile_skill
from skillvm.runtime import (
    DuplicateRunError, NodeState, RunState, _RUN_REGISTRY, execute_ir,
)


COPY_JSON_SKILL = """\
---
id: copy-json
inputs:
  - name: source_path
    type: string
  - name: dest_path
    type: string
permissions: [fs.read, fs.write, json.parse, verify.run]
postconditions:
  - kind: file_exists
    path: "{dest_path}"
---

# Copy JSON
## Steps
1. Read `source_path` with fs.read
2. Parse the file with json.parse
3. Write the object to `dest_path` with fs.write
"""

# A skill with NO verify nodes at all.
NO_VERIFY_SKILL = """\
---
id: no-verify
inputs:
  - name: p
    type: string
permissions: [fs.write]
---
# no-verify
## Steps
1. Write hello to `p` with fs.write
"""

# Inline-node skill with explicit verify node (required=True).
EXPLICIT_VERIFY_SKILL = """\
---
id: explicit-verify
inputs:
  - name: dest_path
    type: string
permissions: [fs.write, verify.run]
nodes:
  - id: in_dest_path
    type: input
    name: dest_path
    value_type: string
  - id: write_step
    type: tool
    tool: fs.write
    args:
      path: {$bind: in_dest_path}
      content: "hello"
    effect: reversible_write
    depends_on: [in_dest_path]
  - id: verify_step
    type: verify
    check: file_exists
    args:
      path: {$bind: in_dest_path}
    required: true
    depends_on: [write_step]
---
# explicit-verify
"""


@pytest.fixture()
def workspace(tmp_path: Path):
    ws = tmp_path / "ws"
    ws.mkdir()
    src = ws / "input.json"
    src.write_text('{"ok": true}', encoding="utf-8")
    return ws


def _compile(src: str):
    r = compile_skill(src)
    assert r.ir is not None, f"compile failed: {[d.message for d in r.diagnostics]}"
    return r.ir


# ---------------------------------------------------------------------------
# Invariant: VERIFIED_SUCCESS requires executed verify nodes
# ---------------------------------------------------------------------------

def test_success_run(workspace: Path):
    """Full run with passing verify node -> VERIFIED_SUCCESS."""
    ir = _compile(COPY_JSON_SKILL)
    run = execute_ir(ir, {"source_path": "input.json", "dest_path": "output.json"}, workspace=workspace)
    assert run.state == RunState.VERIFIED_SUCCESS
    assert (workspace / "output.json").exists()


def test_empty_ir_cannot_produce_verified_success(workspace: Path):
    """Regression: empty workflow must not produce VERIFIED_SUCCESS."""
    from skillvm.ir import WorkflowIR
    ir = WorkflowIR(skill_id="empty", content_hash="x", nodes=[], edges=[])
    run = execute_ir(ir, {}, workspace=workspace)
    assert run.state != RunState.VERIFIED_SUCCESS


def test_no_verify_nodes_cannot_produce_verified_success(workspace: Path):
    """Regression: workflow with no verify nodes must not produce VERIFIED_SUCCESS."""
    ir = _compile(NO_VERIFY_SKILL)
    # Confirm no verify nodes exist.
    assert not any(n.type == "verify" for n in ir.nodes)
    run = execute_ir(ir, {"p": "out.txt"}, workspace=workspace)
    assert run.state != RunState.VERIFIED_SUCCESS
    assert run.state == RunState.SUCCEEDED_UNVERIFIED


def test_verify_node_never_reached_not_verified_success(workspace: Path):
    """Regression: verify node that was skipped must not count as VERIFIED_SUCCESS."""
    ir = _compile(COPY_JSON_SKILL)
    verify_ids = [n.id for n in ir.nodes if n.type == "verify"]
    assert verify_ids
    # Fault the first tool node so the verify node is never reached.
    tool_ids = [n.id for n in ir.nodes if n.type == "tool"]
    assert tool_ids
    faults = {tool_ids[0]: Exception("tool broke")}
    run = execute_ir(ir, {"source_path": "input.json", "dest_path": "output.json"}, workspace=workspace, _fault_nodes=faults)
    assert run.state == RunState.FAILED
    # Verify node must not be SUCCEEDED.
    for vid in verify_ids:
        rec = run.node_records.get(vid)
        if rec:
            assert rec.state != NodeState.SUCCEEDED


def test_verify_failure_no_verified_success(workspace: Path):
    """Regression: injecting fault on verify node must prevent VERIFIED_SUCCESS."""
    ir = _compile(COPY_JSON_SKILL)
    verify_ids = [n.id for n in ir.nodes if n.type == "verify"]
    assert verify_ids, "Expected at least one verify node"
    faults = {nid: Exception("injected fault") for nid in verify_ids}
    run = execute_ir(ir, {"source_path": "input.json", "dest_path": "output.json"}, workspace=workspace, _fault_nodes=faults)
    assert run.state != RunState.VERIFIED_SUCCESS


def test_required_verify_passes_gives_verified_success(workspace: Path):
    """Regression: when required verify passes, VERIFIED_SUCCESS is correct."""
    ir = _compile(COPY_JSON_SKILL)
    run = execute_ir(ir, {"source_path": "input.json", "dest_path": "output.json"}, workspace=workspace)
    assert run.state == RunState.VERIFIED_SUCCESS


def test_multiple_required_checks_partial_failure(workspace: Path):
    """Regression: all required verify nodes must pass for VERIFIED_SUCCESS."""
    ir = _compile(COPY_JSON_SKILL)
    verify_ids = [n.id for n in ir.nodes if n.type == "verify"]
    assert verify_ids
    # Fault only the last verify node.
    faults = {verify_ids[-1]: Exception("partial verify failure")}
    run = execute_ir(ir, {"source_path": "input.json", "dest_path": "output.json"}, workspace=workspace, _fault_nodes=faults)
    assert run.state != RunState.VERIFIED_SUCCESS


def test_malformed_ir_cannot_bypass_verification(workspace: Path):
    """Regression: malformed IR (no nodes) must not yield VERIFIED_SUCCESS."""
    from skillvm.ir import WorkflowIR
    ir = WorkflowIR(skill_id="malformed", content_hash="y", nodes=[], edges=[])
    run = execute_ir(ir, {}, workspace=workspace)
    assert run.state in (RunState.SUCCEEDED_UNVERIFIED, RunState.FAILED)
    assert run.state != RunState.VERIFIED_SUCCESS


# ---------------------------------------------------------------------------
# Existing tests preserved
# ---------------------------------------------------------------------------

def test_tool_failure_propagates(workspace: Path):
    ir = _compile(COPY_JSON_SKILL)
    tool_ids = [n.id for n in ir.nodes if n.type == "tool"]
    assert tool_ids
    run = execute_ir(ir, {"source_path": "input.json", "dest_path": "output.json"}, workspace=workspace, _fault_nodes={tool_ids[0]: Exception("tool broke")})
    assert run.state == RunState.FAILED


def test_duplicate_idempotency_key_blocked(workspace: Path):
    ir = _compile(COPY_JSON_SKILL)
    key = "test-idem-key-99"
    _RUN_REGISTRY.pop(key, None)  # clean up
    execute_ir(ir, {"source_path": "input.json", "dest_path": "output.json"}, workspace=workspace, idempotency_key=key)
    with pytest.raises(DuplicateRunError):
        execute_ir(ir, {"source_path": "input.json", "dest_path": "output.json"}, workspace=workspace, idempotency_key=key)
    _RUN_REGISTRY.pop(key, None)


def test_illegal_state_transition_raises():
    from skillvm.runtime import NodeRecord, NodeState
    rec = NodeRecord(node_id="x")
    rec.transition(NodeState.RUNNING)
    rec.transition(NodeState.SUCCEEDED)
    with pytest.raises(RuntimeError):
        rec.transition(NodeState.PENDING)  # SUCCEEDED -> PENDING is illegal


def test_approval_blocks_without_token(workspace: Path):
    skill = """\
---
id: irreversible-write
inputs:
  - name: p
    type: string
permissions: [fs.write]
effect_overrides:
  fs.write: irreversible
---
# burn
## Steps
1. Write hello to `p` with fs.write
"""
    ir = _compile(skill)
    run = execute_ir(ir, {"p": "out.txt"}, workspace=workspace)
    assert run.state == RunState.NEEDS_APPROVAL


def test_approval_with_token_succeeds(workspace: Path):
    skill = """\
---
id: irreversible-write2
inputs:
  - name: p
    type: string
permissions: [fs.write]
effect_overrides:
  fs.write: irreversible
---
# burn2
## Steps
1. Write hello to `p` with fs.write
"""
    ir = _compile(skill)
    approvals = {n.id: f"approved:{n.id}" for n in ir.nodes if n.type == "approval"}
    run = execute_ir(ir, {"p": "out2.txt"}, workspace=workspace, pending_approvals=approvals)
    # Should not be NEEDS_APPROVAL; no verify nodes so SUCCEEDED_UNVERIFIED is expected.
    assert run.state not in (RunState.NEEDS_APPROVAL, RunState.FAILED)


# ---------------------------------------------------------------------------
# Snapshot / rollback tests
# ---------------------------------------------------------------------------

def test_snapshot_restore(workspace: Path):
    """After restore, changed files are reverted."""
    from skillvm.tools import Sandbox
    f = workspace / "data.txt"
    f.write_text("original")
    sb = Sandbox(workspace=workspace, authorized_root=workspace)
    sb.snapshot()
    f.write_text("changed")
    sb.restore()
    assert f.read_text() == "original"
    sb.cleanup_snapshot()


def test_successful_run_cleans_snapshot(workspace: Path):
    """A successful run should clean up snapshot artifacts."""
    import os
    ir = _compile(COPY_JSON_SKILL)
    run = execute_ir(ir, {"source_path": "input.json", "dest_path": "output.json"}, workspace=workspace)
    assert run.state == RunState.VERIFIED_SUCCESS
    # Snapshot dir should be removed.
    snap = workspace.parent / f".snapshot_{workspace.name}"
    assert not snap.exists()


def test_failed_reversible_restores_state(workspace: Path):
    """Failed tool on a workspace with existing files -> snapshot is restored."""
    (workspace / "original.txt").write_text("keep me")
    ir = _compile(COPY_JSON_SKILL)
    tool_ids = [n.id for n in ir.nodes if n.type == "tool"]
    run = execute_ir(ir, {"source_path": "input.json", "dest_path": "output.json"}, workspace=workspace, _fault_nodes={tool_ids[0]: Exception("fail")})
    assert run.state == RunState.FAILED
    # Original file still exists after restore.
    assert (workspace / "original.txt").read_text() == "keep me"


def test_independent_runs_have_different_snapshot_paths(tmp_path: Path):
    """Concurrent runs use different workspace dirs -> no snapshot collision."""
    ws1 = tmp_path / "ws1"
    ws1.mkdir()
    (ws1 / "input.json").write_text('{"ok":true}')
    ws2 = tmp_path / "ws2"
    ws2.mkdir()
    (ws2 / "input.json").write_text('{"ok":true}')

    from skillvm.tools import Sandbox
    sb1 = Sandbox(workspace=ws1, authorized_root=ws1)
    sb2 = Sandbox(workspace=ws2, authorized_root=ws2)
    sb1.snapshot()
    sb2.snapshot()
    assert sb1._snapshot != sb2._snapshot
    sb1.cleanup_snapshot()
    sb2.cleanup_snapshot()
