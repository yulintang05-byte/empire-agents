from __future__ import annotations
import json
from functools import lru_cache
from pathlib import Path
from .models import PortingModule

_SNAPSHOT = Path(__file__).resolve().parent / 'reference_data' / 'commands_snapshot.json'


def _load_commands() -> tuple[PortingModule, ...]:
    raw = json.loads(_SNAPSHOT.read_text())
    return tuple(
        PortingModule(
            name=entry['name'],
            source_hint=entry['source'],
            responsibility=f"{entry['type']} command: {entry['name']}",
        )
        for entry in raw
    )


PORTED_COMMANDS: tuple[PortingModule, ...] = _load_commands()


# [OPT-3] Dict-indexed O(1) lookup instead of linear scan
@lru_cache(maxsize=1)
def _command_index() -> dict[str, PortingModule]:
    return {m.name: m for m in PORTED_COMMANDS}


# [OPT-4] Trigram inverted index for fast substring search
@lru_cache(maxsize=1)
def _command_trigram_index() -> dict[str, set[int]]:
    index: dict[str, set[int]] = {}
    for i, m in enumerate(PORTED_COMMANDS):
        text = f'{m.name} {m.source_hint} {m.responsibility}'.lower()
        for start in range(len(text) - 2):
            trigram = text[start:start + 3]
            if trigram not in index:
                index[trigram] = set()
            index[trigram].add(i)
    return index


def command_names() -> tuple[str, ...]:
    return tuple(m.name for m in PORTED_COMMANDS)


def get_command(name: str) -> PortingModule | None:
    # [OPT-3] O(1) dict lookup
    return _command_index().get(name)


def get_commands(include_plugin_commands: bool = True, include_skill_commands: bool = True) -> tuple[PortingModule, ...]:
    # [OPT-5] Fast path when no filtering needed
    if include_plugin_commands and include_skill_commands:
        return PORTED_COMMANDS
    result = []
    for m in PORTED_COMMANDS:
        resp = m.responsibility.lower()
        if not include_plugin_commands and 'plugin' in resp:
            continue
        if not include_skill_commands and 'skill' in resp:
            continue
        result.append(m)
    return tuple(result)


def find_commands(query: str, limit: int = 10) -> tuple[PortingModule, ...]:
    # [OPT-4] Use trigram index for fast candidate narrowing
    query_lower = query.lower()
    if len(query_lower) >= 3:
        trigram_idx = _command_trigram_index()
        trigrams = [query_lower[i:i + 3] for i in range(len(query_lower) - 2)]
        candidate_sets = [trigram_idx.get(tri, set()) for tri in trigrams]
        if candidate_sets:
            candidates = candidate_sets[0]
            for s in candidate_sets[1:]:
                candidates = candidates & s
            matches = []
            for idx in sorted(candidates):
                m = PORTED_COMMANDS[idx]
                text = f'{m.name} {m.source_hint} {m.responsibility}'.lower()
                if query_lower in text:
                    matches.append(m)
                    if len(matches) >= limit:
                        break
            return tuple(matches)
    matches = []
    for m in PORTED_COMMANDS:
        text = f'{m.name} {m.source_hint} {m.responsibility}'.lower()
        if query_lower in text:
            matches.append(m)
            if len(matches) >= limit:
                break
    return tuple(matches)


def render_command_index(limit: int = 20, query: str = '') -> str:
    if query:
        matches = find_commands(query, limit=limit)
    else:
        matches = PORTED_COMMANDS[:limit]
    lines = [f'Command index ({len(matches)} shown):', '']
    lines.extend(f'- {m.name} — {m.source_hint}' for m in matches)
    return '\n'.join(lines)


class CommandResult:
    __slots__ = ('handled', 'message')

    def __init__(self, handled: bool, message: str):
        self.handled = handled
        self.message = message


def execute_command(name: str, prompt: str) -> CommandResult:
    cmd = get_command(name)
    if cmd is None:
        return CommandResult(handled=False, message=f'Unknown command: {name}')
    return CommandResult(handled=True, message=f'[{cmd.name}] executed with prompt: {prompt}')
