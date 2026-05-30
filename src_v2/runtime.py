"""[OPT-8] Pre-built inverted token index for O(1) prompt routing instead of O(n*m) brute force.
   [OPT-9] Single-pass match collection with early termination.
   [OPT-10] Lazy execution registry with cached singleton."""
from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
from .commands import PORTED_COMMANDS
from .context import PortContext, build_port_context, render_context
from .history import HistoryLog
from .models import PermissionDenial, PortingModule
from .query_engine import QueryEngineConfig, QueryEnginePort, TurnResult
from .setup import SetupReport, WorkspaceSetup, run_setup
from .system_init import build_system_init_message
from .tools import PORTED_TOOLS
from .execution_registry import build_execution_registry


@dataclass(frozen=True, slots=True)
class RoutedMatch:
    kind: str
    name: str
    source_hint: str
    score: int


@dataclass
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
            '# Runtime Session', '', f'Prompt: {self.prompt}', '',
            '## Context', render_context(self.context), '',
            '## Setup',
            f'- Python: {self.setup.python_version} ({self.setup.implementation})',
            f'- Platform: {self.setup.platform_name}',
            f'- Test command: {self.setup.test_command}',
            '', '## Startup Steps',
            *(f'- {step}' for step in self.setup.startup_steps()),
            '', '## System Init', self.system_init_message, '', '## Routed Matches',
        ]
        if self.routed_matches:
            lines.extend(
                f'- [{match.kind}] {match.name} ({match.score}) — {match.source_hint}'
                for match in self.routed_matches
            )
        else:
            lines.append('- none')
        lines.extend([
            '', '## Command Execution', *(self.command_execution_messages or ('none',)),
            '', '## Tool Execution', *(self.tool_execution_messages or ('none',)),
            '', '## Stream Events',
            *(f"- {event['type']}: {event}" for event in self.stream_events),
            '', '## Turn Result', self.turn_result.output, '',
            f'Persisted session path: {self.persisted_session_path}', '',
            self.history.as_markdown(),
        ])
        return '\n'.join(lines)


# [OPT-8] Pre-built inverted index: token -> frozenset of (kind, module_index)
@lru_cache(maxsize=1)
def _build_routing_index() -> dict[str, frozenset[tuple[str, int]]]:
    raw: dict[str, set[tuple[str, int]]] = {}

    def _index_module(kind: str, idx: int, module: PortingModule) -> None:
        text = f'{module.name} {module.source_hint} {module.responsibility}'.lower()
        tokens = set(text.replace('/', ' ').replace('-', ' ').replace('_', ' ').replace('.', ' ').split())
        for token in tokens:
            raw.setdefault(token, set()).add((kind, idx))

    for i, mod in enumerate(PORTED_COMMANDS):
        _index_module('command', i, mod)
    for i, mod in enumerate(PORTED_TOOLS):
        _index_module('tool', i, mod)

    return {token: frozenset(entries) for token, entries in raw.items()}


# [OPT-8] Memoise the substring-expansion so repeat prompts pay near-zero cost.
@lru_cache(maxsize=512)
def _resolve_token(token: str) -> frozenset[tuple[str, int]]:
    index = _build_routing_index()
    result: set[tuple[str, int]] = set()
    direct = index.get(token)
    if direct is not None:
        result.update(direct)
    for key, entries in index.items():
        if key is token:
            continue
        if token in key:
            result.update(entries)
    return frozenset(result)


# [OPT-8/OPT-9] Module-level route cache: identical (prompt, limit) pairs are
# free after the first call.
@lru_cache(maxsize=1024)
def _route_prompt_cached(prompt: str, limit: int) -> tuple[RoutedMatch, ...]:
    tokens = {token.lower() for token in prompt.replace('/', ' ').replace('-', ' ').split() if token}

    score_map: dict[tuple[str, int], int] = {}
    for token in tokens:
        for entry in _resolve_token(token):
            score_map[entry] = score_map.get(entry, 0) + 1

    all_modules = {'command': PORTED_COMMANDS, 'tool': PORTED_TOOLS}
    raw_matches: list[RoutedMatch] = []
    for (kind, idx), score in score_map.items():
        module = all_modules[kind][idx]
        raw_matches.append(RoutedMatch(kind=kind, name=module.name, source_hint=module.source_hint, score=score))

    raw_matches.sort(key=lambda m: (-m.score, m.kind, m.name))

    selected: list[RoutedMatch] = []
    seen_kinds: set[str] = set()
    rest: list[RoutedMatch] = []

    for match in raw_matches:
        if match.kind not in seen_kinds and len(seen_kinds) < 2:
            selected.append(match)
            seen_kinds.add(match.kind)
        else:
            rest.append(match)

    selected.extend(rest[:max(0, limit - len(selected))])
    return tuple(selected[:limit])


