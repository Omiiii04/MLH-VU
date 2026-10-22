from pathlib import Path

import pytest

from skillvm.compiler import compile_skill
from skillvm.ir import CompileStatus


CLEAN_SKILL = """\
---
id: copy-json
inputs:
  - name: source_path
    type: string
  - name: dest_path
    type: string
permissions: [fs.read, fs.write, json.parse, verify.run]
postconditions:
  - kind: file_exists
    path: "{dest_path}"
  - kind: json_matches_schema
    path: "{dest_path}"
    schema:
      type: object
      required: [ok]
---

# Copy JSON

Copy a JSON object from source to dest.

## Steps
1. Read `source_path` with fs.read
2. Parse the file with json.parse
3. Write the object to `dest_path` with fs.write
"""


def test_valid_skill_compiles_to_runnable_ir():
    result = compile_skill(CLEAN_SKILL)
    assert result.status == CompileStatus.COMPILED
    assert result.ir is not None
    assert result.ir.skill_id == "copy-json"
    types = {n.type for n in result.ir.nodes}
    assert "tool" in types
    assert "verify" in types
    assert result.total_steps >= 3
    assert result.fallback_steps == 0


def test_malformed_frontmatter_rejected():
    result = compile_skill("this is not a skill")
    assert result.status == CompileStatus.REJECTED
    assert any(d.code.startswith("SV1") for d in result.diagnostics)


def test_bad_metadata_rejected():
    src = """---
id: ""
---
# x
## Steps
1. Read a with fs.read
"""
    result = compile_skill(src)
    assert result.status == CompileStatus.REJECTED
    assert any(d.code == "SV1002" for d in result.diagnostics)


def test_cycle_rejected(tmp_path: Path):
    src = """---
id: cyclic
inputs:
  - name: a
    type: string
permissions: [fs.read]
nodes:
  - id: n1
    type: tool
    tool: fs.read
    args: {path: x}
    depends_on: [n2]
  - id: n2
    type: tool
    tool: fs.read
    args: {path: y}
    depends_on: [n1]
---
# cyclic
"""
    result = compile_skill(src)
    assert result.status == CompileStatus.REJECTED
    assert any(d.code == "SV2004" for d in result.diagnostics)


def test_bad_binding_type_error():
    src = """---
id: bad-bind
inputs:
  - name: n
    type: number
permissions: [fs.read]
nodes:
  - id: in_n
    type: input
    name: n
  - id: r
    type: tool
    tool: fs.read
    args:
      path: {$bind: in_n}
    depends_on: [in_n]
---
# x
"""
    result = compile_skill(src)
    assert result.status == CompileStatus.REJECTED
    assert any(d.code.startswith("SV2") for d in result.diagnostics)


def test_unsupported_node_rejected():
    src = """---
id: loop
nodes:
  - id: x
    type: loop
---
# x
"""
    result = compile_skill(src)
    assert result.status == CompileStatus.REJECTED
    assert any(d.code == "SV1005" for d in result.diagnostics)


def test_vacuous_postcondition_rejected():
    src = """---
id: vacuous
inputs:
  - name: p
    type: string
permissions: [fs.read, verify.run]
postconditions:
  - kind: always_true
---
# x
## Steps
1. Read `p` with fs.read
"""
    result = compile_skill(src)
    assert result.status == CompileStatus.REJECTED
    assert any(d.code == "SV3003" for d in result.diagnostics)


def test_ambiguity_needs_review():
    src = """---
id: ambiguous
inputs:
  - name: p
    type: string
permissions: [fs.read, fs.write]
---
# maybe
## Steps
1. Maybe read or write the thing at p somehow
"""
    result = compile_skill(src)
    assert result.status == CompileStatus.NEEDS_REVIEW
    assert result.ir is None or not result.executable
    assert any(d.code == "SV3001" for d in result.diagnostics)


def test_subjective_step_is_fallback_not_free_code():
    src = """---
id: summary
inputs:
  - name: p
    type: string
permissions: [fs.read, fs.write, verify.run]
postconditions:
  - kind: file_exists
    path: out.txt
---
# summary
## Steps
1. Read `p` with fs.read
2. Write a good summary to out.txt
"""
    result = compile_skill(src)
    assert result.total_steps >= 2
    assert result.fallback_steps >= 1
    assert result.status in (CompileStatus.COMPILED, CompileStatus.NEEDS_REVIEW)


def test_irreversible_requires_approval():
    src = """---
id: burn
inputs:
  - name: p
    type: string
permissions: [fs.write]
effect_overrides:
  fs.write: irreversible
---
# burn
## Steps
1. Write hello to `p` with fs.write
"""
    result = compile_skill(src)
    assert result.status == CompileStatus.COMPILED
    types = [n.type for n in result.ir.nodes]
    assert "approval" in types


def test_llm_node_requires_schema_and_verify():
    src = """---
id: llmish
permissions: [verify.run]
nodes:
  - id: think
    type: llm
    prompt: invent json
---
# x
"""
    result = compile_skill(src)
    assert result.status == CompileStatus.REJECTED
    codes = {d.code for d in result.diagnostics}
    assert "SV2006" in codes or "SV2007" in codes


def test_golden_copy_json(tmp_path: Path):
    result = compile_skill(CLEAN_SKILL)
    assert result.status == CompileStatus.COMPILED
    dumped = result.ir.model_dump(mode="json")
    dumped["content_hash"] = "HASH"
    dumped["compiled_at"] = "TS"
    golden = Path(__file__).parent / "goldens" / "copy-json.json"
    import json
    if not golden.exists():
        pytest.skip("golden written by implementation pass")
    expected = json.loads(golden.read_text(encoding="utf-8"))
    for key in ("nodes", "edges", "inputs", "outputs", "skill_id"):
        assert dumped[key] == expected[key]
