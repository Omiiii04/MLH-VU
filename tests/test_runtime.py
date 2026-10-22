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
    approval_nodes = [n for n in ir.nodes if n.type == "approval"]
    assert approval_nodes
    anid = approval_nodes[0].id

    # 1. Predictable forged token is rejected -> run stays in NEEDS_APPROVAL
    forged = {anid: f"approved:{anid}"}
    run = execute_ir(ir, {"p": "out2.txt"}, workspace=workspace, pending_approvals=forged)
    assert run.state == RunState.NEEDS_APPROVAL
    token = run.pending_approvals.get(anid)
    assert token is not None
    assert token != f"approved:{anid}"

    # 2. Resuming with genuine per-run token succeeds
    from skillvm.runtime import resume_run
    resumed = resume_run(run, anid, token)
    assert resumed.state not in (RunState.NEEDS_APPROVAL, RunState.FAILED)
    assert (workspace / "out2.txt").exists()


def test_approval_resumption_does_not_reexecute_completed_side_effects(workspace: Path):
    """Resuming an approved workflow must not re-execute previously completed tool nodes."""
    skill = """\
---
id: approval-side-effect
inputs:
  - name: p1
    type: string
  - name: p2
    type: string
permissions: [fs.write]
effect_overrides:
  fs.write: irreversible
nodes:
  - id: in_p1
    type: input
    name: p1
    value_type: string
  - id: in_p2
    type: input
    name: p2
    value_type: string
  - id: step1
    type: tool
    tool: fs.write
    args:
      path: {$bind: in_p1}
      content: "initial_first_step"
    effect: reversible_write
    depends_on: [in_p1]
  - id: ask_user
    type: approval
    reason: "confirm before step2"
    effect: irreversible
    depends_on: [step1]
  - id: step2
    type: tool
    tool: fs.write
    args:
      path: {$bind: in_p2}
      content: "second_step_done"
    effect: reversible_write
    depends_on: [ask_user, in_p2]
---
# Test approval resumption
"""
    from skillvm.compiler import compile_skill
    from skillvm.runtime import resume_run
    ir = compile_skill(skill).ir
    assert ir is not None

    run = execute_ir(ir, {"p1": "step1.txt", "p2": "step2.txt"}, workspace=workspace)
    assert run.state == RunState.NEEDS_APPROVAL
    assert (workspace / "step1.txt").read_text() == "initial_first_step"
    assert not (workspace / "step2.txt").exists()

    # Tamper with step1 file to detect if step1 gets re-executed on resumption
    (workspace / "step1.txt").write_text("tampered_marker")

    token = run.pending_approvals["ask_user"]
    resumed = resume_run(run, "ask_user", token)
    assert resumed.state not in (RunState.NEEDS_APPROVAL, RunState.FAILED)

    # step2 was executed
    assert (workspace / "step2.txt").read_text() == "second_step_done"
    # step1 was NOT re-executed! It still has the marker!
    assert (workspace / "step1.txt").read_text() == "tampered_marker"



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


# ---------------------------------------------------------------------------
# Verifier correctness: row_count_delta and json_matches_schema
# ---------------------------------------------------------------------------

def test_verifier_row_count_delta_sqlite(workspace: Path):
    import sqlite3
    from skillvm.tools import execute_tool, Sandbox
    sb = Sandbox(workspace=workspace, authorized_root=workspace)

    # Missing db_path / table must fail explicitly (not pass unconditionally!)
    res_no_db = execute_tool("verify.run", {"check": "row_count_delta"}, ["verify.run"], sb)
    assert res_no_db["passed"] is False
    assert "error" in res_no_db["evidence"]

    # Setup sqlite database
    db_file = workspace / "test.db"
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("CREATE TABLE users (id INT, name TEXT)")
    cur.execute("INSERT INTO users VALUES (1, 'Alice'), (2, 'Bob'), (3, 'Charlie')")
    conn.commit()
    conn.close()

    # Genuine count check: matches
    res_match = execute_tool(
        "verify.run",
        {"check": "row_count_delta", "db_path": "test.db", "table": "users", "expected_count": 3},
        ["verify.run"],
        sb,
    )
    assert res_match["passed"] is True
    assert res_match["evidence"]["actual_count"] == 3

    # Genuine count check: mismatch fails
    res_mismatch = execute_tool(
        "verify.run",
        {"check": "row_count_delta", "db_path": "test.db", "table": "users", "expected_count": 99},
        ["verify.run"],
        sb,
    )
    assert res_mismatch["passed"] is False
    assert res_mismatch["evidence"]["actual_count"] == 3

    # Non-existent DB file fails
    res_missing_file = execute_tool(
        "verify.run",
        {"check": "row_count_delta", "db_path": "missing.db", "table": "users", "expected_count": 0},
        ["verify.run"],
        sb,
    )
    assert res_missing_file["passed"] is False


