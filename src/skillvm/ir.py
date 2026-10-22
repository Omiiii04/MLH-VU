from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from skillvm import COMPILER_VERSION, IR_SCHEMA_VERSION
from skillvm.diag import CompileStatus, Diagnostic


class EffectType(str, Enum):
    read = "read"
    reversible_write = "reversible_write"
    irreversible = "irreversible"
    external = "external"


class NodeType(str, Enum):
    input = "input"
    tool = "tool"
    transform = "transform"
    llm = "llm"
    condition = "condition"
    approval = "approval"
    verify = "verify"
    output = "output"


class SourceMap(BaseModel):
    line_start: int | None = None
    line_end: int | None = None
    excerpt: str | None = None


class NodeBase(BaseModel):
    id: str
    depends_on: list[str] = Field(default_factory=list)
    source: SourceMap | None = None
    timeout_seconds: float = 30
    fallback: bool = False


class InputNode(NodeBase):
    type: Literal["input"] = "input"
    name: str
    value_type: str = "string"


class ToolNode(NodeBase):
    type: Literal["tool"] = "tool"
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    effect: EffectType
    idempotent: bool = False
    permissions: list[str] = Field(default_factory=list)


class TransformNode(NodeBase):
    type: Literal["transform"] = "transform"
    op: str
    args: dict[str, Any] = Field(default_factory=dict)


class LlmNode(NodeBase):
    type: Literal["llm"] = "llm"
    prompt: str
    output_schema: dict[str, Any]
    verify_node: str


class ConditionNode(NodeBase):
    type: Literal["condition"] = "condition"
    predicate: Literal["truthy", "equals", "exists"]
    left: Any = None
    right: Any = None
    skip_if_false: list[str] = Field(default_factory=list)


class ApprovalNode(NodeBase):
    type: Literal["approval"] = "approval"
    reason: str
    effect: EffectType


class VerifyNode(NodeBase):
    type: Literal["verify"] = "verify"
    check: str
    args: dict[str, Any] = Field(default_factory=dict)
    required: bool = True


class OutputNode(NodeBase):
    type: Literal["output"] = "output"
    name: str
    from_node: str
    path: str = "$"


Node = Annotated[
    InputNode
    | ToolNode
    | TransformNode
    | LlmNode
    | ConditionNode
    | ApprovalNode
    | VerifyNode
    | OutputNode,
    Field(discriminator="type"),
]


class Edge(BaseModel):
    src: str
    dst: str


class TypedField(BaseModel):
    name: str
    type: str
    required: bool = True


class WorkflowIR(BaseModel):
    schema_version: str = IR_SCHEMA_VERSION
    skill_id: str
    content_hash: str
    compiler_version: str = COMPILER_VERSION
    provider: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    constrained_mode: str = "deterministic"
    compiled_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    inputs: list[TypedField] = Field(default_factory=list)
    outputs: list[TypedField] = Field(default_factory=list)
    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    fallback_steps: int = 0
    total_steps: int = 0

    def node_map(self) -> dict[str, Node]:
        return {n.id: n for n in self.nodes}


class CompileResult(BaseModel):
    status: CompileStatus
    ir: WorkflowIR | None = None
    diagnostics: list[Diagnostic] = Field(default_factory=list)
    fallback_steps: int = 0
    total_steps: int = 0
    executable: bool = False


# Re-export for tests that import CompileStatus from ir
CompileStatus = CompileStatus
