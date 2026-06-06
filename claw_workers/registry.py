"""Unified, indexed registry for mirrored commands and tools.

A single generic :class:`Registry` powers both inventories, eliminating the
duplicated linear-scan code in the baseline. It provides:

* **O(1) name lookup** via a ``dict`` index.
* **Trigram-accelerated substring search** that narrows candidates before doing
  any string comparison, and reuses each module's *precomputed* ``search_text``
  (the baseline rebuilds and lower-cases that corpus on every single query).
* **A fast no-filter path** for ``all()``-style listing.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Iterator

from .models import PortingModule
from .permissions import ToolPermissionContext
from .text import trigrams

_DATA_DIR = Path(__file__).resolve().parent / "reference_data"
_COMMANDS_SNAPSHOT = _DATA_DIR / "commands_snapshot.json"
_TOOLS_SNAPSHOT = _DATA_DIR / "tools_snapshot.json"

_SIMPLE_TOOL_NAMES = frozenset(
    {"BashTool", "FileEditTool", "FileReadTool", "FileWriteTool", "GlobTool", "GrepTool"}
)


def _load_modules(path: Path, category: str) -> tuple[PortingModule, ...]:
    raw = json.loads(path.read_text())
    return tuple(
        PortingModule.create(
            name=entry["name"],
            source_hint=entry["source"],
            responsibility=f"{entry['type']} {category}: {entry['name']}",
            kind=category,
        )
        for entry in raw
    )


class Registry:
    """An indexed collection of :class:`PortingModule` entries."""

    __slots__ = ("label", "_modules", "_by_name", "_trigram")

    def __init__(self, modules: Iterable[PortingModule], *, label: str) -> None:
        self.label = label
        self._modules: tuple[PortingModule, ...] = tuple(modules)
        self._by_name: dict[str, PortingModule] = {m.name: m for m in self._modules}
        self._trigram: dict[str, frozenset[int]] = self._build_trigram_index()

    # -- construction -----------------------------------------------------
    def _build_trigram_index(self) -> dict[str, frozenset[int]]:
        raw: dict[str, set[int]] = {}
        for idx, module in enumerate(self._modules):
            for tri in trigrams(module.search_text):
                raw.setdefault(tri, set()).add(idx)
        return {tri: frozenset(ids) for tri, ids in raw.items()}

    # -- container protocol ----------------------------------------------
    def __len__(self) -> int:
        return len(self._modules)

    def __iter__(self) -> Iterator[PortingModule]:
        return iter(self._modules)

    @property
    def modules(self) -> tuple[PortingModule, ...]:
        return self._modules

    def names(self) -> tuple[str, ...]:
        return tuple(m.name for m in self._modules)

    # -- lookup -----------------------------------------------------------
    def get(self, name: str) -> PortingModule | None:
        """O(1) exact-name lookup."""
        return self._by_name.get(name)

    def find(self, query: str, limit: int = 10) -> tuple[PortingModule, ...]:
        """Return up to ``limit`` modules whose corpus contains ``query``.

        Results preserve registry (load) order, matching the naive scan exactly
        but reaching the answer through a trigram candidate set.
        """
        q = query.lower()
        if not q:
            return ()
        if len(q) < 3:
            return self._linear_find(q, limit)

        # Intersect the candidate sets of every query trigram.
        candidates: frozenset[int] | None = None
        for tri in trigrams(q):
            ids = self._trigram.get(tri)
            if not ids:
                return ()  # a trigram absent everywhere => no match possible
            candidates = ids if candidates is None else (candidates & ids)
            if not candidates:
                return ()
        if not candidates:
            return ()

        matches: list[PortingModule] = []
        for idx in sorted(candidates):
            module = self._modules[idx]
            if q in module.search_text:
                matches.append(module)
                if len(matches) >= limit:
                    break
        return tuple(matches)

    def _linear_find(self, q: str, limit: int) -> tuple[PortingModule, ...]:
        matches: list[PortingModule] = []
        for module in self._modules:
            if q in module.search_text:
                matches.append(module)
                if len(matches) >= limit:
                    break
        return tuple(matches)

    def render_index(self, limit: int = 20, query: str = "") -> str:
        matches = self.find(query, limit=limit) if query else self._modules[:limit]
        lines = [f"{self.label} index ({len(matches)} shown):", ""]
        lines.extend(f"- {m.name} — {m.source_hint}" for m in matches)
        return "\n".join(lines)


# -- module-level singletons (built once, reused everywhere) --------------
@lru_cache(maxsize=1)
def command_registry() -> Registry:
    return Registry(_load_modules(_COMMANDS_SNAPSHOT, "command"), label="Command")


@lru_cache(maxsize=1)
def tool_registry() -> Registry:
    return Registry(_load_modules(_TOOLS_SNAPSHOT, "tool"), label="Tool")


# -- convenience facade (stable public API) -------------------------------
def get_command(name: str) -> PortingModule | None:
    return command_registry().get(name)


def get_tool(name: str) -> PortingModule | None:
    return tool_registry().get(name)


def find_commands(query: str, limit: int = 10) -> tuple[PortingModule, ...]:
    return command_registry().find(query, limit=limit)


def find_tools(query: str, limit: int = 10) -> tuple[PortingModule, ...]:
    return tool_registry().find(query, limit=limit)


def command_names() -> tuple[str, ...]:
    return command_registry().names()


def tool_names() -> tuple[str, ...]:
    return tool_registry().names()


def get_commands(
    include_plugin_commands: bool = True, include_skill_commands: bool = True
) -> tuple[PortingModule, ...]:
    reg = command_registry()
    if include_plugin_commands and include_skill_commands:
        return reg.modules  # fast path: no allocation, no scan
    result = []
    for m in reg:
        if not include_plugin_commands and m.search_text.startswith("plugin"):
            continue
        if not include_skill_commands and m.search_text.startswith("skill"):
            continue
        result.append(m)
    return tuple(result)


def get_tools(
    simple_mode: bool = False,
    include_mcp: bool = True,
    permission_context: ToolPermissionContext | None = None,
) -> tuple[PortingModule, ...]:
    reg = tool_registry()
    if not simple_mode and include_mcp and permission_context is None:
        return reg.modules  # fast path
    result = []
    for m in reg:
        if simple_mode and m.name not in _SIMPLE_TOOL_NAMES:
            continue
        if not include_mcp and "mcp" in m.source_hint.lower():
            continue
        if permission_context is not None and permission_context.blocks(m.name):
            continue
        result.append(m)
    return tuple(result)