def test_verifier_json_matches_schema_nested_and_constraints(workspace: Path):
    import json
    from skillvm.tools import execute_tool, Sandbox
    sb = Sandbox(workspace=workspace, authorized_root=workspace)

    schema = {
        "type": "object",
        "required": ["id", "user", "tags"],
        "properties": {
            "id": {"type": "integer", "minimum": 1, "maximum": 100},
            "user": {
                "type": "object",
                "required": ["name", "email", "role"],
                "properties": {
                    "name": {"type": "string", "minLength": 2, "pattern": r"^[A-Z][a-z]+$"},
                    "email": {"type": "string"},
                    "role": {"type": "string", "enum": ["admin", "editor", "viewer"]},
                },
                "additionalProperties": False,
            },
            "tags": {
                "type": "array",
                "minItems": 1,
                "maxItems": 3,
                "uniqueItems": True,
                "items": {"type": "string"},
            },
        },
    }

    # 1. Valid data matching full nested schema
    valid_data = {
        "id": 10,
        "user": {"name": "Alice", "email": "alice@example.com", "role": "admin"},
        "tags": ["alpha", "beta"],
    }
    (workspace / "data.json").write_text(json.dumps(valid_data), encoding="utf-8")
    res = execute_tool(
        "verify.run",
        {"check": "json_matches_schema", "path": "data.json", "schema": schema},
        ["verify.run"],
        sb,
    )
    assert res["passed"] is True

    # 2. Constraint failure: pattern mismatch ("alice" not capitalized)
    invalid_pattern = dict(valid_data, user={"name": "alice", "email": "a@b.com", "role": "admin"})
    (workspace / "data.json").write_text(json.dumps(invalid_pattern), encoding="utf-8")
    res_pat = execute_tool(
        "verify.run",
        {"check": "json_matches_schema", "path": "data.json", "schema": schema},
        ["verify.run"],
        sb,
    )
    assert res_pat["passed"] is False
    assert "pattern" in res_pat["evidence"]["error"].lower()

    # 3. Array duplicate failure (uniqueItems)
    invalid_unique = dict(valid_data, tags=["tag1", "tag1"])
    (workspace / "data.json").write_text(json.dumps(invalid_unique), encoding="utf-8")
    res_unique = execute_tool(
        "verify.run",
        {"check": "json_matches_schema", "path": "data.json", "schema": schema},
        ["verify.run"],
        sb,
    )
    assert res_unique["passed"] is False
    assert "unique" in res_unique["evidence"]["error"].lower()

    # 4. Nested additionalProperties: False violation
    invalid_extra = dict(valid_data, user={"name": "Alice", "email": "a@b.com", "role": "admin", "extra": 123})
    (workspace / "data.json").write_text(json.dumps(invalid_extra), encoding="utf-8")
    res_extra = execute_tool(
        "verify.run",
        {"check": "json_matches_schema", "path": "data.json", "schema": schema},
        ["verify.run"],
        sb,
    )
    assert res_extra["passed"] is False
    assert "additional" in res_extra["evidence"]["error"].lower()


def test_verifier_json_matches_schema_malformed_schemas(workspace: Path):
    from skillvm.tools import execute_tool, Sandbox
    sb = Sandbox(workspace=workspace, authorized_root=workspace)
    (workspace / "sample_str.json").write_text('"sample text"', encoding="utf-8")

    # Non-dict schema
    res1 = execute_tool(
        "verify.run",
        {"check": "json_matches_schema", "path": "sample_str.json", "schema": "not a schema"},
        ["verify.run"],
        sb,
    )
    assert res1["passed"] is False
    assert "malformed" in res1["evidence"]["error"].lower()

    # Malformed regex pattern
    res2 = execute_tool(
        "verify.run",
        {"check": "json_matches_schema", "path": "sample_str.json", "schema": {"type": "string", "pattern": "[invalid("}},
        ["verify.run"],
        sb,
    )
    assert res2["passed"] is False
    assert "regex" in res2["evidence"]["error"].lower()

    # Unknown type
    res3 = execute_tool(
        "verify.run",
        {"check": "json_matches_schema", "path": "sample_str.json", "schema": {"type": "unknown_type"}},
        ["verify.run"],
        sb,
    )
    assert res3["passed"] is False
    assert "unknown type" in res3["evidence"]["error"].lower()

