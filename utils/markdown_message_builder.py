from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable


@dataclass
class MarkdownSection:
    heading: str | None
    lines: list[str]


class MarkdownMessageBuilder:
    """Simple markdown builder for bot-generated text attachments."""

    def __init__(self, title: str):
        self.title = title
        self._sections: list[MarkdownSection] = []

    def add_section(self, heading: str | None = None, lines: Iterable[str] | None = None) -> "MarkdownMessageBuilder":
        section_lines = [str(line) for line in (lines or [])]
        self._sections.append(MarkdownSection(heading=heading, lines=section_lines))
        return self

    def add_paragraph(self, text: str) -> "MarkdownMessageBuilder":
        return self.add_section(lines=[text])

    def add_numbered_list(self, items: Iterable[str], heading: str | None = None) -> "MarkdownMessageBuilder":
        lines = [f"{index}. {item}" for index, item in enumerate(items, start=1)]
        return self.add_section(heading=heading, lines=lines)

    def build(self) -> str:
        output: list[str] = [f"# {self.title}"]

        for section in self._sections:
            output.append("")
            if section.heading:
                output.append(f"## {section.heading}")
                output.append("")
            output.extend(section.lines)

        return "\n".join(output).rstrip() + "\n"

    def write_temp_file(self, *, prefix: str, username: str | None = None, temp_dir: str = "temp") -> str:
        os.makedirs(temp_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_username = _safe_slug(username or "user")
        file_prefix = f"{_safe_slug(prefix)}_{safe_username}_{stamp}_"

        fd, path = tempfile.mkstemp(prefix=file_prefix, suffix=".md", dir=temp_dir)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(self.build())

        return path


def _safe_slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value).strip())
    return cleaned.strip("_") or "item"
