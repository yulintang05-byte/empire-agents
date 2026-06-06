"""claw_workers — an optimized Python port of the claw-code ultra workers.

A faithful reverse-engineering of the claw-code-parity workspace, rebuilt as a
single cohesive package with ten-plus performance optimizations over the naive
baseline (see ``benchmark/simulate.py`` and the project README).

Public API
----------
Registry / inventory:  :func:`get_command`, :func:`get_tool`,
    :func:`find_commands`, :func:`find_tools`, :func:`get_commands`,
    :func:`get_tools`, :class:`Registry`.
Routing & runtime:     :class:`PortRuntime`, :class:`RoutedMatch`.
Query engine:          :class:`QueryEnginePort`, :class:`QueryEngineConfig`,
    :class:`TurnResult`.
Models:                :class:`PortingModule`, :class:`UsageSummary`,
    :class:`PermissionDenial`, :class:`PortingTask`.
"""
from __future__ import annotations

from .models import PermissionDenial, PortingModule, UsageSummary
from .permissions import ToolPermissionContext
from .query_engine import QueryEngineConfig, QueryEnginePort, TurnResult
from .registry import (
    Registry,
    command_names,
    command_registry,
    find_commands,
    find_tools,
    get_command,
    get_commands,
    get_tool,
    get_tools,
    tool_names,
    tool_registry,
)
from .routing import PortRuntime, RoutedMatch
from .task import PortingTask
from .transcript import TranscriptStore

__version__ = "2.0.0"

__all__ = [
    "PermissionDenial",
    "PortingModule",
    "PortingTask",
    "PortRuntime",
    "QueryEngineConfig",
    "QueryEnginePort",
    "Registry",
    "RoutedMatch",
    "ToolPermissionContext",
    "TranscriptStore",
    "TurnResult",
    "UsageSummary",
    "command_names",
    "command_registry",
    "find_commands",
    "find_tools",
    "get_command",
    "get_commands",
    "get_tool",
    "get_tools",
    "tool_names",
    "tool_registry",
]
