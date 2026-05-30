from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class DeferredInitResult:
    trusted: bool = False
    plugin_init: list[str] = field(default_factory=list)
    skill_init: list[str] = field(default_factory=list)
    mcp_prefetch: list[str] = field(default_factory=list)
    session_hooks: list[str] = field(default_factory=list)

    def as_markdown(self) -> str:
        lines = [
            '## Deferred Init',
            f'- Trusted: {self.trusted}',
            f'- Plugin init: {len(self.plugin_init)}',
            f'- Skill init: {len(self.skill_init)}',
            f'- MCP prefetch: {len(self.mcp_prefetch)}',
            f'- Session hooks: {len(self.session_hooks)}',
        ]
        return '\n'.join(lines)
