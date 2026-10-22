---
id: eval-checksum
inputs:
  - name: file_path
    type: string
  - name: expected_checksum
    type: string
permissions: [fs.read, verify.run]
nodes:
  - id: in_file
    type: input
    name: file_path
    value_type: string
  - id: in_cksum
    type: input
    name: expected_checksum
    value_type: string
  - id: verify_step
    type: verify
    check: checksum_equals
    args:
      path: {$bind: in_file}
      checksum: {$bind: in_cksum}
    required: true
    depends_on: [in_file, in_cksum]
---

# Checksum Integrity Check
Verify a file's SHA-256 checksum matches the expected value.
