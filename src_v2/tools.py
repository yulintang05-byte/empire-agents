from __future__ import annotations
import json
from functools import lru_cache
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


# [OPT-3] Dict-indexed O(1) lookup
@lru_cache(maxsize=1)
def _tool_index() -> dict[str, PortingModule]:
    return {m.name: m for m in PORTED_TOOLS}


# [OPT-4] Trigram inverted index for fast substring search
@lru_cache(maxsize=1)
def _tool_trigram_index() -> dict[str, set[int]]:
    index: dict[str, set[int]] = {}
    for i, m in enumerate(PORTED_TOOLS):
        text = f'{m.name} {m.source_hint} {m.responsibility}'.lower()
        for start in range(len(text) - 2):
            trigram = text[start:start + 3]
            if trigram not in index:
                index[trigram] = set()
            index[trigram].add(i)
    return index


def get_tool(name: str) -> PortingModule | None:
    return _tool_index().get(name)


def get_tools(simple_mode: bool = False, include_mcp: bool = True,
              permission_context: ToolPermissionContext | None = None) -> tuple[PortingModule, ...]:
    if not simple_mode and include_mcp and permission_context is None:
        return PORTED_TOOLS
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
    if len(query_lower) >= 3:
        trigram_idx = _tool_trigram_index()
        trigrams = [query_lower[i:i + 3] for i in range(len(query_lower) - 2)]
        candidate_sets = [trigram_idx.get(tri, set()) for tri in trigrams]
        if candidate_sets:
            candidates = candidate_sets[0]
            for s in candidate_sets[1:]:
                candidates = candidates & s
            matches = []
            for idx in sorted(candidates):
                m = PORTED_TOOLS[idx]
                text = f'{m.name} {m.source_hint} {m.responsibility}'.lower()
                if query_lower in text:
                    matches.append(m)
                    if len(matches) >= limit:
                        break
            return tuple(matches)
    matches = []
    for m in PORTED_TOOLS:
        text = f'{m.name} {m.source_hint} {m.responsibility}'.lower()
        if query_lower in text:
            matches.append(m)
            if len(matches) >= limit:
                break
    return tuple(matches)


def render_tool_index(limit: int = 20, query: str = '') -> str:
    if query:
        matches = find_tools(query, limit=limit)
    else:
        matches = PORTED_TOOLS[:limit]
    lines = [f'Tool index ({len(matches)} shown):', '']
    lines.extend(f'- {m.name} — {m.source_hint}' for m in matches)
    return '\n'.join(lines)


class ToolResult:
    __slots__ = ('handled', 'message')

    def __init__(self, handled: bool, message: str):
        self.handled = handled
        self.message = message


def execute_tool(name: str, payload: str) -> ToolResult:
    tool = get_tool(name)
    if tool is None:
        return ToolResult(handled=False, message=f'Unknown tool: {name}')
    return ToolResult(handled=True, message=f'[{tool.name}] executed with payload: {payload}')
