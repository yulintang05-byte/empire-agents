"""Core data models for the claw-code workers port.

Every value type here is a frozen, ``__slots__``-backed dataclass: immutability
makes them hashable (so they can live in sets / be cached) and ``__slots__``
removes the per-instance ``__dict__`` for a smaller, faster object.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .text import normalize


@dataclass(frozen=True, slots=True)
class Subsystem:
    """A top-level module or directory in the workspace manifest."""

    name: str
    file_count: int
    notes: str


@dataclass(frozen=True, slots=True)
class PortingModule:
    """A mirrored command or tool entry.

    ``search_text`` is the pre-lowercased ``"name source_hint responsibility"``
    corpus. Precomputing it once at load time is the single biggest search-path
    win over the baseline, which rebuilds this f-string and calls ``.lower()``
    on *every* query.
    """

    name: str
    source_hint: str
    responsibility: str
    kind: str = "module"
    search_text: str = ""

    @classmethod
    def create(
        cls, name: str, source_hint: str, responsibility: str, kind: str = "module"
    ) -> "PortingModule":
        corpus = normalize(f"{name} {source_hint} {responsibility}")
        return cls(
            name=name,
            source_hint=source_hint,
            responsibility=responsibility,
            kind=kind,
            search_text=corpus,
        )


@dataclass(frozen=True, slots=True)
class PermissionDenial:
    tool_name: str
    reason: str


@dataclass(frozen=True, slots=True)
class UsageSummary:
    """Token accounting using a fast byte-length estimate (~4 bytes/token)."""

    input_tokens: int
    output_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def add_turn(self, prompt: str, output: str) -> "UsageSummary":
        # ``(len(s) + 3) >> 2`` == ceil(len/4) without float math.
        return UsageSummary(
            input_tokens=self.input_tokens + ((len(prompt) + 3) >> 2),
            output_tokens=self.output_tokens + ((len(output) + 3) >> 2),
        )


@dataclass(slots=True)
class PortingBacklog:
    items: list[str] = field(default_factory=list)

    def add(self, item: str) -> None:
        self.items.append(item)

    def summary(self) -> str:
        if not self.items:
            return "Backlog empty."
        return f"{len(self.items)} items pending: " + ", ".join(self.items[:5])
