---
id: eval-schema-validate-fail
inputs:
  - name: data_path
    type: string
permissions: [fs.read, verify.run]
nodes:
  - id: in_data
    type: input
    name: data_path
    value_type: string
  - id: verify_fields
    type: verify
    check: file_contains_fields
    args:
      path: {$bind: in_data}
      fields: [id, title, status]
    required: true
    depends_on: [in_data]
---

# Schema Validation - Missing Fields Case
Verify required fields; expect FAILED because input is missing 'status'.
