---
id: eval-bad-json
inputs:
  - name: source_path
    type: string
permissions: [fs.read, verify.run]
nodes:
  - id: in_source
    type: input
    name: source_path
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
  - id: verify_step
    type: verify
    check: file_contains_fields
    args:
      path: {$bind: in_source}
      fields: [valid]
    required: true
    depends_on: [parse_step]
---

# Parse Malformed JSON
Attempt to parse an invalid JSON file. Runtime should fail.
