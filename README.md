# SkillVM

A compiler and deterministic runtime that turns natural-language agent skills (`SKILL.md`) into typed, verified workflows.

**Headline claim**: compiling a skill to a typed workflow with deterministic verification lowers the **false-success rate** vs giving the same model the raw skill as a prompt.

Eval on 4 skills (n=2 per skill):

| Arm      | task_success | false_success_rate | verified_success |
|----------|-------------|-------------------|-----------------|
| SkillVM  | 0.75        | **0.00**          | 0.50            |
| Baseline | 0.50        | **0.25**          | 0.00            |

## Install

```powershell
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
```

## Quick start

```powershell
# Compile
.venv\Scripts\skillvm compile path/to/skill.md --out ir.json

# Plan
.venv\Scripts\skillvm plan ir.json

# Run (approve all for demo)
.venv\Scripts\skillvm run ir.json --workspace . --inputs "{}" --approve-all

# Eval
.venv\Scripts\skillvm eval --corpus eval/corpus --n 3 --out eval/results.json

# Probe providers
.venv\Scripts\skillvm probe
```

## Tests

```powershell
.venv\Scripts\python -m pytest tests/ -v
```

All 38 tests pass (1 skipped: symlinks on Windows).

## Codebase Knowledge Graph (Graphify)

SkillVM uses [Graphify](https://github.com/Graphify-Labs/graphify) to build and query an AST-based knowledge graph of the codebase, enabling visual architecture exploration and fast context lookups.

```powershell
# Query knowledge graph
.venv\Scripts\graphify query "how does the compiler work?"

# Explain a node or trace paths
.venv\Scripts\graphify explain "compile_skill"
.venv\Scripts\graphify path "Sandbox" "compile_skill"

# Update graph after code changes
.venv\Scripts\graphify extract . --code-only
.venv\Scripts\graphify cluster-only .

# Visualizations and reports:
# - graphify-out/graph.html (interactive force-directed graph)
# - graphify-out/GRAPH_TREE.html (collapsible hierarchy tree)
# - graphify-out/GRAPH_REPORT.md (god nodes, community hubs, architecture insights)
# - graphify-out/wiki/index.md (navigable wiki)
```

## Providers

Copy `.env.example` to `.env` and fill in keys.

- **Google Gemini** (`GEMINI_API_KEY`, `GEMINI_MODEL`): use `skillvm probe --provider google` to list available models. Gemma 4 on the Gemini API may not support system instructions or JSON mode in all configurations; the provider prepends system instructions to the user turn as a fallback.
- **OpenRouter** (`OPENROUTER_API_KEY`, `OPENROUTER_MODEL`): OpenAI-compatible endpoint.
- **LM Studio** (`LMSTUDIO_BASE_URL`, `LMSTUDIO_MODEL`): Start LM Studio server, load a model, then run `skillvm probe --provider lmstudio` to verify the model ID.

Set `LLM_LOCAL_ONLY=true` to skip all remote providers. **Note**: setting `LLM_LOCAL_ONLY` after a request was already sent remotely does not restore privacy for that request.

## Skill format

```markdown
---
id: my-skill            # required, unique
inputs:
  - name: source_path
    type: string        # string | number | boolean
permissions: [fs.read, fs.write, json.parse, verify.run]
postconditions:
  - kind: file_exists
    path: "{source_path}"
  - kind: json_matches_schema
    path: "{source_path}"
    schema: {type: object, required: [ok]}
effect_overrides:
  fs.write: irreversible   # override default effect type
---

# Title

## Steps
1. Read `source_path` with fs.read
2. Parse the file with json.parse
3. Write the object to `dest_path` with fs.write
```

**Postcondition kinds**: `file_exists`, `file_contains_fields`, `json_matches_schema`, `row_count_delta`, `checksum_equals`, `schema_unchanged`, `http_status`.

**Effect types**: `read` (no approval, retryable), `reversible_write` (snapshot restore), `irreversible` / `external` (always behind approval node, never auto-retried).

## Architecture

```
SKILL.md
  └─ parse.py          frontmatter + step extraction
  └─ compiler.py       validate → build IR graph → diagnostics
  └─ ir.py             Pydantic IR schema (WorkflowIR, Node types)
  └─ registry.py       tool specs (fs.read/list/write, json.parse, data.transform, verify.run)
  └─ runtime.py        dependency scheduler → execute_ir → RunRecord
  └─ tools.py          sandboxed tool implementations + postcondition checkers
  └─ providers.py      GeminiProvider, OpenAICompatProvider, FakeProvider, ProviderManager
  └─ eval.py           skillvm-arm vs baseline-arm harness
  └─ cli.py            Typer: compile, plan, run, approve, eval, probe
```

## Security

| Threat | Mitigation |
|--------|-----------|
| Path traversal | `Sandbox._safe_path()` resolves and checks `relative_to(workspace)` |
| Symlink escape | Symlink targets verified inside workspace |
| Unauthorized tool | Permission check server-side before every invocation |
| Malformed IR | Pydantic validation + compiler rejects; nothing executes |
| Prompt injection | Injected text in skill steps has no effect on runtime policy |
| Forged approval | Token must be exactly `approved:{node_id}` |
| Runaway execution | Per-node timeouts, retry caps, idempotency key deduplication |
| Secret leakage | `redact.py` strips keys from logs/excerpts; never persisted |

**Boundary**: workspace sandbox is a directory copy, not an OS-level container. A process with access to the host filesystem can escape it. Document this honestly.

## Known limitations

- No streaming output
- No multi-user auth (API bound to 127.0.0.1 only)
- `http_status` verifier disabled in local-only mode
- `row_count_delta` verifier is a stub (no DB)
- LLM-assisted compilation (Phase 4) not yet wired to CLI `compile` (FakeProvider works; live requires credentials)
- Tier 2 (FastAPI service + UI) not built

## Tier 3 (future work)

Skill version diffing, PostgreSQL persistence, streaming, image input, multi-user auth, compensation beyond snapshot restore.
