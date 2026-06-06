"""Tool permission gating."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True, slots=True)
class ToolPermissionContext:
    """Blocks tools by exact name or by name prefix.

    Both collections are frozensets so :meth:`blocks` does an O(1) membership
    test on the common (exact-name) path before falling back to prefix scanning.
    """

    denied_tool_names: frozenset[str] = field(default_factory=frozenset)
    denied_prefixes: tuple[str, ...] = ()

    @classmethod
    def from_iterables(
        cls, names: Iterable[str], prefixes: Iterable[str]
    ) -> "ToolPermissionContext":
        return cls(
            denied_tool_names=frozenset(names),
            denied_prefixes=tuple(prefixes),
        )

    def blocks(self, tool_name: str) -> bool:
        if tool_name in self.denied_tool_names:
            return True
        return any(tool_name.startswith(p) for p in self.denied_prefixes)
