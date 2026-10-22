# test_security.py

> 20 nodes · cohesion 0.16

## Key Concepts

- **test_security.py** (17 connections) — `tests/test_security.py`
- **pytest** (14 connections)
- **Path** (9 connections)
- **._safe_path()** (8 connections) — `src/skillvm/tools.py`
- **test_symlink_escape_blocked()** (7 connections) — `tests/test_security.py`
- **SandboxError** (6 connections) — `src/skillvm/tools.py`
- **test_path_traversal_blocked()** (6 connections) — `tests/test_security.py`
- **test_unauthorized_permission_blocked_at_runtime()** (6 connections) — `tests/test_security.py`
- **test_unauthorized_tool_blocked()** (6 connections) — `tests/test_security.py`
- **test_prompt_injection_no_policy_effect()** (5 connections) — `tests/test_security.py`
- **NodeState_BLOCKED_or_FAILED()** (3 connections) — `tests/test_security.py`
- **ws()** (3 connections) — `tests/test_security.py`
- **Path** (2 connections)
- **.__init__()** (2 connections) — `src/skillvm/tools.py`
- **Resolve and enforce workspace boundary. Raises SandboxError on escape.** (1 connections) — `src/skillvm/tools.py`
- **fixture** (1 connections)
- **test_security.py -- adversarial tests from the security table in section 7.** (1 connections) — `tests/test_security.py`
- **Grant only fs.read; tool that needs fs.write must be BLOCKED.** (1 connections) — `tests/test_security.py`
- **Symlink pointing outside workspace is blocked.** (1 connections) — `tests/test_security.py`
- **Injected text in step description has no effect on granted permissions.** (1 connections) — `tests/test_security.py`

## Relationships

- [eval.py](eval.py.md) (15 shared connections)
- [execute_ir](execute_ir.md) (10 shared connections)
- [compile_skill](compile_skill.md) (5 shared connections)
- [providers.py](providers.py.md) (3 shared connections)
- [cli.py](cli.py.md) (2 shared connections)
- [redact.py](redact.py.md) (2 shared connections)
- [compiler.py](compiler.py.md) (1 shared connections)

## Source Files

- `src/skillvm/tools.py`
- `tests/test_security.py`

## Audit Trail

- EXTRACTED: 58 (84%)
- INFERRED: 11 (16%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*