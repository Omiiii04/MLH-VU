---
id: eval-multi-step-chain
inputs:
  - name: raw_path
    type: string
  - name: slim_path
    type: string
  - name: out_path
    type: string
permissions: [fs.read, fs.write, json.parse, verify.run]
postconditions:
  - kind: file_exists
    path: "{out_path}"
  - kind: file_contains_fields
    path: "{out_path}"
    fields: [id, score]
nodes:
  - id: in_raw
    type: input
    name: raw_path
    value_type: string
  - id: in_slim
    type: input
    name: slim_path
    value_type: string
  - id: in_out
    type: input
    name: out_path
    value_type: string
  - id: read_raw
    type: tool
    tool: fs.read
    args:
      path: {$bind: in_raw}
    effect: read
    depends_on: [in_raw]
  - id: parse_raw
    type: tool
    tool: json.parse
    args:
      text: {$bind: read_raw}
    effect: read
    depends_on: [read_raw]
  - id: pick_step
    type: transform
    op: pick_fields
    args:
      value: {$bind: parse_raw}
      fields: [id, score]
    depends_on: [parse_raw]
  - id: write_slim
    type: tool
    tool: fs.write
    args:
      path: {$bind: in_slim}
      content: {$bind: pick_step}
    effect: reversible_write
    depends_on: [pick_step, in_slim]
  - id: read_slim
    type: tool
    tool: fs.read
    args:
      path: {$bind: in_slim}
    effect: read
    depends_on: [write_slim]
  - id: parse_slim
    type: tool
    tool: json.parse
    args:
      text: {$bind: read_slim}
    effect: read
    depends_on: [read_slim]
  - id: write_out
    type: tool
    tool: fs.write
    args:
      path: {$bind: in_out}
      content: {$bind: parse_slim}
    effect: reversible_write
    depends_on: [parse_slim, in_out]
  - id: verify_exists
    type: verify
    check: file_exists
    args:
      path: {$bind: in_out}
    required: true
    depends_on: [write_out]
  - id: verify_fields
    type: verify
    check: file_contains_fields
    args:
      path: {$bind: in_out}
      fields: [id, score]
    required: true
    depends_on: [write_out]
---

# Multi-Step Chain: Extract, Write, Read Back, Verify
A 3-phase dependency chain to test multi-step orchestration.
