"""Prompt routing across the command and tool inventories.

The baseline scores every prompt against every module (O(prompts x modules x
tokens)). This module instead:

* Builds a **pre-computed inverted token index** mapping each corpus token to the
  modules that contain it (``_build_routing_index``), so a prompt only ever
  touches modules that share at least one token.
* **Memoises** both per-token expansion (``_resolve_token``) and whole-prompt
  routing (``_route_cached``); repeated prompts become a single dict hit.
* Selects the top ``limit`` matches, guaranteeing at least one command and one
  tool when available, then ranking the rest by score.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from .models import PermissionDenial
from .registry import command_registry, tool_registry
from .text import tokenize_cached


@dataclass(frozen=True, slots=True)
class RoutedMatch:
    kind: str
    name: str
    source_hint: str
    score: int


@lru_cache(maxsize=1)
def _build_routing_index() -> dict[str, frozenset[tuple[str, int]]]:
    """token -> frozenset of (kind, module_index)."""
    raw: dict[str, set[tuple[str, int]]] = {}
    for kind, reg in (("command", command_registry()), ("tool", tool_registry())):
        for idx, module in enumerate(reg):
            for token in tokenize_cached(module.search_text):
                raw.setdefault(token, set()).add((kind, idx))
    return {token: frozenset(entries) for token, entries in raw.items()}


@lru_cache(maxsize=2048)
def _resolve_token(token: str) -> frozenset[tuple[str, int]]:
    """Expand a query token to matching modules, including substring matches.

    This preserves the baseline's ``token in haystack`` substring semantics while
    keeping the cost amortised: the answer for each distinct token is cached.
    """
    index = _build_routing_index()
    direct = index.get(token)
    result: set[tuple[str, int]] = set(direct) if direct else set()
    for key, entries in index.items():
        if key is not token and token in key:
            result.update(entries)
    return frozenset(result)


@lru_cache(maxsize=4096)
def _route_cached(prompt: str, limit: int) -> tuple[RoutedMatch, ...]:
    tokens = tokenize_cached(prompt)
    registries = {"command": command_registry(), "tool": tool_registry()}

    score_map: dict[tuple[str, int], int] = {}
    for token in tokens:
        for entry in _resolve_token(token):
            score_map[entry] = score_map.get(entry, 0) + 1

    # Group matches by kind, each ranked by (-score, name).
    by_kind: dict[str, list[RoutedMatch]] = {"command": [], "tool": []}
    for (kind, idx), score in score_map.items():
        module = registries[kind].modules[idx]
        by_kind[kind].append(
            RoutedMatch(kind=kind, name=module.name, source_hint=module.source_hint, score=score)
        )
    for group in by_kind.values():
        group.sort(key=lambda m: (-m.score, m.name))

    # Header: the best command, then the best tool (kind order, when present).
    selected: list[RoutedMatch] = []
    for kind in ("command", "tool"):
        if by_kind[kind]:
            selected.append(by_kind[kind].pop(0))

    # Remainder ranked by (-score, kind, name) — 'command' sorts before 'tool'.
    leftovers = sorted(
        (m for group in by_kind.values() for m in group),
        key=lambda m: (-m.score, m.kind, m.name),
    )
    selected.extend(leftovers[: max(0, limit - len(selected))])
    return tuple(selected[:limit])


class PortRuntime:
    """High-level façade tying routing, execution and the query engine together."""

    def route_prompt(self, prompt: str, limit: int = 5) -> list[RoutedMatch]:
        return list(_route_cached(prompt, limit))

    def bootstrap_session(self, prompt: str, limit: int = 5):
        # Imported lazily to avoid a heavy import graph for pure routing callers.
        from .runtime import bootstrap_session

        return bootstrap_session(self, prompt, limit)

    def run_turn_loop(
        self, prompt: str, limit: int = 5, max_turns: int = 3, structured_output: bool = False
    ):
        from .runtime import run_turn_loop

        return run_turn_loop(self, prompt, limit, max_turns, structured_output)

    @staticmethod
    def infer_permission_denials(matches: list[RoutedMatch]) -> list[PermissionDenial]:
        return [
            PermissionDenial(
                tool_name=m.name,
                reason="destructive shell execution remains gated in the Python port",
            )
            for m in matches
            if m.kind == "tool" and "bash" in m.name.lower()
        ]
