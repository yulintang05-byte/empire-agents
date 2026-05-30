from __future__ import annotations
from dataclasses import dataclass, field
from .tools import PORTED_TOOLS


@dataclass
class ToolPool:
    tool_names: list[str] = field(default_factory=list)
    denied_tools: list[str] = field(default_factory=list)
    mcp_tools: list[str] = field(default_factory=list)

    def as_markdown(self) -> str:
        lines = ['# Tool Pool', '']
        lines.append(f'Available: {len(self.tool_names)}')
        lines.append(f'Denied: {len(self.denied_tools)}')
        lines.append(f'MCP: {len(self.mcp_tools)}')
        if self.tool_names:
            lines.append('')
            lines.extend(f'- {name}' for name in self.tool_names[:20])
        return '\n'.join(lines)


def assemble_tool_pool() -> ToolPool:
    return ToolPool(
        tool_names=[t.name for t in PORTED_TOOLS],
        denied_tools=[],
        mcp_tools=[t.name for t in PORTED_TOOLS if 'mcp' in t.source_hint.lower()],
    )