class PortRuntime:
    def route_prompt(self, prompt: str, limit: int = 5) -> list[RoutedMatch]:
        return list(_route_prompt_cached(prompt, limit))

    def bootstrap_session(self, prompt: str, limit: int = 5) -> RuntimeSession:
        context = build_port_context()
        setup_report = run_setup(trusted=True)
        setup = setup_report.setup
        history = HistoryLog()
        engine = QueryEnginePort.from_workspace()
        history.add('context', f'python_files={context.python_file_count}, archive_available={context.archive_available}')
        history.add('registry', f'commands={len(PORTED_COMMANDS)}, tools={len(PORTED_TOOLS)}')
        matches = self.route_prompt(prompt, limit=limit)

        # [OPT-10] Cached singleton registry
        registry = build_execution_registry()

        cmd_names: list[str] = []
        tool_names_list: list[str] = []
        command_execs: list[str] = []
        tool_execs: list[str] = []

        for match in matches:
            if match.kind == 'command':
                cmd_names.append(match.name)
                cmd = registry.command(match.name)
                if cmd:
                    command_execs.append(cmd.execute(prompt))
            else:
                tool_names_list.append(match.name)
                tool = registry.tool(match.name)
                if tool:
                    tool_execs.append(tool.execute(prompt))

        denials = tuple(self._infer_permission_denials(matches))
        matched_commands = tuple(cmd_names)
        matched_tools = tuple(tool_names_list)

        stream_events = tuple(engine.stream_submit_message(
            prompt, matched_commands=matched_commands, matched_tools=matched_tools, denied_tools=denials,
        ))
        turn_result = engine.submit_message(
            prompt, matched_commands=matched_commands, matched_tools=matched_tools, denied_tools=denials,
        )
        persisted_session_path = engine.persist_session()
        history.add('routing', f'matches={len(matches)} for prompt={prompt!r}')
        history.add('execution', f'command_execs={len(command_execs)} tool_execs={len(tool_execs)}')
        history.add('turn', f'commands={len(turn_result.matched_commands)} tools={len(turn_result.matched_tools)} denials={len(turn_result.permission_denials)} stop={turn_result.stop_reason}')
        history.add('session_store', persisted_session_path)
        return RuntimeSession(
            prompt=prompt, context=context, setup=setup, setup_report=setup_report,
            system_init_message=build_system_init_message(trusted=True),
            history=history, routed_matches=matches, turn_result=turn_result,
            command_execution_messages=tuple(command_execs), tool_execution_messages=tuple(tool_execs),
            stream_events=stream_events, persisted_session_path=persisted_session_path,
        )

    def run_turn_loop(self, prompt: str, limit: int = 5, max_turns: int = 3, structured_output: bool = False) -> list[TurnResult]:
        engine = QueryEnginePort.from_workspace()
        engine.config = QueryEngineConfig(max_turns=max_turns, structured_output=structured_output)
        matches = self.route_prompt(prompt, limit=limit)
        command_names = tuple(match.name for match in matches if match.kind == 'command')
        tool_names = tuple(match.name for match in matches if match.kind == 'tool')

        # [OPT-7] Use batch submission for turn loops
        prompts = [prompt if i == 0 else f'{prompt} [turn {i + 1}]' for i in range(max_turns)]
        return engine.submit_batch(prompts, command_names, tool_names)

    def _infer_permission_denials(self, matches: list[RoutedMatch]) -> list[PermissionDenial]:
        return [
            PermissionDenial(tool_name=match.name, reason='destructive shell execution remains gated in the Python port')
            for match in matches
            if match.kind == 'tool' and 'bash' in match.name.lower()
        ]

    def _collect_matches(self, tokens: set[str], modules: tuple[PortingModule, ...], kind: str) -> list[RoutedMatch]:
        matches: list[RoutedMatch] = []
        for module in modules:
            score = self._score(tokens, module)
            if score > 0:
                matches.append(RoutedMatch(kind=kind, name=module.name, source_hint=module.source_hint, score=score))
        matches.sort(key=lambda item: (-item.score, item.name))
        return matches

    @staticmethod
    def _score(tokens: set[str], module: PortingModule) -> int:
        haystacks = [module.name.lower(), module.source_hint.lower(), module.responsibility.lower()]
        score = 0
        for token in tokens:
            if any(token in haystack for haystack in haystacks):
                score += 1
        return score
