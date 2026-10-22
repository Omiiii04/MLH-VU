---
id: eval-file-list
inputs:
  - name: dir_path
    type: string
  - name: out_path
    type: string
permissions: [fs.list, fs.write, verify.run]
postconditions:
  - kind: file_exists
    path: "{out_path}"
nodes:
  - id: in_dir
    type: input
    name: dir_path
    value_type: string
  - id: in_out
    type: input
    name: out_path
    value_type: string
  - id: list_step
    type: tool
    tool: fs.list
    args:
      path: {$bind: in_dir}
    effect: read
    depends_on: [in_dir]
  - id: write_step
    type: tool
    tool: fs.write
    args:
      path: {$bind: in_out}
      content: {$bind: list_step}
    effect: reversible_write
    depends_on: [list_step, in_out]
  - id: verify_step
    type: verify
    check: file_exists
    args:
      path: {$bind: in_out}
    required: true
    depends_on: [write_step]
---

# List Directory
List the contents of a directory and write the entries to a JSON file.
