---
id: eval-path-traversal
inputs:
  - name: target_path
    type: string
permissions: [fs.read, fs.write, verify.run]
nodes:
  - id: in_target
    type: input
    name: target_path
    value_type: string
  - id: read_step
    type: tool
    tool: fs.read
    args:
      path: {$bind: in_target}
    effect: read
    depends_on: [in_target]
---

# Path Traversal Attempt
Attempt to read a file outside the workspace sandbox using relative traversal (e.g. ../escape.txt).
The runtime sandbox must block the escape and fail execution.
