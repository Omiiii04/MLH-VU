---
id: eval-copy-json
inputs:
  - name: source_path
    type: string
  - name: dest_path
    type: string
permissions: [fs.read, fs.write, json.parse, verify.run]
postconditions:
  - kind: file_exists
    path: "{dest_path}"
  - kind: json_matches_schema
    path: "{dest_path}"
    schema:
      type: object
      required: [value]
---

# Copy JSON
## Steps
1. Read `source_path` with fs.read
2. Parse the file with json.parse
3. Write the object to `dest_path` with fs.write
