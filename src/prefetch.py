from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class PrefetchResult:
    plugin_tools: list[str] = field(default_factory=list)
    mcp_servers: list[str] = field(default_factory=list)
    skill_tools: list[str] = field(default_factory=list)

    def as_markdown(self) -> str:
        lines = ['## Prefetch Results']
        lines.append(f'- Plugin tools: {len(self.plugin_tools)}')
        lines.append(f'- MCP servers: {len(self.mcp_servers)}')
        lines.append(f'- Skill tools: {len(self.skill_tools)}')
        return '\n'.join(lines)
