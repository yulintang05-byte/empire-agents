from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class CommandGraphSegment:
    name: str
    entry_count: int
    description: str


@dataclass
class CommandGraph:
    segments: list[CommandGraphSegment] = field(default_factory=list)

    def as_markdown(self) -> str:
        lines = ['# Command Graph Segmentation', '']
        for segment in self.segments:
            lines.append(f'## {segment.name} ({segment.entry_count} entries)')
            lines.append(segment.description)
            lines.append('')
        return '\n'.join(lines)


def build_command_graph() -> CommandGraph:
    return CommandGraph(segments=[
        CommandGraphSegment('core', 12, 'Core shell commands (help, commit, review, etc.)'),
        CommandGraphSegment('plugin', 45, 'Plugin-contributed commands registered at startup'),
        CommandGraphSegment('skill', 51, 'Skill-contributed commands loaded on demand'),
    ])
