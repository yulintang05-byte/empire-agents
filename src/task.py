from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class PortingTask:
    title: str
    description: str
    priority: int = 0
    subtasks: list[str] = field(default_factory=list)
    completed: bool = False

    def mark_complete(self) -> None:
        self.completed = True

    def as_markdown(self) -> str:
        status = 'done' if self.completed else 'pending'
        lines = [f'## {self.title} [{status}]', '', self.description]
        if self.subtasks:
            lines.append('')
            lines.extend(f'- {sub}' for sub in self.subtasks)
        return '\n'.join(lines)
