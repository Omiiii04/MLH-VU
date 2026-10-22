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
    # Relative workspace name under the configured SKILLVM_WORKSPACE_ROOT.
    # Absolute paths and path traversal are rejected by the server.
    workspace: str = "default"
    approve_all: bool = False
    idempotency_key: str | None = None


class RunResponse(BaseModel):
    run_id: str
    state: str
    node_states: dict[str, str] = {}
    failed_evidence: list[dict] = []
    started_at: float | None = None
    finished_at: float | None = None
    pending_approvals: dict[str, str] = {}


class ApproveRequest(BaseModel):
    node_id: str
    token: str


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
        pending_approvals=dict(run.pending_approvals),
    )


def _resolve_workspace(requested: str, settings) -> Path:
    """Resolve a client-supplied workspace name against the configured root.

    Rules:
    - The root is taken from server config (SKILLVM_WORKSPACE_ROOT), never from
      the client request.
    - Empty paths, whitespace, and "." are rejected.
    - Absolute paths and drive/root-relative paths in `requested` are rejected.
    - Resolved path must be a strict descendant of the root (not the root itself).
    - Symlinks must not escape the root or resolve to the root itself.
    """
    root = settings.workspace_root.resolve()

    if not isinstance(requested, str) or not requested.strip():
        raise HTTPException(status_code=400, detail="Workspace path cannot be empty.")

    clean_req = requested.strip()
    if clean_req == ".":
        raise HTTPException(status_code=400, detail="Workspace cannot be the root directory ('.').")

    req_path = Path(clean_req)
    # Reject absolute paths (including POSIX /etc and Windows drive letters or leading slashes).
    if req_path.is_absolute() or clean_req.startswith(("/", "\\")) or (len(clean_req) > 1 and clean_req[1] == ":"):
        raise HTTPException(status_code=400, detail="Workspace must be a relative path name, not an absolute path.")

    candidate = (root / clean_req).resolve()

    # Must be a strict descendant: root in candidate.parents and candidate != root.
    if candidate == root or root not in candidate.parents:
        raise HTTPException(
            status_code=400,
            detail="Workspace path must be a strict descendant of the configured workspace root, not the root itself."
        )

    # Enforce containment — raises ValueError if candidate escapes root.
    try:
        rel_parts = candidate.relative_to(root).parts
    except ValueError:
        raise HTTPException(status_code=400, detail="Workspace path must remain inside the configured workspace root.")

    if not rel_parts:
        raise HTTPException(status_code=400, detail="Workspace path cannot be the workspace root.")

    # Symlink containment check: walk each component from the root.
    accum = root
    for part in rel_parts:
        accum = accum / part
        if accum.is_symlink():
            real = accum.resolve()
            if real == root or root not in real.parents:
                raise HTTPException(status_code=400, detail="Symlink in workspace path must resolve to a strict descendant of workspace root.")
            try:
                real.relative_to(root)
            except ValueError:
                raise HTTPException(status_code=400, detail="Symlink in workspace path escapes workspace root.")

    if not candidate.exists():
        raise HTTPException(status_code=400, detail=f"Workspace not found: {requested!r}")
    if not candidate.is_dir():
        raise HTTPException(status_code=400, detail=f"Workspace is not a directory: {requested!r}")

    return candidate


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

    workspace = _resolve_workspace(req.workspace, _settings())

    # Do not trust approve_all=true as a production authorization mechanism
    if req.approve_all:
        raise HTTPException(
            status_code=400,
            detail="approve_all=true is rejected. It is not a permitted production authorization mechanism. Explicit per-node approval tokens are required."
        )

    try:
        run = execute_ir(
            ir,
            req.inputs,
            workspace=workspace,
            idempotency_key=req.idempotency_key,
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

    from skillvm.runtime import resume_run
    from skillvm.tools import PermissionError_
    try:
        resumed = resume_run(run, req.node_id, req.token)
    except PermissionError_ as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    with _LOCK:
        _RUNS[run_id] = resumed

    return _run_to_response(resumed)


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
