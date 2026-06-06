"""Execution shims for mirrored commands and tools.

The registry is a process-wide cached singleton (built once via
``lru_cache``) with dict-indexed lookups, so repeated ``command()`` / ``tool()``
calls are O(1) and allocate nothing.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from .registry import command_registry, tool_registry


@dataclass(frozen=True, slots=True)
class MirroredCommand:
    name: str
    source_hint: str

    def execute(self, prompt: str) -> str:
        return f"[cmd:{self.name}] {prompt}"


@dataclass(frozen=True, slots=True)
class MirroredTool:
    name: str
    source_hint: str

    def execute(self, payload: str) -> str:
        return f"[tool:{self.name}] {payload}"


class ExecutionRegistry:
    __slots__ = ("_commands", "_tools")

    def __init__(self) -> None:
        self._commands = {
            m.name: MirroredCommand(m.name, m.source_hint) for m in command_registry()
        }
        self._tools = {m.name: MirroredTool(m.name, m.source_hint) for m in tool_registry()}

    def command(self, name: str) -> MirroredCommand | None:
        return self._commands.get(name)

    def tool(self, name: str) -> MirroredTool | None:
        return self._tools.get(name)


@lru_cache(maxsize=1)
def build_execution_registry() -> ExecutionRegistry:
    return ExecutionRegistry()


# -- command / tool execution facade --------------------------------------
@dataclass(frozen=True, slots=True)
class ShimResult:
    handled: bool
    message: str


def execute_command(name: str, prompt: str) -> ShimResult:
    cmd = build_execution_registry().command(name)
    if cmd is None:
        return ShimResult(False, f"Unknown command: {name}")
    return ShimResult(True, f"[{cmd.name}] executed with prompt: {prompt}")


def execute_tool(name: str, payload: str) -> ShimResult:
    tool = build_execution_registry().tool(name)
    if tool is None:
        return ShimResult(False, f"Unknown tool: {name}")
    return ShimResult(True, f"[{tool.name}] executed with payload: {payload}")
