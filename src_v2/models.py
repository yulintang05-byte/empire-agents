from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Subsystem:
    name: str
    file_count: int
    notes: str


@dataclass(frozen=True, slots=True)
class PortingModule:
    name: str
    source_hint: str
    responsibility: str


@dataclass(frozen=True, slots=True)
class PermissionDenial:
    tool_name: str
    reason: str


@dataclass(frozen=True, slots=True)
class UsageSummary:
    input_tokens: int
    output_tokens: int

    def add_turn(self, prompt: str, output: str) -> 'UsageSummary':
        # [OPT-1] Byte-length estimation: ~4 bytes per token, bit-shift for speed
        return UsageSummary(
            input_tokens=self.input_tokens + ((len(prompt) + 3) >> 2),
            output_tokens=self.output_tokens + ((len(output) + 3) >> 2),
        )


@dataclass
class PortingBacklog:
    items: list[str] = field(default_factory=list)

    def add(self, item: str) -> None:
        self.items.append(item)

    def summary(self) -> str:
        if not self.items:
            return 'Backlog empty.'
        return f'{len(self.items)} items pending: ' + ', '.join(self.items[:5])
