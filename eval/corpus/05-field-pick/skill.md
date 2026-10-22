---
id: eval-field-pick
inputs:
  - name: source_path
    type: string
  - name: dest_path
    type: string
permissions: [fs.read, fs.write, json.parse, verify.run]
postconditions:
  - kind: file_exists
    path: "{dest_path}"
  - kind: file_contains_fields
    path: "{dest_path}"
    fields: [name, email]
nodes:
  - id: in_source
    type: input
    name: source_path
    value_type: string
  - id: in_dest
    type: input
    name: dest_path
    value_type: string
  - id: read_step
    type: tool
    tool: fs.read
    args:
      path: {$bind: in_source}
    effect: read
    depends_on: [in_source]
  - id: parse_step
    type: tool
    tool: json.parse
    args:
      text: {$bind: read_step}
    effect: read
    depends_on: [read_step]
  - id: pick_step
    type: transform
    op: pick_fields
    args:
      value: {$bind: parse_step}
      fields: [name, email]
    depends_on: [parse_step]
  - id: write_step
    type: tool
    tool: fs.write
    args:
      path: {$bind: in_dest}
      content: {$bind: pick_step}
    effect: reversible_write
    depends_on: [pick_step, in_dest]
  - id: verify_exists
    type: verify
    check: file_exists
    args:
      path: {$bind: in_dest}
    required: true
    depends_on: [write_step]
  - id: verify_fields
    type: verify
    check: file_contains_fields
    args:
      path: {$bind: in_dest}
      fields: [name, email]
    required: true
    depends_on: [write_step]
---

# Pick Fields
Extract only the `name` and `email` fields from a JSON object.
