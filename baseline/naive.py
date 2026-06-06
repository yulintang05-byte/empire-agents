"""Naive, unoptimized reference implementation (the "before" picture).

Every operation here is deliberately written the slow, obvious way so the
benchmark can measure what the optimizations in :mod:`claw_workers` actually buy.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent / "reference_data"


# -- models ---------------------------------------------------------------
@dataclass(frozen=True)
class PortingModule:
    name: str
    source_hint: str
    responsibility: str


@dataclass(frozen=True)
class PermissionDenial:
    tool_name: str
    reason: str


@dataclass(frozen=True)
class UsageSummary:
    input_tokens: int
    output_tokens: int

    def add_turn(self, prompt: str, output: str) -> "UsageSummary":
        # Naive: counts whitespace-delimited words by allocating two lists.
        return UsageSummary(
            input_tokens=self.input_tokens + len(prompt.split()),
            output_tokens=self.output_tokens + len(output.split()),
        )


def _load(path: Path, category: str) -> tuple[PortingModule, ...]:
    raw = json.loads(path.read_text())
    return tuple(
        PortingModule(
            name=e["name"],
            source_hint=e["source"],
            responsibility=f"{e['type']} {category}: {e['name']}",
        )
        for e in raw
    )


PORTED_COMMANDS = _load(_DATA_DIR / "commands_snapshot.json", "command")
PORTED_TOOLS = _load(_DATA_DIR / "tools_snapshot.json", "tool")


# -- registry: linear scans, corpus rebuilt every call --------------------
def get_command(name: str) -> PortingModule | None:
    for m in PORTED_COMMANDS:
        if m.name == name:
            return m
    return None


def get_tool(name: str) -> PortingModule | None:
    for m in PORTED_TOOLS:
        if m.name == name:
            return m
    return None


def _find(modules, query: str, limit: int) -> tuple[PortingModule, ...]:
    q = query.lower()
    out = []
    for m in modules:
        text = f"{m.name} {m.source_hint} {m.responsibility}".lower()  # rebuilt each call
        if q in text:
            out.append(m)
    return tuple(out[:limit])


def find_commands(query: str, limit: int = 10):
    return _find(PORTED_COMMANDS, query, limit)


def find_tools(query: str, limit: int = 10):
    return _find(PORTED_TOOLS, query, limit)


def command_names():
    return tuple(m.name for m in PORTED_COMMANDS)


def get_commands(include_plugin_commands: bool = True, include_skill_commands: bool = True):
    out = []
    for m in PORTED_COMMANDS:
        resp = m.responsibility.lower()
        if not include_plugin_commands and "plugin" in resp:
            continue
        if not include_skill_commands and "skill" in resp:
            continue
        out.append(m)
    return tuple(out)


_SIMPLE = {"BashTool", "FileEditTool", "FileReadTool", "FileWriteTool", "GlobTool", "GrepTool"}


def get_tools(simple_mode: bool = False, include_mcp: bool = True, permission_context=None):
    out = []
    for m in PORTED_TOOLS:
        if simple_mode and m.name not in _SIMPLE:
            continue
        if not include_mcp and "mcp" in m.source_hint.lower():
            continue
        out.append(m)
    return tuple(out)


# -- execution registry: rebuilt fresh on every call ----------------------
@dataclass
class MirroredCommand:
    name: str
    source_hint: str

    def execute(self, prompt: str) -> str:
        return f"[cmd:{self.name}] {prompt}"


@dataclass
class MirroredTool:
    name: str
    source_hint: str

    def execute(self, payload: str) -> str:
        return f"[tool:{self.name}] {payload}"


class ExecutionRegistry:
    def __init__(self, commands, tools):
        self._commands = commands
        self._tools = tools

    def command(self, name: str):
        for m in self._commands:  # linear scan
            if m.name == name:
                return MirroredCommand(m.name, m.source_hint)
        return None

    def tool(self, name: str):
        for m in self._tools:  # linear scan
            if m.name == name:
                return MirroredTool(m.name, m.source_hint)
        return None


def build_execution_registry() -> ExecutionRegistry:
    return ExecutionRegistry(PORTED_COMMANDS, PORTED_TOOLS)  # no caching


# -- transcript: plain list with slice-copy compaction --------------------
@dataclass
class TranscriptStore:
    entries: list = field(default_factory=list)
    flushed: bool = False

    def append(self, entry: str) -> None:
        self.entries.append(entry)
        self.flushed = False

    def compact(self, keep_last: int = 10) -> None:
        if len(self.entries) > keep_last:
            self.entries[:] = self.entries[-keep_last:]  # allocates a new list

    def replay(self):
        return tuple(self.entries)

    def flush(self) -> None:
        self.flushed = True


# -- manifest: rescans the filesystem on every call -----------------------
@dataclass
class PortManifest:
    total_python_files: int = 0


def build_port_manifest() -> PortManifest:
    root = Path(__file__).resolve().parent
    total = sum(1 for _ in root.rglob("*.py"))
    return PortManifest(total_python_files=total)


# -- query engine ---------------------------------------------------------
@dataclass(frozen=True)
class TurnResult:
    output: str
    stop_reason: str
    matched_commands: tuple
    matched_tools: tuple
    permission_denials: tuple


class QueryEnginePort:
    def __init__(self, manifest=None):
        self.manifest = manifest or build_port_manifest()
        self.session_id = uuid.uuid4().hex[:12]
        self.usage = UsageSummary(0, 0)
        self.transcript_store = TranscriptStore()
        self.max_turns = 10
        self.max_budget = 100_000
        self._turns = 0

    @classmethod
    def from_workspace(cls):
        return cls(build_port_manifest())

    def submit_message(self, prompt, matched_commands=(), matched_tools=(), denied_tools=()):
        self._turns += 1
        self.transcript_store.append(f"user: {prompt}")
        if self._turns > self.max_turns:
            return TurnResult("Max turns reached.", "max_turns_reached",
                              matched_commands, matched_tools, denied_tools)
        # Naive: build the output by repeated string concatenation.
        output = f"Processed: {prompt}"
        if matched_commands:
            output = output + " | Commands: " + ", ".join(matched_commands)
        if matched_tools:
            output = output + " | Tools: " + ", ".join(matched_tools)
        if denied_tools:
            output = output + " | Denials: " + str(len(denied_tools))
        output = output + " | Session: " + self.session_id
        output = output + " | Files: " + str(self.manifest.total_python_files)
        self.transcript_store.append(f"assistant: {output}")
        self.usage = self.usage.add_turn(prompt, output)
        total = self.usage.input_tokens + self.usage.output_tokens
        stop = "max_budget_reached" if total > self.max_budget else "completed"
        return TurnResult(output, stop, matched_commands, matched_tools, denied_tools)


# -- routing: brute-force O(prompts x modules x tokens) -------------------
@dataclass(frozen=True)
class RoutedMatch:
    kind: str
    name: str
    source_hint: str
    score: int


def _score(tokens, module) -> int:
    haystacks = [module.name.lower(), module.source_hint.lower(), module.responsibility.lower()]
    score = 0
    for token in tokens:
        if any(token in h for h in haystacks):
            score += 1
    return score


def _collect(tokens, modules, kind):
    matches = []
    for module in modules:
        s = _score(tokens, module)
        if s > 0:
            matches.append(RoutedMatch(kind, module.name, module.source_hint, s))
    matches.sort(key=lambda m: (-m.score, m.name))
    return matches


class PortRuntime:
    def route_prompt(self, prompt: str, limit: int = 5):
        tokens = {t.lower() for t in prompt.replace("/", " ").replace("-", " ").split() if t}
        by_kind = {
            "command": _collect(tokens, PORTED_COMMANDS, "command"),
            "tool": _collect(tokens, PORTED_TOOLS, "tool"),
        }
        selected = []
        for kind in ("command", "tool"):
            if by_kind[kind]:
                selected.append(by_kind[kind].pop(0))
        leftovers = sorted(
            [m for ms in by_kind.values() for m in ms],
            key=lambda m: (-m.score, m.kind, m.name),
        )
        selected.extend(leftovers[: max(0, limit - len(selected))])
        return selected[:limit]
