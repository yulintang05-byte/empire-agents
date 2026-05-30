from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
from .commands import PORTED_COMMANDS
from .tools import PORTED_TOOLS
from .models import PortingModule


@dataclass
class MirroredCommand:
    name: str
    source_hint: str

    def execute(self, prompt: str) -> str:
        return f'[cmd:{self.name}] {prompt}'


@dataclass
class MirroredTool:
    name: str
    source_hint: str

    def execute(self, payload: str) -> str:
        return f'[tool:{self.name}] {payload}'


class ExecutionRegistry:
    def __init__(self, commands: tuple[PortingModule, ...], tools: tuple[PortingModule, ...]):
        # [OPT-10] Dict-indexed lookups instead of linear scan
        self._cmd_index = {m.name: MirroredCommand(name=m.name, source_hint=m.source_hint) for m in commands}
        self._tool_index = {m.name: MirroredTool(name=m.name, source_hint=m.source_hint) for m in tools}

    def command(self, name: str) -> MirroredCommand | None:
        return self._cmd_index.get(name)

    def tool(self, name: str) -> MirroredTool | None:
        return self._tool_index.get(name)


# [OPT-10] Cached singleton: registry is built once and reused
@lru_cache(maxsize=1)
def build_execution_registry() -> ExecutionRegistry:
    return ExecutionRegistry(PORTED_COMMANDS, PORTED_TOOLS)
