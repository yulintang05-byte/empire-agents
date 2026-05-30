from __future__ import annotations
import json
from pathlib import Path
from .models import PortingModule
from .permissions import ToolPermissionContext

_SNAPSHOT = Path(__file__).resolve().parent / 'reference_data' / 'tools_snapshot.json'

def _load_tools() -> tuple[PortingModule, ...]:
    raw = json.loads(_SNAPSHOT.read_text())
    return tuple(
        PortingModule(
            name=entry['name'],
            source_hint=entry['source'],
            responsibility=f"{entry['type']} tool: {entry['name']}",
        )
        for entry in raw
    )

PORTED_TOOLS: tuple[PortingModule, ...] = _load_tools()

_SIMPLE_TOOL_NAMES = frozenset({
    'BashTool', 'FileEditTool', 'FileReadTool', 'FileWriteTool',
    'GlobTool', 'GrepTool',
})

def get_tool(name: str) -> PortingModule | None:
    for m in PORTED_TOOLS:
        if m.name == name:
            return m
    return None

def get_tools(simple_mode: bool = False, include_mcp: bool = True,
              permission_context: ToolPermissionContext | None = None) -> tuple[PortingModule, ...]:
    result = []
    for m in PORTED_TOOLS:
        if simple_mode and m.name not in _SIMPLE_TOOL_NAMES:
            continue
        if not include_mcp and 'mcp' in m.source_hint.lower():
            continue
        if permission_context and permission_context.blocks(m.name):
            continue
        result.append(m)
    return tuple(result)

def find_tools(query: str, limit: int = 10) -> tuple[PortingModule, ...]:
    query_lower = query.lower()
    matches = []
    for m in PORTED_TOOLS:
        text = f'{m.name} {m.source_hint} {m.responsibility}'.lower()
        if query_lower in text:
            matches.append(m)
    return tuple(matches[:limit])

def render_tool_index(limit: int = 20, query: str = '') -> str:
    if query:
        matches = find_tools(query, limit=limit)
    else:
        matches = PORTED_TOOLS[:limit]
    lines = [f'Tool index ({len(matches)} shown):', '']
    lines.extend(f'- {m.name} — {m.source_hint}' for m in matches)
    return '\n'.join(lines)

class ToolResult:
    def __init__(self, handled: bool, message: str):
        self.handled = handled
        self.message = message

def execute_tool(name: str, payload: str) -> ToolResult:
    tool = get_tool(name)
    if tool is None:
        return ToolResult(handled=False, message=f'Unknown tool: {name}')
    return ToolResult(handled=True, message=f'[{tool.name}] executed with payload: {payload}')
