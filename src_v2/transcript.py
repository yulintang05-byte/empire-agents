"""[OPT-2] Front-trimming list transcript: `del entries[:overflow]` beats
v1's `entries[:] = entries[-keep:]` because it skips the intermediate slice
allocation and operates fully in C inside list_ass_slice."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class TranscriptStore:
    _entries: list[str] = field(default_factory=list)
    flushed: bool = False

    @property
    def entries(self) -> list[str]:
        return self._entries

    def append(self, entry: str) -> None:
        self._entries.append(entry)
        self.flushed = False

    def compact(self, keep_last: int = 10) -> None:
        overflow = len(self._entries) - keep_last
        if overflow > 0:
            del self._entries[:overflow]

    def replay(self) -> tuple[str, ...]:
        return tuple(self._entries)

    def flush(self) -> None:
        self.flushed = True

    def __len__(self) -> int:
        return len(self._entries)
