"""test_server.py -- FastAPI server tests via httpx TestClient (no network)."""
from __future__ import annotations

import dataclasses
import json
import pytest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

import skillvm.server as server_module
from skillvm.server import app, _resolve_workspace

client = TestClient(app)

# ── Fixtures ──

VALID_SKILL = """\
---
id: srv-test
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
# Srv test
## Steps
1. Read `source_path` with fs.read
2. Parse the file with json.parse
3. Write the object to `dest_path` with fs.write
"""

BAD_SKILL = "not yaml at all {{{"


def _make_root_with_workspace(tmp_path: Path) -> tuple[Path, str, object]:
    """Create a workspace inside a temporary root; return (workspace_path, name, settings)."""
    root = tmp_path / "root"
    root.mkdir()
    ws = root / "myws"
    ws.mkdir()
    from skillvm.config import load_settings
    settings = dataclasses.replace(load_settings(), workspace_root=root)
    return ws, "myws", settings


# ── Health ──

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── Compile ──

def test_compile_valid_skill():
    r = client.post("/compile", json={"source": VALID_SKILL})
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "COMPILED"
    assert d["executable"] is True
    assert d["ir"] is not None
    assert d["total_steps"] > 0


def test_compile_rejected_skill():
    r = client.post("/compile", json={"source": BAD_SKILL})
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "REJECTED"
    assert d["ir"] is None
    assert len(d["diagnostics"]) > 0


def test_compile_diagnostics_have_required_fields():
    r = client.post("/compile", json={"source": VALID_SKILL})
    d = r.json()
    for diag in d["diagnostics"]:
        assert "code" in diag
        assert "severity" in diag
        assert "message" in diag


def test_compile_llm_false_uses_deterministic():
    """llm=false (default) must never call a provider — deterministic only."""
    r = client.post("/compile", json={"source": VALID_SKILL, "llm": False})
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "COMPILED"
    assert d["provider"] is None or d["provider"] == ""


# ── Run (via _resolve_workspace directly) ──

def test_run_valid_ir(tmp_path):
    ws, ws_name, settings = _make_root_with_workspace(tmp_path)
    (ws / "input.json").write_text('{"ok": true}', encoding="utf-8")

    # Compile
    cr = client.post("/compile", json={"source": VALID_SKILL})
    ir = cr.json()["ir"]
    assert ir is not None

    # Execute directly via execute_ir using the resolved workspace (bypasses HTTP root check).
    from skillvm.ir import WorkflowIR
    from skillvm.runtime import execute_ir, RunState
    workflow = WorkflowIR.model_validate(ir)
    run = execute_ir(workflow, {"source_path": "input.json", "dest_path": "output.json"}, workspace=ws)
    assert run.state in (RunState.VERIFIED_SUCCESS, RunState.FAILED, RunState.NEEDS_APPROVAL)


def test_run_verified_success(tmp_path):
    ws, ws_name, settings = _make_root_with_workspace(tmp_path)
    (ws / "src.json").write_text('{"ok": true}', encoding="utf-8")

    cr = client.post("/compile", json={"source": VALID_SKILL})
    ir_dict = cr.json()["ir"]

    from skillvm.ir import WorkflowIR
    from skillvm.runtime import execute_ir, RunState
    workflow = WorkflowIR.model_validate(ir_dict)
    run = execute_ir(workflow, {"source_path": "src.json", "dest_path": "dst.json"}, workspace=ws)
    assert run.state == RunState.VERIFIED_SUCCESS
    assert (ws / "dst.json").exists()


# ── _resolve_workspace security checks ──

def test_absolute_path_workspace_rejected(tmp_path):
    """Client sending absolute path as workspace must get HTTP 400."""
    from fastapi import HTTPException
    root = tmp_path / "root"
    root.mkdir()
    from skillvm.config import load_settings
    settings = dataclasses.replace(load_settings(), workspace_root=root)
    with pytest.raises(HTTPException) as exc_info:
        _resolve_workspace("/etc", settings)
    assert exc_info.value.status_code == 400


