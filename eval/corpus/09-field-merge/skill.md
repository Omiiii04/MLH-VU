---
id: eval-field-merge
inputs:
  - name: base_path
    type: string
  - name: patch_path
    type: string
  - name: out_path
    type: string
permissions: [fs.read, fs.write, json.parse, verify.run]
postconditions:
  - kind: file_exists
    path: "{out_path}"
nodes:
  - id: in_base
    type: input
    name: base_path
    value_type: string
  - id: in_patch
    type: input
    name: patch_path
    value_type: string
  - id: in_out
    type: input
    name: out_path
    value_type: string
  - id: read_base
    type: tool
    tool: fs.read
    args:
      path: {$bind: in_base}
    effect: read
    depends_on: [in_base]
  - id: parse_base
    type: tool
    tool: json.parse
    args:
      text: {$bind: read_base}
    effect: read
    depends_on: [read_base]
  - id: read_patch
    type: tool
    tool: fs.read
    args:
      path: {$bind: in_patch}
    effect: read
    depends_on: [in_patch]
  - id: parse_patch
    type: tool
    tool: json.parse
    args:
      text: {$bind: read_patch}
    effect: read
    depends_on: [read_patch]
  - id: merge_step
    type: transform
    op: merge
    args:
      value: {$bind: parse_base}
      set: {$bind: parse_patch}
    depends_on: [parse_base, parse_patch]
  - id: write_step
    type: tool
    tool: fs.write
    args:
      path: {$bind: in_out}
      content: {$bind: merge_step}
    effect: reversible_write
    depends_on: [merge_step, in_out]
  - id: verify_step
    type: verify
    check: file_exists
    args:
      path: {$bind: in_out}
    required: true
    depends_on: [write_step]
---

# Merge JSON Objects
Read two JSON files and write their merged result.
