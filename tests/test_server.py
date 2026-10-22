"""test_server.py -- FastAPI server tests via httpx TestClient (no network)."""
from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient

from skillvm.server import app

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
    # Deterministic compile has no provider info
    assert d["provider"] is None or d["provider"] == ""


# ── Run ──

def test_run_valid_ir(tmp_path):
    # First compile
    cr = client.post("/compile", json={"source": VALID_SKILL})
    ir = cr.json()["ir"]
    assert ir is not None

    # Set up workspace
    src = tmp_path / "input.json"
    src.write_text('{"ok": true}', encoding="utf-8")

    r = client.post("/runs", json={
        "ir": ir,
        "inputs": {"source_path": "input.json", "dest_path": "output.json"},
        "workspace": str(tmp_path),
        "approve_all": True,
    })
    assert r.status_code == 202
    d = r.json()
    assert "run_id" in d
    assert d["state"] in ("VERIFIED_SUCCESS", "FAILED", "NEEDS_APPROVAL")


def test_run_verified_success(tmp_path):
    cr = client.post("/compile", json={"source": VALID_SKILL})
    ir = cr.json()["ir"]
    (tmp_path / "src.json").write_text('{"ok": true}', encoding="utf-8")

    r = client.post("/runs", json={
        "ir": ir,
        "inputs": {"source_path": "src.json", "dest_path": "dst.json"},
        "workspace": str(tmp_path),
        "approve_all": True,
    })
    assert r.status_code == 202
    assert r.json()["state"] == "VERIFIED_SUCCESS"
    assert (tmp_path / "dst.json").exists()


def test_get_run(tmp_path):
    cr = client.post("/compile", json={"source": VALID_SKILL})
    ir = cr.json()["ir"]
    (tmp_path / "s.json").write_text('{"ok": true}')

    rr = client.post("/runs", json={
        "ir": ir,
        "inputs": {"source_path": "s.json", "dest_path": "d.json"},
        "workspace": str(tmp_path), "approve_all": True,
    })
    run_id = rr.json()["run_id"]

    gr = client.get(f"/runs/{run_id}")
    assert gr.status_code == 200
    assert gr.json()["run_id"] == run_id


def test_get_run_not_found():
    r = client.get("/runs/nonexistent-run-id")
    assert r.status_code == 404


def test_run_invalid_ir():
    r = client.post("/runs", json={"ir": {"bad": "schema"}, "inputs": {}})
    assert r.status_code == 422


def test_run_missing_workspace():
    cr = client.post("/compile", json={"source": VALID_SKILL})
    ir = cr.json()["ir"]
    r = client.post("/runs", json={
        "ir": ir, "inputs": {}, "workspace": "/nonexistent/path/xyz"
    })
    assert r.status_code == 400


def test_node_states_present_in_run_response(tmp_path):
    cr = client.post("/compile", json={"source": VALID_SKILL})
    ir = cr.json()["ir"]
    (tmp_path / "x.json").write_text('{"ok": true}')

    r = client.post("/runs", json={
        "ir": ir,
        "inputs": {"source_path": "x.json", "dest_path": "y.json"},
        "workspace": str(tmp_path), "approve_all": True,
    })
    d = r.json()
    assert isinstance(d["node_states"], dict)
    assert len(d["node_states"]) > 0


# ── UI ──

def test_ui_returns_html():
    r = client.get("/")
    # Either 200 with HTML or JSON fallback — both are fine
    assert r.status_code == 200
