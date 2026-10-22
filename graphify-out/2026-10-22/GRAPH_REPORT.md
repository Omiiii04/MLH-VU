# Graph Report - MLH-VU  (2026-10-22)

## Corpus Check
- 36 files · ~11,761 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 4 file(s) not represented in the graph (top: (none) 3, .example 1)

## Summary
- 308 nodes · 843 edges · 12 communities (10 shown, 2 thin omitted)
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 103 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `2eabff01`
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
- FakeProvider

## God Nodes (most connected - your core abstractions)
1. `compile_skill()` - 36 edges
2. `execute_ir()` - 31 edges
3. `FakeProvider` - 26 edges
4. `compile_with_llm()` - 25 edges
5. `Settings` - 23 edges
6. `ProviderError` - 21 edges
7. `Sandbox` - 18 edges
8. `_build_nodes()` - 18 edges
9. `ProviderManager` - 15 edges
10. `Diagnostic` - 15 edges

## Surprising Connections (you probably didn't know these)
- `Known limitations` --references--> `compile()`  [INFERRED]
  README.md → src/skillvm/cli.py
- `test_live_fallback_chain()` --calls--> `compile_with_llm()`  [INFERRED]
  tests/test_live.py → src/skillvm/llm_compile.py
- `test_live_gemini_compile()` --calls--> `compile_with_llm()`  [INFERRED]
  tests/test_live.py → src/skillvm/llm_compile.py
- `test_live_lmstudio_compile()` --calls--> `compile_with_llm()`  [INFERRED]
  tests/test_live.py → src/skillvm/llm_compile.py
- `test_live_openrouter_compile()` --calls--> `compile_with_llm()`  [INFERRED]
  tests/test_live.py → src/skillvm/llm_compile.py

## Import Cycles
- None detected.

## Communities (12 total, 2 thin omitted)

### Community 0 - "providers.py"
Cohesion: 0.09
Nodes (22): Settings, AuthError, BaseProvider, build_manager(), _classify_genai_error(), GeminiProvider, ModelNotFoundError, OpenAICompatProvider (+14 more)

### Community 1 - "compiler.py"
Cohesion: 0.11
Nodes (30): _build_nodes(), _check_postconditions(), _has_cycle(), dfs(), _validate_ir(), CompileStatus, d(), Diagnostic (+22 more)

### Community 2 - "execute_ir"
Cohesion: 0.12
Nodes (18): DuplicateRunError, execute_ir(), NodeRecord, NodeState, _resolve_args(), _resolve_template(), RunRecord, RunState (+10 more)

### Community 3 - "eval.py"
Cohesion: 0.25
Nodes (11): check(), _infer_tool(), _path_from_step(), _aggregate(), _ground_truth(), _load_fixture(), run_baseline_arm(), run_eval() (+3 more)

### Community 4 - "cli.py"
Cohesion: 0.09
Nodes (17): Architecture, Codebase Knowledge Graph (Graphify), Install, Known limitations, Providers, Quick start, Skill format, SkillVM (+9 more)

### Community 5 - "test_security.py"
Cohesion: 0.09
Nodes (17): Security, _check_permission(), execute_tool(), PermissionError_, _run_check(), Sandbox, SandboxError, NodeState_BLOCKED_or_FAILED() (+9 more)

### Community 6 - "compile_skill"
Cohesion: 0.21
Nodes (14): compile_skill(), test_ambiguity_needs_review(), test_bad_binding_type_error(), test_bad_metadata_rejected(), test_cycle_rejected(), test_golden_copy_json(), test_irreversible_requires_approval(), test_llm_node_requires_schema_and_verify() (+6 more)

### Community 7 - "redact.py"
Cohesion: 0.43
Nodes (4): excerpt(), prompt_hash(), redact_obj(), redact_text()

### Community 9 - "pathlib"
Cohesion: 0.13
Nodes (5): _b(), _f(), _i(), load_settings(), settings()

### Community 10 - "FakeProvider"
Cohesion: 0.13
Nodes (20): _build_prompt(), compile_with_llm(), FakeProvider, _mgr(), test_llm_ir_passes_same_validator_as_deterministic(), test_malformed_ir_both_attempts_falls_back_to_deterministic(), test_malformed_ir_triggers_repair_then_valid(), test_provider_failure_falls_back_to_deterministic() (+12 more)

## Knowledge Gaps
- **1 isolated node(s):** `skillvm`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 78 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `compile_skill()` connect `compile_skill` to `compiler.py`, `execute_ir`, `eval.py`, `cli.py`, `test_security.py`, `FakeProvider`?**
  _High betweenness centrality (0.129) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `compile_skill()` (e.g. with `CompileStatus` and `Diagnostic`) actually correct?**
  _`compile_skill()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `skillvm` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `providers.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09143686502177069 - nodes in this community are weakly interconnected._
- **Why does `execute_ir()` connect `execute_ir` to `compiler.py`, `eval.py`, `cli.py`, `test_security.py`?**
  _High betweenness centrality (0.100) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `execute_ir()` (e.g. with `EffectType` and `WorkflowIR`) actually correct?**
  _`execute_ir()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Should `compiler.py` be split into smaller, more focused modules?**
  _Cohesion score 0.11245791245791245 - nodes in this community are weakly interconnected._