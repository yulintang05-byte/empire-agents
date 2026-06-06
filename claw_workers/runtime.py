"""Runtime orchestration: bootstrap a full session and run turn loops."""
from __future__ import annotations

from dataclasses import dataclass

from .context import PortContext, build_port_context, render_context
from .execution import build_execution_registry
from .history import HistoryLog
from .query_engine import QueryEngineConfig, QueryEnginePort, TurnResult
from .registry import command_registry, tool_registry
from .routing import RoutedMatch
from .setup import SetupReport, WorkspaceSetup, build_system_init_message, run_setup


@dataclass(slots=True)
class RuntimeSession:
    prompt: str
    context: PortContext
    setup: WorkspaceSetup
    setup_report: SetupReport
    system_init_message: str
    history: HistoryLog
    routed_matches: list[RoutedMatch]
    turn_result: TurnResult
    command_execution_messages: tuple[str, ...]
    tool_execution_messages: tuple[str, ...]
    stream_events: tuple[dict[str, object], ...]
    persisted_session_path: str

    def as_markdown(self) -> str:
        lines = [
            "# Runtime Session",
            "",
            f"Prompt: {self.prompt}",
            "",
            "## Context",
            render_context(self.context),
            "",
            "## Setup",
            f"- Python: {self.setup.python_version} ({self.setup.implementation})",
            f"- Platform: {self.setup.platform_name}",
            f"- Test command: {self.setup.test_command}",
            "",
            "## Startup Steps",
            *(f"- {step}" for step in self.setup.startup_steps()),
            "",
            "## System Init",
            self.system_init_message,
            "",
            "## Routed Matches",
        ]
        if self.routed_matches:
            lines.extend(
                f"- [{m.kind}] {m.name} ({m.score}) — {m.source_hint}"
                for m in self.routed_matches
            )
        else:
            lines.append("- none")
        lines.extend(
            [
                "",
                "## Command Execution",
                *(self.command_execution_messages or ("none",)),
                "",
                "## Tool Execution",
                *(self.tool_execution_messages or ("none",)),
                "",
                "## Stream Events",
                *(f"- {event['type']}: {event}" for event in self.stream_events),
                "",
                "## Turn Result",
                self.turn_result.output,
                "",
                f"Persisted session path: {self.persisted_session_path}",
                "",
                self.history.as_markdown(),
            ]
        )
        return "\n".join(lines)


def bootstrap_session(runtime, prompt: str, limit: int = 5) -> RuntimeSession:
    context = build_port_context()
    setup_report = run_setup(trusted=True)
    history = HistoryLog()
    engine = QueryEnginePort.from_workspace()
    history.add(
        "context",
        f"python_files={context.python_file_count}, archive_available={context.archive_available}",
    )
    history.add(
        "registry", f"commands={len(command_registry())}, tools={len(tool_registry())}"
    )
    matches = runtime.route_prompt(prompt, limit=limit)
    registry = build_execution_registry()

    cmd_names: list[str] = []
    tool_names: list[str] = []
    command_execs: list[str] = []
    tool_execs: list[str] = []
    for match in matches:
        if match.kind == "command":
            cmd_names.append(match.name)
            shim = registry.command(match.name)
            if shim:
                command_execs.append(shim.execute(prompt))
        else:
            tool_names.append(match.name)
            shim = registry.tool(match.name)
            if shim:
                tool_execs.append(shim.execute(prompt))

    denials = tuple(runtime.infer_permission_denials(matches))
    matched_commands = tuple(cmd_names)
    matched_tools = tuple(tool_names)
    stream_events = tuple(
        engine.stream_submit_message(
            prompt,
            matched_commands=matched_commands,
            matched_tools=matched_tools,
            denied_tools=denials,
        )
    )
    turn_result = engine.submit_message(
        prompt,
        matched_commands=matched_commands,
        matched_tools=matched_tools,
        denied_tools=denials,
    )
    persisted = engine.persist_session()
    history.add("routing", f"matches={len(matches)} for prompt={prompt!r}")
    history.add(
        "execution", f"command_execs={len(command_execs)} tool_execs={len(tool_execs)}"
    )
    history.add(
        "turn",
        f"commands={len(turn_result.matched_commands)} tools={len(turn_result.matched_tools)} "
        f"denials={len(turn_result.permission_denials)} stop={turn_result.stop_reason}",
    )
    history.add("session_store", persisted)
    return RuntimeSession(
        prompt=prompt,
        context=context,
        setup=setup_report.setup,
        setup_report=setup_report,
        system_init_message=build_system_init_message(trusted=True),
        history=history,
        routed_matches=matches,
        turn_result=turn_result,
        command_execution_messages=tuple(command_execs),
        tool_execution_messages=tuple(tool_execs),
        stream_events=stream_events,
        persisted_session_path=persisted,
    )


def run_turn_loop(
    runtime, prompt: str, limit: int = 5, max_turns: int = 3, structured_output: bool = False
) -> list[TurnResult]:
    engine = QueryEnginePort.from_workspace()
    engine.config = QueryEngineConfig(max_turns=max_turns, structured_output=structured_output)
    matches = runtime.route_prompt(prompt, limit=limit)
    command_names = tuple(m.name for m in matches if m.kind == "command")
    tool_names = tuple(m.name for m in matches if m.kind == "tool")
    prompts = [prompt if i == 0 else f"{prompt} [turn {i + 1}]" for i in range(max_turns)]
    return engine.submit_batch(prompts, command_names, tool_names)
