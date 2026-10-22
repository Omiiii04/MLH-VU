# compile_skill

> 17 nodes · cohesion 0.21

## Key Concepts

- **compile_skill()** (34 connections) — `src/skillvm/compiler.py`
- **test_compiler.py** (16 connections) — `tests/test_compiler.py`
- **test_golden_copy_json()** (4 connections) — `tests/test_compiler.py`
- **test_cycle_rejected()** (3 connections) — `tests/test_compiler.py`
- **test_malformed_ir_rejected()** (3 connections) — `tests/test_security.py`
- **Path** (2 connections)
- **test_ambiguity_needs_review()** (2 connections) — `tests/test_compiler.py`
- **test_bad_binding_type_error()** (2 connections) — `tests/test_compiler.py`
- **test_bad_metadata_rejected()** (2 connections) — `tests/test_compiler.py`
- **test_irreversible_requires_approval()** (2 connections) — `tests/test_compiler.py`
- **test_llm_node_requires_schema_and_verify()** (2 connections) — `tests/test_compiler.py`
- **test_malformed_frontmatter_rejected()** (2 connections) — `tests/test_compiler.py`
- **test_subjective_step_is_fallback_not_free_code()** (2 connections) — `tests/test_compiler.py`
- **test_unsupported_node_rejected()** (2 connections) — `tests/test_compiler.py`
- **test_vacuous_postcondition_rejected()** (2 connections) — `tests/test_compiler.py`
- **test_valid_skill_compiles_to_runnable_ir()** (2 connections) — `tests/test_compiler.py`
- **Hostile IR with bad node types must be rejected, nothing executes.** (1 connections) — `tests/test_security.py`

## Relationships

- [compiler.py](compiler.py.md) (15 shared connections)
- [test_security.py](test_security.py.md) (5 shared connections)
- [cli.py](cli.py.md) (3 shared connections)
- [eval.py](eval.py.md) (2 shared connections)
- [execute_ir](execute_ir.md) (2 shared connections)

## Source Files

- `src/skillvm/compiler.py`
- `tests/test_compiler.py`
- `tests/test_security.py`

## Audit Trail

- EXTRACTED: 51 (93%)
- INFERRED: 4 (7%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*