"""cli.py -- Typer CLI: compile, plan, run, approve, eval, probe."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(name="skillvm", no_args_is_help=True, help="SkillVM compiler and runtime.")


def _load_settings():
    from skillvm.config import load_settings
    return load_settings()


@app.command()
def compile(
    skill: Path = typer.Argument(..., help="Path to SKILL.md"),
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="Write IR JSON to file"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    llm: bool = typer.Option(False, "--llm", help="Use model-assisted compilation (skill text sent to configured providers)"),
):
    """Compile a SKILL.md to typed IR and show diagnostics."""
    source = skill.read_text(encoding="utf-8")

    if llm:
        from skillvm.llm_compile import compile_with_llm
        from skillvm.providers import build_manager
        settings = _load_settings()
        if not settings.local_only:
            typer.echo("Note: --llm is set and LLM_LOCAL_ONLY=false — skill text will be sent to remote providers.")
        manager = build_manager(settings)
        result = compile_with_llm(source, manager)
        if result.ir:
            typer.echo(f"Provider: {result.ir.provider}  Model: {result.ir.model}  Mode: {result.ir.constrained_mode}")
    else:
        from skillvm.compiler import compile_skill
        result = compile_skill(source)

    typer.echo(f"Status: {result.status.value}")
    typer.echo(f"Steps: {result.total_steps}  Fallback: {result.fallback_steps}")
    if result.diagnostics:
        for d in result.diagnostics:
            typer.echo(f"  [{d.code}] {d.severity.value}: {d.message}")
            if d.suggestion:
                typer.echo(f"    Suggestion: {d.suggestion}")

    if result.ir and out:
        out.write_text(result.ir.model_dump_json(indent=2), encoding="utf-8")
        typer.echo(f"IR written to {out}")
    elif result.ir and verbose:
        typer.echo(result.ir.model_dump_json(indent=2))

    if result.status.value == "REJECTED":
        raise typer.Exit(1)


@app.command()
def plan(
    ir_file: Path = typer.Argument(..., help="IR JSON file"),
):
    """Show execution plan from compiled IR."""
    from skillvm.ir import WorkflowIR
    ir = WorkflowIR.model_validate_json(ir_file.read_text(encoding="utf-8"))
    typer.echo(f"Skill: {ir.skill_id}  Nodes: {len(ir.nodes)}")
    typer.echo(f"Permissions: {ir.permissions}")
    for n in ir.nodes:
        effect = getattr(n, "effect", "-")
        typer.echo(f"  {n.id:25s}  {n.type:12s}  effect={effect}")


@app.command()
def run(
    ir_file: Path = typer.Argument(..., help="IR JSON file"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
    inputs_json: str = typer.Option("{}", "--inputs", "-i", help="JSON object of input values"),
    approve_all: bool = typer.Option(False, "--approve-all", help="Auto-approve all approval nodes"),
):
    """Execute a compiled IR."""
    from skillvm.ir import WorkflowIR
    from skillvm.runtime import execute_ir, RunState

    ir = WorkflowIR.model_validate_json(ir_file.read_text(encoding="utf-8"))
    inputs = json.loads(inputs_json)

    # Auto-approve: build approval dict
    approvals = {}
    if approve_all:
        for n in ir.nodes:
            if n.type == "approval":
                approvals[n.id] = f"approved:{n.id}"

    run_rec = execute_ir(ir, inputs, workspace=workspace, pending_approvals=approvals)
    typer.echo(f"Run ID: {run_rec.run_id}")
    typer.echo(f"State:  {run_rec.state.value}")
    for nid, rec in run_rec.node_records.items():
        typer.echo(f"  {nid:30s}  {rec.state.value}")
    if run_rec.failed_evidence:
        typer.echo("Failed evidence:")
        typer.echo(json.dumps(run_rec.failed_evidence, indent=2))
    if run_rec.state != RunState.VERIFIED_SUCCESS:
        raise typer.Exit(1)


@app.command()
def approve(
    run_id: str = typer.Argument(...),
    node_id: str = typer.Argument(...),
):
    """Generate an approval token for a run+node (stub for demo)."""
    token = f"approved:{node_id}"
    typer.echo(f"Approval token: {token}")
    typer.echo("Pass with --inputs or API call.")


@app.command()
def probe(
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="google|openrouter|lmstudio"),
):
    """Probe configured providers for capabilities and list available models."""
    from skillvm.providers import GeminiProvider, OpenAICompatProvider, AuthError, ProviderError
    settings = _load_settings()

    names = [provider] if provider else settings.provider_order
    for name in names:
        typer.echo(f"\n=== {name} ===")
        if settings.local_only and name != "lmstudio":
            typer.echo("  Skipped (LLM_LOCAL_ONLY=true)")
            continue
        try:
            if name == "google":
                p = GeminiProvider()
                models = p.list_models(settings)
                typer.echo(f"  Models: {models[:5]}")
                caps = p.probe(settings)
            elif name in ("openrouter", "lmstudio"):
                p = OpenAICompatProvider(name)
                models = p.list_models(settings)
                typer.echo(f"  Models: {models[:5]}")
                caps = p.probe(settings)
            else:
                typer.echo(f"  Unknown provider: {name}")
                continue
            typer.echo(f"  Capabilities: {caps}")
        except AuthError as e:
            typer.echo(f"  Auth error: {e}")
        except ProviderError as e:
            typer.echo(f"  Unavailable: {e}")
        except Exception as e:
            typer.echo(f"  Error: {e}")


@app.command()
def eval(
    corpus_dir: Path = typer.Option(Path("eval/corpus"), "--corpus"),
    n: int = typer.Option(3, "--n", help="Runs per skill"),
    out: Path = typer.Option(Path("eval/results.json"), "--out"),
    baseline: bool = typer.Option(True, "--baseline/--no-baseline"),
    live: bool = typer.Option(False, "--live", help="Run live LLM baseline and LLM-assisted SkillVM with configured provider"),
):
    """Run evaluation harness on the skill corpus."""
    from skillvm.eval import run_eval
    results = run_eval(corpus_dir=corpus_dir, n_per_skill=n, run_baseline=baseline, run_llm=live)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    typer.echo(f"Eval results written to {out}")
    if results.get("llm_baseline_skipped_reason"):
        typer.echo(f"LLM baseline skipped: {results['llm_baseline_skipped_reason']}")
    # Print summary
    arm_results = results.get("arms", {})
    for arm, metrics in arm_results.items():
        typer.echo(f"\n{arm}:")
        typer.echo(f"  task_success: {metrics.get('task_success_rate', 'N/A')}")
        typer.echo(f"  false_success_rate: {metrics.get('false_success_rate', 'N/A')}")
        typer.echo(f"  verified_success: {metrics.get('verified_success_rate', 'N/A')}")


@app.command()
def serve(
    host: str = typer.Option("", "--host", "-h", help="Override bind host (default from SKILLVM_BIND)"),
    port: int = typer.Option(0, "--port", "-p", help="Override port (default from SKILLVM_PORT)"),
    reload: bool = typer.Option(False, "--reload", help="Hot-reload for development"),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="Open browser on start"),
):
    """Start the SkillVM FastAPI service."""
    import uvicorn
    settings = _load_settings()
    _host = host or settings.bind
    _port = port or settings.port

    typer.echo(f"SkillVM API  ->  http://{_host}:{_port}")
    typer.echo(f"Docs         ->  http://{_host}:{_port}/docs")

    if open_browser:
        import threading, webbrowser, time
        def _open():
            time.sleep(1.2)
            webbrowser.open(f"http://{_host}:{_port}")
        threading.Thread(target=_open, daemon=True).start()

    uvicorn.run(
        "skillvm.server:app",
        host=_host,
        port=_port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    app()

