---
id: eval-perm-violation
inputs:
  - name: p
    type: string
permissions: [fs.read, verify.run]
postconditions:
  - kind: file_exists
    path: "{p}"
---
# Permission Violation
## Steps
1. Read `p` with fs.read
2. Write results to `p` with fs.write
