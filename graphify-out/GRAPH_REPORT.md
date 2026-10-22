# Graph Report - MLH-VU  (2026-10-22)

## Corpus Check
- 33 files · ~10,282 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 4 file(s) not represented in the graph (top: (none) 3, .example 1)

## Summary
- 273 nodes · 709 edges · 11 communities (10 shown, 1 thin omitted)
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 85 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `054fc9c1`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- providers.py
- compiler.py
- execute_ir
- eval.py
- cli.py
- test_security.py
- compile_skill
- redact.py
- skillvm
- pathlib
- SkillVM

## God Nodes (most connected - your core abstractions)
1. `compile_skill()` - 34 edges
2. `execute_ir()` - 31 edges
3. `Settings` - 23 edges
4. `FakeProvider` - 18 edges
5. `ProviderError` - 18 edges
6. `Sandbox` - 18 edges
7. `_build_nodes()` - 18 edges
8. `Diagnostic` - 14 edges
9. `run_baseline_arm()` - 14 edges
10. `execute_tool()` - 14 edges

## Surprising Connections (you probably didn't know these)
- `Known limitations` --references--> `compile()`  [INFERRED]
  README.md → src/skillvm/cli.py
- `NodeState_BLOCKED_or_FAILED()` --uses--> `NodeState`  [INFERRED]
  tests/test_security.py → src/skillvm/runtime.py
- `test_snapshot_restore()` --uses--> `Sandbox`  [INFERRED]
  tests/test_runtime.py → src/skillvm/tools.py
- `test_secrets_not_in_results()` --calls--> `redact_text()`  [INFERRED]
  tests/test_security.py → src/skillvm/redact.py
- `test_auth_error_recorded_no_retry()` --uses--> `AuthError`  [INFERRED]
  tests/test_providers.py → src/skillvm/providers.py

## Import Cycles
- None detected.

## Communities (11 total, 1 thin omitted)

### Community 0 - "providers.py"
Cohesion: 0.09
Nodes (27): Settings, AuthError, BaseProvider, build_manager(), _classify_genai_error(), FakeProvider, GeminiProvider, ModelNotFoundError (+19 more)

### Community 1 - "compiler.py"
Cohesion: 0.11
Nodes (28): _build_nodes(), _check_postconditions(), _has_cycle(), dfs(), _validate_ir(), CompileStatus, d(), Diagnostic (+20 more)

### Community 2 - "execute_ir"
Cohesion: 0.10
Nodes (20): run(), DuplicateRunError, execute_ir(), NodeRecord, NodeState, _resolve_args(), _resolve_template(), RunRecord (+12 more)

### Community 3 - "eval.py"
Cohesion: 0.25
Nodes (11): check(), _infer_tool(), _path_from_step(), _aggregate(), _ground_truth(), _load_fixture(), run_baseline_arm(), run_eval() (+3 more)

### Community 4 - "cli.py"
Cohesion: 0.15
Nodes (7): Known limitations, approve(), compile(), eval(), _load_settings(), plan(), probe()

### Community 5 - "test_security.py"
Cohesion: 0.10
Nodes (16): Security, _check_permission(), execute_tool(), PermissionError_, _run_check(), Sandbox, SandboxError, NodeState_BLOCKED_or_FAILED() (+8 more)

### Community 6 - "compile_skill"
Cohesion: 0.21
Nodes (14): compile_skill(), test_ambiguity_needs_review(), test_bad_binding_type_error(), test_bad_metadata_rejected(), test_cycle_rejected(), test_golden_copy_json(), test_irreversible_requires_approval(), test_llm_node_requires_schema_and_verify() (+6 more)

### Community 7 - "redact.py"
Cohesion: 0.47
Nodes (3): excerpt(), redact_obj(), redact_text()

### Community 9 - "pathlib"
Cohesion: 0.15
Nodes (4): _b(), _f(), _i(), load_settings()

### Community 10 - "SkillVM"
Cohesion: 0.20
Nodes (9): Architecture, Codebase Knowledge Graph (Graphify), Install, Providers, Quick start, Skill format, SkillVM, Tests (+1 more)

## Knowledge Gaps
- **1 isolated node(s):** `skillvm`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 67 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `compile_skill()` connect `compile_skill` to `compiler.py`, `execute_ir`, `eval.py`, `cli.py`, `test_security.py`?**
  _High betweenness centrality (0.145) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `compile_skill()` (e.g. with `CompileStatus` and `Diagnostic`) actually correct?**
  _`compile_skill()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `skillvm` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `providers.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08892921960072596 - nodes in this community are weakly interconnected._
- **Why does `execute_ir()` connect `execute_ir` to `compiler.py`, `eval.py`, `cli.py`, `test_security.py`?**
  _High betweenness centrality (0.122) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `execute_ir()` (e.g. with `EffectType` and `WorkflowIR`) actually correct?**
  _`execute_ir()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Should `compiler.py` be split into smaller, more focused modules?**
  _Cohesion score 0.11224489795918367 - nodes in this community are weakly interconnected._