from __future__ import annotations
import json
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

def command_names() -> tuple[str, ...]:
    return tuple(m.name for m in PORTED_COMMANDS)

def get_command(name: str) -> PortingModule | None:
    for m in PORTED_COMMANDS:
        if m.name == name:
            return m
    return None

def get_commands(include_plugin_commands: bool = True, include_skill_commands: bool = True) -> tuple[PortingModule, ...]:
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
    query_lower = query.lower()
    matches = []
    for m in PORTED_COMMANDS:
        text = f'{m.name} {m.source_hint} {m.responsibility}'.lower()
        if query_lower in text:
            matches.append(m)
    return tuple(matches[:limit])

def render_command_index(limit: int = 20, query: str = '') -> str:
    if query:
        matches = find_commands(query, limit=limit)
    else:
        matches = PORTED_COMMANDS[:limit]
    lines = [f'Command index ({len(matches)} shown):', '']
    lines.extend(f'- {m.name} — {m.source_hint}' for m in matches)
    return '\n'.join(lines)

class CommandResult:
    def __init__(self, handled: bool, message: str):
        self.handled = handled
        self.message = message

def execute_command(name: str, prompt: str) -> CommandResult:
    cmd = get_command(name)
    if cmd is None:
        return CommandResult(handled=False, message=f'Unknown command: {name}')
    return CommandResult(handled=True, message=f'[{cmd.name}] executed with prompt: {prompt}')
