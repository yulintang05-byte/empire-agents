"""Structured event log for a runtime session."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class HistoryLog:
    events: list[tuple[str, str]] = field(default_factory=list)

    def add(self, kind: str, detail: str) -> None:
        self.events.append((kind, detail))

    def as_markdown(self) -> str:
        lines = ["## History"]
        lines.extend(f"- **{kind}**: {detail}" for kind, detail in self.events)
        return "\n".join(lines)
