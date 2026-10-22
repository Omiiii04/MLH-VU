---
id: eval-permission-violation
inputs:
  - name: out_path
    type: string
permissions: [fs.read]
nodes:
  - id: in_out
    type: input
    name: out_path
    value_type: string
  - id: write_step
    type: tool
    tool: fs.write
    args:
      path: {$bind: in_out}
      content: "unauthorized write attempt"
    effect: reversible_write
    depends_on: [in_out]
---

# Unauthorized Write
Attempt to write a file with only fs.read permission.
The runtime must block this. Claiming success is wrong.
