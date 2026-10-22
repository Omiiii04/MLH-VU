"""tools.py -- sandboxed tool implementations.

Sandbox: each run operates on a copy of the authorized workspace directory.
This is a workspace-level boundary, NOT an OS-level sandbox.
Defences: path traversal, symlink escape, permission enforcement before each call.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from skillvm.diag import d
from skillvm.registry import TOOLS, EffectType


class SandboxError(Exception):
    pass


class PermissionError_(Exception):  # avoids shadowing builtin
    pass


class Sandbox:
    """Per-run isolated workspace sandbox with snapshot and restoration.

    Guarantees:
    - Per-run snapshot isolation (uses run_id) prevents concurrent runs from
      clobbering snapshots.
    - Snapshot failures are reported as SandboxError rather than silently ignored.
    - Restores strictly within the declared workspace inside authorized_root.
    - Boundary note: Workspace restoration rolls back reversible filesystem changes
      inside the workspace directory only. External side effects (out-of-tree files,
      external database modifications, or network requests) cannot be rolled back
      by workspace restoration.
    """

    def __init__(self, workspace: Path, authorized_root: Path, run_id: str | None = None):
        self.workspace = workspace.resolve()
        self.authorized_root = authorized_root.resolve()
        import uuid
        self.run_id = run_id or uuid.uuid4().hex
        self._snapshot: Path | None = None

    def snapshot(self) -> None:
        snap = self.workspace.parent / f".snapshot_{self.workspace.name}_{self.run_id}"
        if snap.exists():
            shutil.rmtree(snap, ignore_errors=True)
        try:
            shutil.copytree(self.workspace, snap)
        except Exception as e:
            raise SandboxError(f"Failed to create workspace snapshot: {e}") from e
        self._snapshot = snap

    def restore(self) -> None:
        if not self._snapshot or not self._snapshot.exists():
            raise SandboxError("No snapshot available to restore")
        # Ensure workspace is strictly within authorized_root before restoring
        try:
            self.workspace.relative_to(self.authorized_root)
        except ValueError:
            raise SandboxError("Restoration blocked: workspace is outside authorized root")
        if self.workspace.exists():
            shutil.rmtree(self.workspace)
        shutil.copytree(self._snapshot, self.workspace)

    def _safe_path(self, rel: str) -> Path:
        """Resolve and enforce workspace boundary. Raises SandboxError on escape."""
        p = (self.workspace / rel).resolve()
        try:
            p.relative_to(self.workspace)
        except ValueError:
            raise SandboxError(f"Path traversal blocked: {rel!r}")
        # Symlink escape check
        check = Path(rel)
        parts = Path(os.path.normpath(rel)).parts
        accum = self.workspace
        for part in parts:
            accum = accum / part
            if accum.is_symlink():
                target = accum.resolve()
                try:
                    target.relative_to(self.workspace)
                except ValueError:
                    raise SandboxError(f"Symlink escape blocked: {rel!r} -> {target}")
        return p

    def cleanup_snapshot(self) -> None:
        if self._snapshot and self._snapshot.exists():
            shutil.rmtree(self._snapshot, ignore_errors=True)


def _check_permission(tool_name: str, granted: list[str]) -> None:
    spec = TOOLS.get(tool_name)
    if spec is None:
        raise PermissionError_(f"Unknown tool '{tool_name}'")
    required = set(spec.permissions)
    if not required.issubset(set(granted)):
        missing = required - set(granted)
        raise PermissionError_(f"Tool '{tool_name}' requires permissions {missing}, only {granted} granted")


def execute_tool(
    tool_name: str,
    args: dict[str, Any],
    granted_permissions: list[str],
    sandbox: Sandbox,
) -> dict[str, Any]:
    """Execute a tool inside the sandbox. Enforces permissions server-side."""
    # Permission check first — before any side effect
    _check_permission(tool_name, granted_permissions)

    spec = TOOLS[tool_name]

    if tool_name == "fs.read":
        path = str(args.get("path", ""))
        p = sandbox._safe_path(path)
        if not p.exists():
            raise FileNotFoundError(f"fs.read: {path!r} not found")
        content = p.read_text(encoding="utf-8")
        return {"path": path, "content": content}

    elif tool_name == "fs.list":
        path = str(args.get("path", "."))
        p = sandbox._safe_path(path)
        if not p.exists():
            raise FileNotFoundError(f"fs.list: {path!r} not found")
        entries = [e.name for e in p.iterdir()]
        return {"path": path, "entries": entries}

    elif tool_name == "fs.write":
        path = str(args.get("path", ""))
        content = args.get("content", "")
        p = sandbox._safe_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, (dict, list)):
            p.write_text(json.dumps(content, indent=2), encoding="utf-8")
        else:
            p.write_text(str(content), encoding="utf-8")
        return {"path": path, "bytes_written": p.stat().st_size}

    elif tool_name == "json.parse":
        text = str(args.get("text", ""))
        try:
            value = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"json.parse: {e}")
        return {"value": value}

    elif tool_name == "data.transform":
        op = str(args.get("op", "identity"))
        value = args.get("value")
        if op in ("identity", "passthrough_unverified"):
            return {"value": value}
        elif op == "pick_fields":
            fields = args.get("fields", [])
            if isinstance(value, dict):
                return {"value": {k: value[k] for k in fields if k in value}}
            return {"value": value}
        elif op == "set_field":
            field = str(args.get("field", ""))
            val = args.get("set")
            if isinstance(value, dict):
                out = dict(value)
                out[field] = val
                return {"value": out}
            return {"value": value}
        elif op == "merge":
            extra = args.get("set", {})
            if isinstance(value, dict) and isinstance(extra, dict):
                return {"value": {**value, **extra}}
            return {"value": value}
        else:
            raise ValueError(f"data.transform: unknown op '{op}'")

    elif tool_name == "verify.run":
        check = str(args.get("check", ""))
        return _run_check(check, args, sandbox)

    else:
        raise ValueError(f"No implementation for tool '{tool_name}'")


# ---------------------------------------------------------------------------
# Postcondition checkers (restricted library, no free-form code)
# ---------------------------------------------------------------------------

def validate_json_schema(instance: Any, schema: Any) -> tuple[bool, str | None]:
    """Validate instance against schema. Returns (passed, error_message)."""
    if isinstance(schema, bool):
        return (schema, None if schema else "Schema is false (matches nothing)")
    if not isinstance(schema, dict):
        return (False, f"Malformed schema: expected dict or bool, got {type(schema).__name__}")

    # const
    if "const" in schema:
        if instance != schema["const"]:
            return (False, f"Value {instance!r} does not match const {schema['const']!r}")

    # enum
    if "enum" in schema:
        enum_vals = schema["enum"]
        if not isinstance(enum_vals, list):
            return (False, "Malformed schema: 'enum' must be a list")
        if instance not in enum_vals:
            return (False, f"Value {instance!r} is not in enum {enum_vals!r}")

    # type
    if "type" in schema:
        types = schema["type"]
        if isinstance(types, str):
            types = [types]
        elif not isinstance(types, list) or not all(isinstance(t, str) for t in types):
            return (False, "Malformed schema: 'type' must be a string or list of strings")

        valid_type_names = {"null", "boolean", "integer", "number", "string", "array", "object"}
        for t in types:
            if t not in valid_type_names:
                return (False, f"Malformed schema: unknown type {t!r}")

        def matches_type(val: Any, t: str) -> bool:
            if t == "null":
                return val is None
            if t == "boolean":
                return isinstance(val, bool)
            if t == "integer":
                return isinstance(val, int) and not isinstance(val, bool)
            if t == "number":
                return isinstance(val, (int, float)) and not isinstance(val, bool)
            if t == "string":
                return isinstance(val, str)
            if t == "array":
                return isinstance(val, list)
            if t == "object":
                return isinstance(val, dict)
            return False

        if not any(matches_type(instance, t) for t in types):
            return (False, f"Expected type {'/'.join(types)}, got {type(instance).__name__}")

    # String constraints
    if isinstance(instance, str):
        if "minLength" in schema:
            min_len = schema["minLength"]
            if not isinstance(min_len, int) or min_len < 0:
                return (False, "Malformed schema: 'minLength' must be a non-negative integer")
            if len(instance) < min_len:
                return (False, f"String length {len(instance)} is less than minLength {min_len}")
        if "maxLength" in schema:
            max_len = schema["maxLength"]
            if not isinstance(max_len, int) or max_len < 0:
                return (False, "Malformed schema: 'maxLength' must be a non-negative integer")
            if len(instance) > max_len:
                return (False, f"String length {len(instance)} exceeds maxLength {max_len}")
        if "pattern" in schema:
            pat = schema["pattern"]
            if not isinstance(pat, str):
                return (False, "Malformed schema: 'pattern' must be a string")
            try:
                import re
                regex = re.compile(pat)
            except Exception as e:
                return (False, f"Malformed schema: invalid regex pattern {pat!r}: {e}")
            if not regex.search(instance):
                return (False, f"String {instance!r} does not match pattern {pat!r}")

    # Numeric constraints
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema:
            m = schema["minimum"]
            if not isinstance(m, (int, float)) or isinstance(m, bool):
                return (False, "Malformed schema: 'minimum' must be a number")
            if instance < m:
                return (False, f"Value {instance} is less than minimum {m}")
        if "maximum" in schema:
            m = schema["maximum"]
            if not isinstance(m, (int, float)) or isinstance(m, bool):
                return (False, "Malformed schema: 'maximum' must be a number")
            if instance > m:
                return (False, f"Value {instance} exceeds maximum {m}")
        if "exclusiveMinimum" in schema:
            m = schema["exclusiveMinimum"]
            if not isinstance(m, (int, float)) or isinstance(m, bool):
                return (False, "Malformed schema: 'exclusiveMinimum' must be a number")
            if instance <= m:
                return (False, f"Value {instance} is not strictly greater than exclusiveMinimum {m}")
        if "exclusiveMaximum" in schema:
            m = schema["exclusiveMaximum"]
            if not isinstance(m, (int, float)) or isinstance(m, bool):
                return (False, "Malformed schema: 'exclusiveMaximum' must be a number")
            if instance >= m:
                return (False, f"Value {instance} is not strictly less than exclusiveMaximum {m}")
        if "multipleOf" in schema:
            m = schema["multipleOf"]
            if not isinstance(m, (int, float)) or isinstance(m, bool) or m <= 0:
                return (False, "Malformed schema: 'multipleOf' must be a positive number")
            quot = instance / m
            if abs(quot - round(quot)) > 1e-9:
                return (False, f"Value {instance} is not a multiple of {m}")

    # Array constraints
    if isinstance(instance, list):
        if "minItems" in schema:
            mi = schema["minItems"]
            if not isinstance(mi, int) or mi < 0:
                return (False, "Malformed schema: 'minItems' must be a non-negative integer")
            if len(instance) < mi:
                return (False, f"Array length {len(instance)} is less than minItems {mi}")
        if "maxItems" in schema:
            mi = schema["maxItems"]
            if not isinstance(mi, int) or mi < 0:
                return (False, "Malformed schema: 'maxItems' must be a non-negative integer")
            if len(instance) > mi:
                return (False, f"Array length {len(instance)} exceeds maxItems {mi}")
        if schema.get("uniqueItems") is True:
            seen = []
            for item in instance:
                if item in seen:
                    return (False, f"Array items are not unique: duplicate found {item!r}")
                seen.append(item)
        if "items" in schema:
            item_schema = schema["items"]
            if isinstance(item_schema, (dict, bool)):
                for idx, item in enumerate(instance):
                    ok, err = validate_json_schema(item, item_schema)
                    if not ok:
                        return (False, f"Item at index {idx} failed schema: {err}")
            elif isinstance(item_schema, list):
                for idx, ischema in enumerate(item_schema):
                    if idx < len(instance):
                        ok, err = validate_json_schema(instance[idx], ischema)
                        if not ok:
                            return (False, f"Tuple item at index {idx} failed schema: {err}")
            else:
                return (False, "Malformed schema: 'items' must be a dict, bool, or list")

    # Object constraints
    if isinstance(instance, dict):
        if "required" in schema:
            req = schema["required"]
            if not isinstance(req, list) or not all(isinstance(k, str) for k in req):
                return (False, "Malformed schema: 'required' must be a list of strings")
            missing = [k for k in req if k not in instance]
            if missing:
                return (False, f"Missing required properties: {missing}")
        if "minProperties" in schema:
            mp = schema["minProperties"]
            if not isinstance(mp, int) or mp < 0:
                return (False, "Malformed schema: 'minProperties' must be a non-negative integer")
            if len(instance) < mp:
                return (False, f"Object properties count {len(instance)} is less than minProperties {mp}")
        if "maxProperties" in schema:
            mp = schema["maxProperties"]
            if not isinstance(mp, int) or mp < 0:
                return (False, "Malformed schema: 'maxProperties' must be a non-negative integer")
            if len(instance) > mp:
                return (False, f"Object properties count {len(instance)} exceeds maxProperties {mp}")
        props = schema.get("properties", {})
        if not isinstance(props, dict):
            return (False, "Malformed schema: 'properties' must be a dict")
        for prop_name, prop_schema in props.items():
            if prop_name in instance:
                ok, err = validate_json_schema(instance[prop_name], prop_schema)
                if not ok:
                    return (False, f"Property {prop_name!r} failed schema: {err}")
        if "additionalProperties" in schema:
            add_props = schema["additionalProperties"]
            extra_keys = [k for k in instance if k not in props]
            if add_props is False and extra_keys:
                return (False, f"Additional properties not allowed: {extra_keys}")
            elif isinstance(add_props, (dict, bool)) and add_props is not True:
                for k in extra_keys:
                    ok, err = validate_json_schema(instance[k], add_props)
                    if not ok:
                        return (False, f"Additional property {k!r} failed schema: {err}")

    # Combinators: allOf, anyOf, oneOf, not
    if "allOf" in schema:
        subschemas = schema["allOf"]
        if not isinstance(subschemas, list):
            return (False, "Malformed schema: 'allOf' must be a list")
        for idx, sub in enumerate(subschemas):
            ok, err = validate_json_schema(instance, sub)
            if not ok:
                return (False, f"allOf[{idx}] failed: {err}")
    if "anyOf" in schema:
        subschemas = schema["anyOf"]
        if not isinstance(subschemas, list):
            return (False, "Malformed schema: 'anyOf' must be a list")
        passed_any = False
        errs = []
        for idx, sub in enumerate(subschemas):
            ok, err = validate_json_schema(instance, sub)
            if ok:
                passed_any = True
                break
            errs.append(err)
        if not passed_any:
            return (False, f"None of anyOf conditions matched: {errs}")
    if "oneOf" in schema:
        subschemas = schema["oneOf"]
        if not isinstance(subschemas, list):
            return (False, "Malformed schema: 'oneOf' must be a list")
        matches = sum(1 for sub in subschemas if validate_json_schema(instance, sub)[0])
        if matches != 1:
            return (False, f"Expected exactly one match in oneOf, matched {matches}")
    if "not" in schema:
        ok, _ = validate_json_schema(instance, schema["not"])
        if ok:
            return (False, "Value matched forbidden 'not' schema")

    return (True, None)


def _run_check(kind: str, args: dict[str, Any], sandbox: Sandbox) -> dict[str, Any]:
    try:
        if kind == "file_exists":
            path = str(args.get("path", ""))
            p = sandbox._safe_path(path)
            passed = p.exists()
            return {"passed": passed, "evidence": {"path": path, "exists": passed}}

        elif kind == "file_contains_fields":
            path = str(args.get("path", ""))
            fields = args.get("fields", [])
            p = sandbox._safe_path(path)
            if not p.exists():
                return {"passed": False, "evidence": {"error": "file not found"}}
            data = json.loads(p.read_text(encoding="utf-8"))
            missing = [f for f in fields if f not in (data if isinstance(data, dict) else {})]
            return {"passed": not missing, "evidence": {"missing_fields": missing}}

        elif kind == "json_matches_schema":
            path = str(args.get("path", ""))
            schema = args.get("schema", {})
            p = sandbox._safe_path(path)
            if not p.exists():
                return {"passed": False, "evidence": {"error": "file not found"}}
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception as e:
                return {"passed": False, "evidence": {"error": f"JSON decode error: {e}"}}
            passed, err = validate_json_schema(data, schema)
            evidence: dict[str, Any] = {"path": path}
            if not passed:
                evidence["error"] = err
            return {"passed": passed, "evidence": evidence}

        elif kind == "checksum_equals":
            import hashlib
            path = str(args.get("path", ""))
            expected = str(args.get("checksum", ""))
            p = sandbox._safe_path(path)
            if not p.exists():
                return {"passed": False, "evidence": {"error": "file not found"}}
            actual = hashlib.sha256(p.read_bytes()).hexdigest()
            return {"passed": actual == expected, "evidence": {"expected": expected, "actual": actual}}

        elif kind == "row_count_delta":
            import sqlite3
            import re
            db_path = args.get("db_path") or args.get("path")
            table = args.get("table")
            if not db_path or not table:
                return {
                    "passed": False,
                    "evidence": {
                        "error": "row_count_delta requires 'db_path' and 'table'. External relational databases are not configured/supported in local sandbox."
                    }
                }
            p = sandbox._safe_path(str(db_path))
            if not p.exists():
                return {"passed": False, "evidence": {"error": f"Database file not found: {db_path}"}}
            if not re.match(r"^[A-Za-z0-9_]+$", str(table)):
                return {"passed": False, "evidence": {"error": f"Invalid table name: {table}"}}
            try:
                conn = sqlite3.connect(p)
                cursor = conn.cursor()
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                conn.close()

                expected_count = args.get("expected_count")
                expected_delta = args.get("expected_delta")
                initial_count = args.get("initial_count", 0)

                if expected_count is not None:
                    passed = (count == int(expected_count))
                    return {"passed": passed, "evidence": {"table": table, "actual_count": count, "expected_count": int(expected_count)}}
                elif expected_delta is not None:
                    actual_delta = count - int(initial_count)
                    passed = (actual_delta == int(expected_delta))
                    return {"passed": passed, "evidence": {"table": table, "actual_delta": actual_delta, "expected_delta": int(expected_delta), "current_count": count}}
                else:
                    return {"passed": True, "evidence": {"table": table, "row_count": count}}
            except Exception as e:
                return {"passed": False, "evidence": {"error": f"Database check failed: {e}"}}

        elif kind == "schema_unchanged":
            # Compare JSON keys at top level
            path = str(args.get("path", ""))
            expected_keys = args.get("keys", [])
            p = sandbox._safe_path(path)
            if not p.exists():
                return {"passed": False, "evidence": {"error": "file not found"}}
            data = json.loads(p.read_text(encoding="utf-8"))
            actual_keys = list(data.keys()) if isinstance(data, dict) else []
            return {"passed": set(actual_keys) == set(expected_keys), "evidence": {"actual": actual_keys, "expected": expected_keys}}

        elif kind == "http_status":
            # ponytail: tool is local-only, no network; mark as not applicable
            return {"passed": False, "evidence": {"error": "http_status not available in local-only mode"}}

        else:
            return {"passed": False, "evidence": {"error": f"Unknown check kind: {kind}"}}

    except Exception as e:
        return {"passed": False, "evidence": {"error": str(e)}}
