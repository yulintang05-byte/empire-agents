from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class HistoryLog:
    events: list[tuple[str, str]] = field(default_factory=list)

    def add(self, kind: str, detail: str) -> None:
        self.events.append((kind, detail))

    def as_markdown(self) -> str:
        lines = ['## History']
        for kind, detail in self.events:
            lines.append(f'- **{kind}**: {detail}')
        return '\n'.join(lines)
