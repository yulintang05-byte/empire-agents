from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from .models import PermissionDenial, UsageSummary
from .port_manifest import build_port_manifest
from .session_store import StoredSession, save_session
from .transcript import TranscriptStore


@dataclass
class QueryEngineConfig:
    max_turns: int = 10
    structured_output: bool = False
    max_budget_tokens: int = 100_000


@dataclass(frozen=True)
class TurnResult:
    output: str
    stop_reason: str
    matched_commands: tuple[str, ...]
    matched_tools: tuple[str, ...]
    permission_denials: tuple[PermissionDenial, ...]


class QueryEnginePort:
    def __init__(self, manifest=None):
        self.manifest = manifest or build_port_manifest()
        self.config = QueryEngineConfig()
        self.session_id = uuid.uuid4().hex[:12]
        self.usage = UsageSummary(0, 0)
        self.transcript_store = TranscriptStore()
        self._turn_count = 0

    @classmethod
    def from_workspace(cls) -> 'QueryEnginePort':
        return cls(build_port_manifest())

    def submit_message(self, prompt: str, matched_commands: tuple[str, ...] = (),
                       matched_tools: tuple[str, ...] = (),
                       denied_tools: tuple[PermissionDenial, ...] = ()) -> TurnResult:
        self._turn_count += 1
        self.transcript_store.append(f'user: {prompt}')
        if self._turn_count > self.config.max_turns:
            return TurnResult(
                output='Max turns reached.',
                stop_reason='max_turns_reached',
                matched_commands=matched_commands,
                matched_tools=matched_tools,
                permission_denials=denied_tools,
            )
        output = self._format_output(prompt, matched_commands, matched_tools, denied_tools)
        self.transcript_store.append(f'assistant: {output}')
        self.usage = self.usage.add_turn(prompt, output)
        if self.usage.input_tokens + self.usage.output_tokens > self.config.max_budget_tokens:
            stop_reason = 'max_budget_reached'
        else:
            stop_reason = 'completed'
        return TurnResult(
            output=output,
            stop_reason=stop_reason,
            matched_commands=matched_commands,
            matched_tools=matched_tools,
            permission_denials=denied_tools,
        )

    def _format_output(self, prompt, commands, tools, denials):
        parts = [f'Processed: {prompt}']
        if commands:
            parts.append(f'Commands: {", ".join(commands)}')
        if tools:
            parts.append(f'Tools: {", ".join(tools)}')
        if denials:
            parts.append(f'Denials: {len(denials)}')
        parts.append(f'Session: {self.session_id}')
        parts.append(f'Files: {self.manifest.total_python_files}')
        return ' | '.join(parts)

    def stream_submit_message(self, prompt: str, matched_commands=(), matched_tools=(), denied_tools=()) -> list[dict]:
        events = [
            {'type': 'start', 'prompt': prompt},
            {'type': 'routing', 'commands': len(matched_commands), 'tools': len(matched_tools)},
            {'type': 'complete', 'session': self.session_id},
        ]
        return events

    def compact(self, keep_last: int = 10) -> None:
        self.transcript_store.compact(keep_last)

    def persist_session(self) -> str:
        session = StoredSession(
            session_id=self.session_id,
            messages=self.transcript_store.entries if isinstance(self.transcript_store.entries, list) else list(self.transcript_store.entries),
            input_tokens=self.usage.input_tokens,
            output_tokens=self.usage.output_tokens,
        )
        path = save_session(session)
        self.transcript_store.flush()
        return path

    def render_summary(self) -> str:
        lines = [
            '# Query Engine Summary',
            '',
            f'Session: {self.session_id}',
            f'Turns: {self._turn_count}',
            f'Input tokens: {self.usage.input_tokens}',
            f'Output tokens: {self.usage.output_tokens}',
            f'Manifest files: {self.manifest.total_python_files}',
        ]
        return '\n'.join(lines)
