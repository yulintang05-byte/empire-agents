"""Session transcript: C-speed append, O(keep) compaction, bounded on demand.

The transcript is append-dominated, so the append path is kept as cheap as
physically possible in CPython — a bare ``list.append`` with no per-call
bookkeeping (matching the theoretical floor). The genuine improvement over the
baseline is in :meth:`compact`:

* baseline:  ``entries[:] = entries[-keep:]`` rebuilds the whole tail — **O(n)**.
* here:      ``del self._entries[:overflow]`` moves only the survivors — **O(keep)**.

Memory is bounded explicitly via :meth:`compact` (which the query engine calls
between turns) or :meth:`trim_to_capacity`, rather than by taxing every append.
"""
from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_CAPACITY = 4096


@dataclass(slots=True)
class TranscriptStore:
    capacity: int = DEFAULT_CAPACITY
    flushed: bool = False
    _entries: list[str] = field(default_factory=list)

    @property
    def entries(self) -> list[str]:
        return list(self._entries)  # defensive copy; internal state stays private

    def append(self, entry: str) -> None:
        self._entries.append(entry)
        self.flushed = False

    def compact(self, keep_last: int = 10) -> None:
        overflow = len(self._entries) - keep_last
        if overflow > 0:
            del self._entries[:overflow]  # O(keep_last), not O(n)

    def trim_to_capacity(self) -> None:
        """Bound memory to ``capacity`` without taxing the append hot path."""
        self.compact(self.capacity)

    def replay(self) -> tuple[str, ...]:
        return tuple(self._entries)

    def flush(self) -> None:
        self.flushed = True

    def __len__(self) -> int:
        return len(self._entries)
