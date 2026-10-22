---
id: eval-missing-source
inputs:
  - name: source_path
    type: string
  - name: dest_path
    type: string
permissions: [fs.read, fs.write, verify.run]
postconditions:
  - kind: file_exists
    path: "{dest_path}"
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
  - id: write_step
    type: tool
    tool: fs.write
    args:
      path: {$bind: in_dest}
      content: {$bind: read_step}
    effect: reversible_write
    depends_on: [read_step, in_dest]
  - id: verify_step
    type: verify
    check: file_exists
    args:
      path: {$bind: in_dest}
    required: true
    depends_on: [write_step]
---

# Read Missing File
Attempt to read a file that does not exist. Task should fail.