def test_traversal_workspace_rejected(tmp_path):
    """../traversal is rejected."""
    from fastapi import HTTPException
    root = tmp_path / "root"
    root.mkdir()
    from skillvm.config import load_settings
    settings = dataclasses.replace(load_settings(), workspace_root=root)
    with pytest.raises(HTTPException) as exc_info:
        _resolve_workspace("../escape", settings)
    assert exc_info.value.status_code == 400


def test_missing_workspace_rejected(tmp_path):
    """Non-existent workspace name is rejected."""
    from fastapi import HTTPException
    root = tmp_path / "root"
    root.mkdir()
    from skillvm.config import load_settings
    settings = dataclasses.replace(load_settings(), workspace_root=root)
    with pytest.raises(HTTPException) as exc_info:
        _resolve_workspace("no_such_ws", settings)
    assert exc_info.value.status_code == 400


def test_valid_workspace_resolved(tmp_path):
    """A valid relative workspace name inside root is resolved."""
    ws, ws_name, settings = _make_root_with_workspace(tmp_path)
    resolved = _resolve_workspace(ws_name, settings)
    assert resolved == ws.resolve()


# ── Other server routes ──

def test_get_run_not_found():
    r = client.get("/runs/nonexistent-run-id")
    assert r.status_code == 404


def test_run_invalid_ir():
    r = client.post("/runs", json={"ir": {"bad": "schema"}, "inputs": {}})
    assert r.status_code == 422


def test_run_absolute_path_rejected():
    """Client sending /etc as workspace must be rejected with 400 before listing contents."""
    cr = client.post("/compile", json={"source": VALID_SKILL})
    ir = cr.json()["ir"]
    r = client.post("/runs", json={
        "ir": ir, "inputs": {}, "workspace": "/etc"
    })
    assert r.status_code == 400


# ── UI ──

def test_ui_returns_html():
    r = client.get("/")
    assert r.status_code == 200


def test_run_approve_all_rejected(tmp_path):
    """approve_all=true is rejected with 400 as an unpermitted production mechanism."""
    ws, ws_name, settings = _make_root_with_workspace(tmp_path)
    cr = client.post("/compile", json={"source": VALID_SKILL})
    ir = cr.json()["ir"]
    with patch.object(server_module, "_SETTINGS", settings):
        r = client.post("/runs", json={"ir": ir, "inputs": {}, "workspace": ws_name, "approve_all": True})
        assert r.status_code == 400
        assert "approve_all" in r.json()["detail"].lower()


def test_run_approval_and_resumption_api(tmp_path):
    """Workflow requiring approval pauses, returns token, and resumes cleanly."""
    ws, ws_name, settings = _make_root_with_workspace(tmp_path)
    (ws / "in.txt").write_text("hello")

    approval_skill = """\
---
id: srv-approval
inputs:
  - name: p
    type: string
permissions: [fs.read, fs.write]
effect_overrides:
  fs.write: irreversible
---
# Srv approval
## Steps
1. Write done to `p` with fs.write
"""
    cr = client.post("/compile", json={"source": approval_skill})
    ir = cr.json()["ir"]
    assert ir is not None

    # Patch server_module._SETTINGS to use our test root
    with patch.object(server_module, "_SETTINGS", settings):
        r = client.post("/runs", json={"ir": ir, "inputs": {"p": "done.txt"}, "workspace": ws_name})
        assert r.status_code == 202
        data = r.json()
        assert data["state"] == "NEEDS_APPROVAL"
        assert len(data["pending_approvals"]) > 0
        node_id, token = next(iter(data["pending_approvals"].items()))

        # Wrong token is rejected with 403
        r_bad = client.post(f"/runs/{data['run_id']}/approve", json={"node_id": node_id, "token": "wrong_token"})
        assert r_bad.status_code == 403

        # Correct token resumes the run
        r_good = client.post(f"/runs/{data['run_id']}/approve", json={"node_id": node_id, "token": token})
        assert r_good.status_code == 200
        assert r_good.json()["state"] != "NEEDS_APPROVAL"
        assert (ws / "done.txt").exists()

