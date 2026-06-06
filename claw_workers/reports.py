"""Auxiliary reports: graphs, mode simulations, tool pool and parity audit.

These were a handful of tiny single-purpose modules in the original port;
consolidating them keeps the public surface small without losing any behaviour.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .registry import command_registry, tool_registry

_DATA_DIR = Path(__file__).resolve().parent / "reference_data"
_ARCHIVE_SURFACE = _DATA_DIR / "archive_surface_snapshot.json"
_COMMANDS_SNAPSHOT = _DATA_DIR / "commands_snapshot.json"
_TOOLS_SNAPSHOT = _DATA_DIR / "tools_snapshot.json"
_ARCHIVE_ROOT = (
    Path(__file__).resolve().parent.parent / "archive" / "claude_code_ts_snapshot" / "src"
)


# -- bootstrap / command graphs ------------------------------------------
@dataclass(slots=True)
class BootstrapGraph:
    stages: list[str] = field(default_factory=list)

    def as_markdown(self) -> str:
        lines = ["# Bootstrap Graph", ""]
        lines.extend(f"{i}. {stage}" for i, stage in enumerate(self.stages, 1))
        return "\n".join(lines)


def build_bootstrap_graph() -> BootstrapGraph:
    return BootstrapGraph(
        stages=[
            "Load workspace context",
            "Build port manifest",
            "Initialize execution registry",
            "Prefetch plugin/MCP/skill tools",
            "Build routing index",
            "Ready for prompts",
        ]
    )


@dataclass(slots=True)
class CommandGraphSegment:
    name: str
    entry_count: int
    description: str


@dataclass(slots=True)
class CommandGraph:
    segments: list[CommandGraphSegment] = field(default_factory=list)

    def as_markdown(self) -> str:
        lines = ["# Command Graph Segmentation", ""]
        for seg in self.segments:
            lines.append(f"## {seg.name} ({seg.entry_count} entries)")
            lines.append(seg.description)
            lines.append("")
        return "\n".join(lines)


def build_command_graph() -> CommandGraph:
    return CommandGraph(
        segments=[
            CommandGraphSegment("core", 12, "Core shell commands (help, commit, review, ...)"),
            CommandGraphSegment("plugin", 45, "Plugin-contributed commands registered at startup"),
            CommandGraphSegment("skill", 51, "Skill-contributed commands loaded on demand"),
        ]
    )


# -- mode simulations -----------------------------------------------------
@dataclass(frozen=True, slots=True)
class ModeReport:
    mode: str
    target: str
    status: str = "simulated"

    def as_text(self) -> str:
        return f"[{self.mode}] target={self.target} status={self.status}"


def run_remote_mode(target: str) -> ModeReport:
    return ModeReport("remote", target)


def run_ssh_mode(target: str) -> ModeReport:
    return ModeReport("ssh", target)


def run_teleport_mode(target: str) -> ModeReport:
    return ModeReport("teleport", target)


def run_direct_connect(target: str) -> ModeReport:
    return ModeReport("direct-connect", target)


def run_deep_link(target: str) -> ModeReport:
    return ModeReport("deep-link", target)


# -- tool pool ------------------------------------------------------------
@dataclass(slots=True)
class ToolPool:
    tool_names: list[str] = field(default_factory=list)
    denied_tools: list[str] = field(default_factory=list)
    mcp_tools: list[str] = field(default_factory=list)

    def as_markdown(self) -> str:
        lines = [
            "# Tool Pool",
            "",
            f"Available: {len(self.tool_names)}",
            f"Denied: {len(self.denied_tools)}",
            f"MCP: {len(self.mcp_tools)}",
        ]
        if self.tool_names:
            lines.append("")
            lines.extend(f"- {name}" for name in self.tool_names[:20])
        return "\n".join(lines)


def assemble_tool_pool() -> ToolPool:
    reg = tool_registry()
    return ToolPool(
        tool_names=[t.name for t in reg],
        denied_tools=[],
        mcp_tools=[t.name for t in reg if "mcp" in t.source_hint.lower()],
    )


# -- parity audit ---------------------------------------------------------
ARCHIVE_ROOT_FILES = {
    "QueryEngine.ts": "query_engine.py",
    "Task.ts": "task.py",
    "commands.ts": "registry.py",
    "context.ts": "context.py",
    "history.ts": "history.py",
    "main.tsx": "cli.py",
    "setup.ts": "setup.py",
    "tools.ts": "registry.py",
}


@dataclass(frozen=True, slots=True)
class ParityAuditResult:
    archive_present: bool
    total_file_ratio: tuple[int, int]
    command_entry_ratio: tuple[int, int]
    tool_entry_ratio: tuple[int, int]

    def to_markdown(self) -> str:
        lines = ["# Parity Audit"]
        if not self.archive_present:
            lines.append(
                "Local archive unavailable; comparing against the captured surface snapshot."
            )
        lines.extend(
            [
                "",
                f"Python files vs archived TS-like files: "
                f"**{self.total_file_ratio[0]}/{self.total_file_ratio[1]}**",
                f"Command entry coverage: "
                f"**{self.command_entry_ratio[0]}/{self.command_entry_ratio[1]}**",
                f"Tool entry coverage: "
                f"**{self.tool_entry_ratio[0]}/{self.tool_entry_ratio[1]}**",
            ]
        )
        return "\n".join(lines)


def run_parity_audit() -> ParityAuditResult:
    surface = json.loads(_ARCHIVE_SURFACE.read_text())
    package_root = Path(__file__).resolve().parent
    py_files = sum(1 for p in package_root.rglob("*.py") if p.is_file())
    return ParityAuditResult(
        archive_present=_ARCHIVE_ROOT.exists(),
        total_file_ratio=(py_files, int(surface["total_ts_like_files"])),
        command_entry_ratio=(len(command_registry()), int(surface["command_entry_count"])),
        tool_entry_ratio=(len(tool_registry()), int(surface["tool_entry_count"])),
    )
