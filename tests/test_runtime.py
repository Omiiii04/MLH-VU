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


@pytest.fixture()
def workspace(tmp_path: Path):
    ws = tmp_path / "ws"
    ws.mkdir()
    src = ws / "input.json"
    src.write_text("{\"ok\": true}", encoding="utf-8")
    return ws


def _compile(src: str):
    r = compile_skill(src)
    assert r.ir is not None, f"compile failed: {[d.message for d in r.diagnostics]}"
    return r.ir


def test_success_run(workspace: Path):
    ir = _compile(COPY_JSON_SKILL)
    run = execute_ir(ir, {"source_path": "input.json", "dest_path": "output.json"}, workspace=workspace)
    assert run.state == RunState.VERIFIED_SUCCESS
    assert (workspace / "output.json").exists()


def test_verify_failure_no_verified_success(workspace: Path, tmp_path: Path):
    """Injecting fault on verify node must prevent VERIFIED_SUCCESS."""
    ir = _compile(COPY_JSON_SKILL)
    # Inject fault on the verify node
    verify_ids = [n.id for n in ir.nodes if n.type == "verify"]
    assert verify_ids, "Expected at least one verify node"
    faults = {nid: Exception("injected fault") for nid in verify_ids}
    run = execute_ir(ir, {"source_path": "input.json", "dest_path": "output.json"}, workspace=workspace, _fault_nodes=faults)
    assert run.state != RunState.VERIFIED_SUCCESS


def test_tool_failure_propagates(workspace: Path):
    ir = _compile(COPY_JSON_SKILL)
    # Inject failure on first tool step
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
    # No approvals provided — should block
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
    # Should not be NEEDS_APPROVAL anymore
    assert run.state != RunState.NEEDS_APPROVAL


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
