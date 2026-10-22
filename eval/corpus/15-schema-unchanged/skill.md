---
id: eval-schema-unchanged
inputs:
  - name: file_path
    type: string
  - name: expected_keys
    type: string
permissions: [fs.read, verify.run]
nodes:
  - id: in_file
    type: input
    name: file_path
    value_type: string
  - id: verify_step
    type: verify
    check: schema_unchanged
    args:
      path: {$bind: in_file}
      keys: [id, name, version]
    required: true
    depends_on: [in_file]
---

# Schema Unchanged Check
Verify the top-level keys of a JSON config file have not drifted from the expected set.
