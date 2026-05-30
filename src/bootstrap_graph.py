from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class BootstrapGraph:
    stages: list[str] = field(default_factory=list)

    def as_markdown(self) -> str:
        lines = ['# Bootstrap Graph', '']
        for i, stage in enumerate(self.stages, 1):
            lines.append(f'{i}. {stage}')
        return '\n'.join(lines)


def build_bootstrap_graph() -> BootstrapGraph:
    return BootstrapGraph(stages=[
        'Load workspace context',
        'Build port manifest',
        'Initialize execution registry',
        'Prefetch plugin/MCP/skill tools',
        'Build routing index',
        'Ready for prompts',
    ])
