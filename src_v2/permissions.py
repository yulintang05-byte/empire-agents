from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class ToolPermissionContext:
    denied_tool_names: frozenset[str] = field(default_factory=frozenset)
    denied_prefixes: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def from_iterables(cls, names, prefixes) -> 'ToolPermissionContext':
        return cls(
            denied_tool_names=frozenset(names),
            denied_prefixes=frozenset(prefixes),
        )

    def blocks(self, tool_name: str) -> bool:
        if tool_name in self.denied_tool_names:
            return True
        return any(tool_name.startswith(prefix) for prefix in self.denied_prefixes)
