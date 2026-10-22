from __future__ import annotations

import hashlib
import re
from typing import Any

import yaml

from skillvm.diag import Diagnostic, Severity, d

FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.S)
STEP = re.compile(r"^\s*(\d+)\.\s+(.*)$")


class ParsedSkill:
    def __init__(
        self,
        source: str,
        meta: dict[str, Any],
        body: str,
        steps: list[tuple[int, int, str]],
        content_hash: str,
        diagnostics: list[Diagnostic],
    ):
        self.source = source
        self.meta = meta
        self.body = body
        self.steps = steps  # (num, line, text)
        self.content_hash = content_hash
        self.diagnostics = diagnostics


def parse_skill(source: str) -> ParsedSkill:
    diags: list[Diagnostic] = []
    m = FRONTMATTER.match(source)
    if not m:
        diags.append(
            d("SV1001", "Skill must start with YAML frontmatter delimited by ---", suggestion="Add --- id: my-skill ---")
        )
        return ParsedSkill(source, {}, source, [], hashlib.sha256(source.encode()).hexdigest(), diags)
    raw_yaml, body = m.group(1), m.group(2)
    try:
        meta = yaml.safe_load(raw_yaml) or {}
        if not isinstance(meta, dict):
            raise ValueError("frontmatter is not a mapping")
    except Exception as e:
        diags.append(d("SV1001", f"Invalid YAML frontmatter: {e}"))
        return ParsedSkill(source, {}, body, [], hashlib.sha256(source.encode()).hexdigest(), diags)

    steps: list[tuple[int, int, str]] = []
    preamble_len = source[: m.start(2)].count("\n") + 1
    for i, line in enumerate(body.splitlines(), start=preamble_len):
        sm = STEP.match(line)
        if sm:
            steps.append((int(sm.group(1)), i, sm.group(2).strip()))

    sid = str(meta.get("id") or "").strip()
    if not sid:
        diags.append(d("SV1002", "Frontmatter id is required and must be non-empty", suggestion="Set id: my-skill"))

    h = hashlib.sha256(source.encode("utf-8")).hexdigest()
    return ParsedSkill(source, meta, body, steps, h, diags)
