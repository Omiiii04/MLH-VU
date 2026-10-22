# Graph Report - MLH-VU  (2026-10-22)

## Corpus Check
- 38 files · ~17,047 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 4 file(s) not represented in the graph (top: (none) 3, .example 1)

## Summary
- 366 nodes · 947 edges · 13 communities (10 shown, 3 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 107 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7534e453`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- providers.py
- compiler.py
- execute_ir
- eval.py
- SkillVM
- redact.py
- compile_skill
- test_server.py
- skillvm
- server.py
- compile_with_llm
- cli.py

## God Nodes (most connected - your core abstractions)
1. `compile_skill()` - 38 edges
2. `execute_ir()` - 33 edges
3. `FakeProvider` - 27 edges
4. `compile_with_llm()` - 27 edges
5. `Settings` - 23 edges
6. `ProviderError` - 21 edges
7. `Sandbox` - 18 edges
8. `_build_nodes()` - 18 edges
9. `SkillVM` - 16 edges
10. `Diagnostic` - 15 edges

## Surprising Connections (you probably didn't know these)
- `Security and Sandboxing` --references--> `_validate_ir()`  [INFERRED]
  README.md → src/skillvm/compiler.py
- `Security and Sandboxing` --references--> `ApprovalNode`  [INFERRED]
  README.md → src/skillvm/ir.py
- `Testing` --references--> `FakeProvider`  [INFERRED]
  README.md → src/skillvm/providers.py
- `Security and Sandboxing` --references--> `_check_permission()`  [INFERRED]
  README.md → src/skillvm/tools.py
- `Testing` --references--> `test_symlink_escape_blocked()`  [EXTRACTED]
  README.md → tests/test_security.py

## Import Cycles
- None detected.

## Communities (13 total, 3 thin omitted)

### Community 0 - "providers.py"
Cohesion: 0.07
Nodes (33): Settings, AuthError, BaseProvider, build_manager(), _classify_genai_error(), FakeProvider, GeminiProvider, ModelNotFoundError (+25 more)

### Community 1 - "compiler.py"
Cohesion: 0.11
Nodes (30): _build_nodes(), _check_postconditions(), _has_cycle(), dfs(), _validate_ir(), CompileStatus, d(), Diagnostic (+22 more)

### Community 2 - "execute_ir"
Cohesion: 0.05
Nodes (34): Security and Sandboxing, DuplicateRunError, execute_ir(), NodeRecord, NodeState, _resolve_args(), _resolve_template(), RunState (+26 more)

### Community 3 - "eval.py"
Cohesion: 0.25
Nodes (11): check(), _infer_tool(), _path_from_step(), _aggregate(), _ground_truth(), _load_fixture(), run_baseline_arm(), run_eval() (+3 more)

### Community 4 - "SkillVM"
Cohesion: 0.07
Nodes (26): 1. Compile a Skill to Workflow IR, 2. Inspect the Execution Plan, 3. Execute a Workflow, 4. Generate an Approval Token, 5. Probe Configured Providers, 6. Run the Evaluation Harness, Architecture, Command-Line Interface (CLI) (+18 more)

### Community 5 - "redact.py"
Cohesion: 0.43
Nodes (4): excerpt(), prompt_hash(), redact_obj(), redact_text()

### Community 6 - "compile_skill"
Cohesion: 0.21
Nodes (14): compile_skill(), test_ambiguity_needs_review(), test_bad_binding_type_error(), test_bad_metadata_rejected(), test_cycle_rejected(), test_golden_copy_json(), test_irreversible_requires_approval(), test_llm_node_requires_schema_and_verify() (+6 more)

### Community 9 - "server.py"
Cohesion: 0.10
Nodes (19): _b(), _f(), _i(), load_settings(), RunRecord, approve_run(), ApproveRequest, compile_endpoint() (+11 more)

### Community 10 - "compile_with_llm"
Cohesion: 0.22
Nodes (9): _build_prompt(), compile_with_llm(), _mgr(), test_llm_ir_passes_same_validator_as_deterministic(), test_malformed_ir_both_attempts_falls_back_to_deterministic(), test_malformed_ir_triggers_repair_then_valid(), test_provider_failure_falls_back_to_deterministic(), test_provider_failure_no_fallback_rejects() (+1 more)

### Community 12 - "cli.py"
Cohesion: 0.14
Nodes (8): approve(), compile(), eval(), _load_settings(), plan(), probe(), run(), serve()

## Knowledge Gaps
- **1 isolated node(s):** `skillvm`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 113 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SkillVM` connect `SkillVM` to `execute_ir`?**
  _High betweenness centrality (0.131) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `compile_skill()` (e.g. with `CompileStatus` and `Diagnostic`) actually correct?**
  _`compile_skill()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `skillvm` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `providers.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07374254049445865 - nodes in this community are weakly interconnected._
- **Why does `compile_skill()` connect `compile_skill` to `compiler.py`, `execute_ir`, `eval.py`, `server.py`, `compile_with_llm`, `cli.py`?**
  _High betweenness centrality (0.110) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `execute_ir()` (e.g. with `EffectType` and `WorkflowIR`) actually correct?**
  _`execute_ir()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Should `compiler.py` be split into smaller, more focused modules?**
  _Cohesion score 0.11245791245791245 - nodes in this community are weakly interconnected._