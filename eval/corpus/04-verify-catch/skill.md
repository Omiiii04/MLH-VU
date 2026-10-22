---
id: eval-verify-catch
inputs:
  - name: dest_path
    type: string
permissions: [fs.write, verify.run]
postconditions:
  - kind: file_exists
    path: "{dest_path}"
---
# Verify Catch
## Steps
1. Write hello to `dest_path` with fs.write
