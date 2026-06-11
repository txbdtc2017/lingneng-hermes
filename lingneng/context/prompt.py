from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field

TRUSTED_RUNTIME_CONTEXT_HEADING = "## LingNeng Trusted Runtime Context"
UNTRUSTED_REQUEST_CONTEXT_HEADING = (
    "## LingNeng Request-Scoped Untrusted Context"
)
TOOL_DERIVED_PUBLIC_GUIDANCE_HEADING = "## LingNeng Tool-Derived Public Guidance"

__all__ = [
    "PromptSection",
    "TOOL_DERIVED_PUBLIC_GUIDANCE_HEADING",
    "TRUSTED_RUNTIME_CONTEXT_HEADING",
    "UNTRUSTED_REQUEST_CONTEXT_HEADING",
    "compose_lingneng_ephemeral_prompt",
]


class PromptSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    heading: str
    body: str = ""
    max_chars: int = Field(default=8000, ge=100)

    def to_prompt_text(self) -> str:
        body = self.body.strip()
        if not body:
            return ""
        safe_body = _demote_body_headings(body)
        return _bounded_text(f"{self.heading}\n\n{safe_body}", max_chars=self.max_chars)


def compose_lingneng_ephemeral_prompt(
    *,
    trusted_runtime_context: str = "",
    untrusted_request_context: str = "",
    tool_public_guidance: str = "",
    max_section_chars: int,
) -> str:
    section_inputs = [
        (TRUSTED_RUNTIME_CONTEXT_HEADING, trusted_runtime_context),
        (UNTRUSTED_REQUEST_CONTEXT_HEADING, untrusted_request_context),
        (TOOL_DERIVED_PUBLIC_GUIDANCE_HEADING, tool_public_guidance),
    ]
    return "\n\n".join(
        section_text
        for section_text in (
            PromptSection(
                heading=heading,
                body=body,
                max_chars=max_section_chars,
            ).to_prompt_text()
            for heading, body in section_inputs
            if body.strip()
        )
        if section_text
    )


def _bounded_text(text: str, *, max_chars: int) -> str:
    if max_chars <= 0:
        return ""

    stripped = text.strip()
    if len(stripped) <= max_chars:
        return stripped

    marker = "\n...[truncated]"
    if max_chars <= len(marker):
        return marker[-max_chars:]

    return stripped[: max_chars - len(marker)].rstrip() + marker


_MARKDOWN_HEADING_RE = re.compile(r"^(?P<indent>[ \t]{0,3})#{1,6}[ \t]+(?P<title>.+)$")


def _demote_body_headings(body: str) -> str:
    lines = []
    for line in body.splitlines():
        match = _MARKDOWN_HEADING_RE.match(line)
        if match is None:
            lines.append(line)
            continue
        title = match.group("title").strip()
        lines.append(f"{match.group('indent')}- Body heading: {title}")
    return "\n".join(lines)
