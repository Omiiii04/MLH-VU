from __future__ import annotations

from dataclasses import dataclass, field

from skillvm.ir import EffectType

ALLOWED_TOOLS = ("fs.read", "fs.list", "fs.write", "json.parse", "data.transform", "verify.run")


@dataclass(frozen=True)
class ToolSpec:
    name: str
    version: str
    arg_schema: dict
    result_schema: dict
    permissions: tuple[str, ...]
    effect: EffectType
    timeout_seconds: float
    idempotent: bool
    requires_approval: bool
    arg_types: dict[str, str] = field(default_factory=dict)


TOOLS: dict[str, ToolSpec] = {
    "fs.read": ToolSpec(
        name="fs.read",
        version="1",
        arg_schema={"type": "object", "required": ["path"], "properties": {"path": {"type": "string"}}},
        result_schema={"type": "object", "required": ["path", "content"]},
        permissions=("fs.read",),
        effect=EffectType.read,
        timeout_seconds=15,
        idempotent=True,
        requires_approval=False,
        arg_types={"path": "string"},
    ),
    "fs.list": ToolSpec(
        name="fs.list",
        version="1",
        arg_schema={"type": "object", "required": ["path"], "properties": {"path": {"type": "string"}}},
        result_schema={"type": "object", "required": ["entries"]},
        permissions=("fs.read",),
        effect=EffectType.read,
        timeout_seconds=15,
        idempotent=True,
        requires_approval=False,
        arg_types={"path": "string"},
    ),
    "fs.write": ToolSpec(
        name="fs.write",
        version="1",
        arg_schema={
            "type": "object",
            "required": ["path", "content"],
            "properties": {"path": {"type": "string"}, "content": {}},
        },
        result_schema={"type": "object", "required": ["path", "bytes_written"]},
        permissions=("fs.write",),
        effect=EffectType.reversible_write,
        timeout_seconds=15,
        idempotent=True,
        requires_approval=False,
        arg_types={"path": "string", "content": "any"},
    ),
    "json.parse": ToolSpec(
        name="json.parse",
        version="1",
        arg_schema={"type": "object", "required": ["text"], "properties": {"text": {"type": "string"}}},
        result_schema={"type": "object", "required": ["value"]},
        permissions=("json.parse",),
        effect=EffectType.read,
        timeout_seconds=10,
        idempotent=True,
        requires_approval=False,
        arg_types={"text": "string"},
    ),
    "data.transform": ToolSpec(
        name="data.transform",
        version="1",
        arg_schema={"type": "object", "required": ["op"], "properties": {"op": {"type": "string"}}},
        result_schema={"type": "object", "required": ["value"]},
        permissions=("data.transform",),
        effect=EffectType.read,
        timeout_seconds=10,
        idempotent=True,
        requires_approval=False,
        arg_types={"op": "string", "value": "any", "fields": "any", "field": "string", "set": "any"},
    ),
    "verify.run": ToolSpec(
        name="verify.run",
        version="1",
        arg_schema={"type": "object", "required": ["check"], "properties": {"check": {"type": "string"}}},
        result_schema={"type": "object", "required": ["passed", "evidence"]},
        permissions=("verify.run",),
        effect=EffectType.read,
        timeout_seconds=15,
        idempotent=True,
        requires_approval=False,
        arg_types={"check": "string"},
    ),
}


TRANSFORM_OPS = frozenset({"identity", "pick_fields", "set_field", "merge", "passthrough_unverified"})
