# Graph Report - MLH-VU  (2026-10-22)

## Corpus Check
- 38 files · ~15,315 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 4 file(s) not represented in the graph (top: (none) 3, .example 1)

## Summary
- 350 nodes · 927 edges · 12 communities (9 shown, 3 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 104 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `fa79657b`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- providers.py
- compiler.py
- execute_ir
- eval.py
- SkillVM
- test_security.py
- compile_skill
- test_server.py
- skillvm
- server.py
- FakeProvider

## God Nodes (most connected - your core abstractions)
1. `compile_skill()` - 38 edges
2. `execute_ir()` - 33 edges
3. `compile_with_llm()` - 27 edges
4. `FakeProvider` - 26 edges
5. `Settings` - 23 edges
6. `ProviderError` - 21 edges
7. `Sandbox` - 18 edges
8. `_build_nodes()` - 18 edges
9. `ProviderManager` - 15 edges
10. `Diagnostic` - 15 edges

## Surprising Connections (you probably didn't know these)
- `Known limitations` --references--> `compile()`  [INFERRED]
  README.md → src/skillvm/cli.py
- `test_auth_error_recorded_no_retry()` --uses--> `AuthError`  [INFERRED]
  tests/test_providers.py → src/skillvm/providers.py
- `test_live_fallback_chain()` --calls--> `GeminiProvider`  [INFERRED]
  tests/test_live.py → src/skillvm/providers.py
- `test_live_gemini_compile()` --calls--> `GeminiProvider`  [INFERRED]
  tests/test_live.py → src/skillvm/providers.py
- `test_model_not_found_no_retry_on_provider()` --uses--> `ModelNotFoundError`  [INFERRED]
  tests/test_providers.py → src/skillvm/providers.py

## Import Cycles
- None detected.

## Communities (12 total, 3 thin omitted)

### Community 0 - "providers.py"
Cohesion: 0.08
Nodes (20): Known limitations, approve(), compile(), eval(), _load_settings(), plan(), probe(), run() (+12 more)

### Community 1 - "compiler.py"
Cohesion: 0.10
Nodes (31): _build_nodes(), _check_postconditions(), _has_cycle(), dfs(), _validate_ir(), CompileStatus, d(), Diagnostic (+23 more)

### Community 2 - "execute_ir"
Cohesion: 0.11
Nodes (18): DuplicateRunError, execute_ir(), NodeRecord, NodeState, _resolve_args(), _resolve_template(), RunState, _compile() (+10 more)

### Community 3 - "eval.py"
Cohesion: 0.15
Nodes (11): check(), _infer_tool(), _path_from_step(), _aggregate(), _ground_truth(), _load_fixture(), run_baseline_arm(), run_eval() (+3 more)

### Community 4 - "SkillVM"
Cohesion: 0.18
Nodes (10): Architecture, Codebase Knowledge Graph (Graphify), Install, Providers, Quick start, Security, Skill format, SkillVM (+2 more)

### Community 5 - "test_security.py"
Cohesion: 0.09
Nodes (17): redact_obj(), redact_text(), _check_permission(), execute_tool(), PermissionError_, _run_check(), Sandbox, SandboxError (+9 more)

### Community 6 - "compile_skill"
Cohesion: 0.21
Nodes (14): compile_skill(), test_ambiguity_needs_review(), test_bad_binding_type_error(), test_bad_metadata_rejected(), test_cycle_rejected(), test_golden_copy_json(), test_irreversible_requires_approval(), test_llm_node_requires_schema_and_verify() (+6 more)

### Community 9 - "server.py"
Cohesion: 0.11
Nodes (19): _b(), _f(), _i(), load_settings(), RunRecord, approve_run(), ApproveRequest, compile_endpoint() (+11 more)

### Community 10 - "FakeProvider"
Cohesion: 0.08
Nodes (32): _build_prompt(), compile_with_llm(), FakeProvider, ProviderAttempt, ProviderManager, ProviderResult, excerpt(), _has_gemini() (+24 more)

## Knowledge Gaps
- **1 isolated node(s):** `skillvm`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 100 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `compile_skill()` connect `compile_skill` to `providers.py`, `compiler.py`, `execute_ir`, `eval.py`, `test_security.py`, `server.py`, `FakeProvider`?**
  _High betweenness centrality (0.121) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `compile_skill()` (e.g. with `CompileStatus` and `Diagnostic`) actually correct?**
  _`compile_skill()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `skillvm` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `providers.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07706766917293233 - nodes in this community are weakly interconnected._
- **Why does `execute_ir()` connect `execute_ir` to `providers.py`, `compiler.py`, `eval.py`, `test_security.py`, `server.py`?**
  _High betweenness centrality (0.097) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `execute_ir()` (e.g. with `EffectType` and `WorkflowIR`) actually correct?**
  _`execute_ir()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Should `compiler.py` be split into smaller, more focused modules?**
  _Cohesion score 0.10286382232612508 - nodes in this community are weakly interconnected._