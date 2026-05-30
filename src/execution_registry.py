from __future__ import annotations
from dataclasses import dataclass
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
        self._commands = commands
        self._tools = tools

    def command(self, name: str) -> MirroredCommand | None:
        for m in self._commands:
            if m.name == name:
                return MirroredCommand(name=m.name, source_hint=m.source_hint)
        return None

    def tool(self, name: str) -> MirroredTool | None:
        for m in self._tools:
            if m.name == name:
                return MirroredTool(name=m.name, source_hint=m.source_hint)
        return None


def build_execution_registry() -> ExecutionRegistry:
    return ExecutionRegistry(PORTED_COMMANDS, PORTED_TOOLS)
