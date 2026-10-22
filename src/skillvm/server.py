"""server.py -- FastAPI service for SkillVM.

Endpoints:
  GET  /health
  POST /compile          body: {source: str, llm?: bool}
  POST /runs             body: {ir: dict, inputs: dict, workspace?: str, approve_all?: bool}
  GET  /runs/{run_id}    poll run state
  POST /runs/{run_id}/approve  body: {node_id: str}
  GET  /                 serve UI

All runs are in-memory (no persistence in Tier 2).
Bound to 127.0.0.1 — no multi-user auth needed at this scope.
"""
from __future__ import annotations

import threading
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from skillvm import __version__
from skillvm.compiler import compile_skill
from skillvm.config import load_settings
from skillvm.ir import WorkflowIR
from skillvm.runtime import RunRecord, RunState, execute_ir

app = FastAPI(title="SkillVM", version=__version__, docs_url="/docs")

# ---------------------------------------------------------------------------
# In-memory state
# ---------------------------------------------------------------------------
_RUNS: dict[str, RunRecord] = {}
_LOCK = threading.Lock()
_SETTINGS = None


def _settings():
    global _SETTINGS
    if _SETTINGS is None:
        _SETTINGS = load_settings()
    return _SETTINGS


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class CompileRequest(BaseModel):
    source: str
    llm: bool = False


class CompileResponse(BaseModel):
    status: str
    total_steps: int = 0
    fallback_steps: int = 0
    executable: bool = False
    ir: dict | None = None
    diagnostics: list[dict] = []
    provider: str | None = None
    model: str | None = None
    constrained_mode: str | None = None


class RunRequest(BaseModel):
    ir: dict
    inputs: dict[str, Any] = {}
    workspace: str = "."
    approve_all: bool = False
    idempotency_key: str | None = None


class RunResponse(BaseModel):
    run_id: str
    state: str
    node_states: dict[str, str] = {}
    failed_evidence: list[dict] = []
    started_at: float | None = None
    finished_at: float | None = None


class ApproveRequest(BaseModel):
    node_id: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_to_response(run: RunRecord) -> RunResponse:
    return RunResponse(
        run_id=run.run_id,
        state=run.state.value,
        node_states={nid: rec.state.value for nid, rec in run.node_records.items()},
        failed_evidence=run.failed_evidence,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok", "version": __version__}


@app.post("/compile", response_model=CompileResponse)
def compile_endpoint(req: CompileRequest):
    if req.llm:
        from skillvm.llm_compile import compile_with_llm
        from skillvm.providers import build_manager
        s = _settings()
        manager = build_manager(s)
        result = compile_with_llm(req.source, manager)
    else:
        result = compile_skill(req.source)

    diags = [
        {"code": d.code, "severity": d.severity.value, "message": d.message, "suggestion": d.suggestion}
        for d in result.diagnostics
    ]
    ir_dict = result.ir.model_dump(mode="json") if result.ir else None
    resp = CompileResponse(
        status=result.status.value,
        total_steps=result.total_steps,
        fallback_steps=result.fallback_steps,
        executable=result.executable,
        ir=ir_dict,
        diagnostics=diags,
    )
    if result.ir:
        resp.provider = result.ir.provider
        resp.model = result.ir.model
        resp.constrained_mode = result.ir.constrained_mode
    return resp


@app.post("/runs", response_model=RunResponse, status_code=202)
def create_run(req: RunRequest):
    try:
        ir = WorkflowIR.model_validate(req.ir)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid IR: {e}")

    workspace = Path(req.workspace).resolve()
    if not workspace.exists():
        raise HTTPException(status_code=400, detail=f"Workspace not found: {workspace}")

    # Auto-approve if requested
    approvals = {}
    if req.approve_all:
        for n in ir.nodes:
            if n.type == "approval":
                approvals[n.id] = f"approved:{n.id}"

    try:
        run = execute_ir(
            ir,
            req.inputs,
            workspace=workspace,
            idempotency_key=req.idempotency_key,
            pending_approvals=approvals,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    with _LOCK:
        _RUNS[run.run_id] = run

    return _run_to_response(run)


@app.get("/runs/{run_id}", response_model=RunResponse)
def get_run(run_id: str):
    with _LOCK:
        run = _RUNS.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return _run_to_response(run)


@app.post("/runs/{run_id}/approve", response_model=RunResponse)
def approve_run(run_id: str, req: ApproveRequest):
    with _LOCK:
        run = _RUNS.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.state != RunState.NEEDS_APPROVAL:
        raise HTTPException(status_code=409, detail=f"Run is not awaiting approval (state={run.state.value})")

    # Re-execute with approval token injected
    try:
        ir_dict = {n.id: n for n in run.node_records}  # we need the original IR
    except Exception:
        pass

    # The run record doesn't store the IR — client must re-POST /runs with approval.
    # Return 409 with guidance.
    raise HTTPException(
        status_code=409,
        detail=(
            f"To approve node '{req.node_id}', re-POST /runs with the same IR+inputs "
            f"and add approve_all=true or inject the token via inputs."
        ),
    )


# ---------------------------------------------------------------------------
# Static UI
# ---------------------------------------------------------------------------

_UI_DIR = Path(__file__).parent / "ui"


@app.get("/", include_in_schema=False)
def serve_ui():
    index = _UI_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return JSONResponse({"message": "SkillVM API — UI not found. Try /docs"})


if _UI_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_UI_DIR)), name="static")
