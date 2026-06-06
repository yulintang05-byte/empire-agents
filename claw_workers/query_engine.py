"""Stateful query engine: turns, token budgets, batching, persistence."""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from .manifest import build_port_manifest
from .models import PermissionDenial, UsageSummary
from .session import StoredSession, save_session
from .transcript import TranscriptStore


@dataclass(slots=True)
class QueryEngineConfig:
    max_turns: int = 10
    structured_output: bool = False
    max_budget_tokens: int = 100_000


@dataclass(frozen=True, slots=True)
class TurnResult:
    output: str
    stop_reason: str
    matched_commands: tuple[str, ...]
    matched_tools: tuple[str, ...]
    permission_denials: tuple[PermissionDenial, ...]


def _format_output(
    prompt: str,
    commands: tuple[str, ...],
    tools: tuple[str, ...],
    denials: tuple[PermissionDenial, ...],
    session_id: str,
    total_files: int,
) -> str:
    """String-builder formatting: collect parts, join once (no ``+=`` churn)."""
    parts = [f"Processed: {prompt}"]
    if commands:
        parts.append(f"Commands: {', '.join(commands)}")
    if tools:
        parts.append(f"Tools: {', '.join(tools)}")
    if denials:
        parts.append(f"Denials: {len(denials)}")
    parts.append(f"Session: {session_id}")
    parts.append(f"Files: {total_files}")
    return " | ".join(parts)


class QueryEnginePort:
    __slots__ = ("manifest", "config", "session_id", "usage", "transcript_store", "_turn_count")

    def __init__(self, manifest=None) -> None:
        self.manifest = manifest or build_port_manifest()
        self.config = QueryEngineConfig()
        self.session_id = uuid.uuid4().hex[:12]
        self.usage = UsageSummary(0, 0)
        self.transcript_store = TranscriptStore()
        self._turn_count = 0

    @classmethod
    def from_workspace(cls) -> "QueryEnginePort":
        return cls(build_port_manifest())

    def submit_message(
        self,
        prompt: str,
        matched_commands: tuple[str, ...] = (),
        matched_tools: tuple[str, ...] = (),
        denied_tools: tuple[PermissionDenial, ...] = (),
    ) -> TurnResult:
        self._turn_count += 1
        self.transcript_store.append(f"user: {prompt}")
        if self._turn_count > self.config.max_turns:
            return TurnResult(
                output="Max turns reached.",
                stop_reason="max_turns_reached",
                matched_commands=matched_commands,
                matched_tools=matched_tools,
                permission_denials=denied_tools,
            )
        output = _format_output(
            prompt,
            matched_commands,
            matched_tools,
            denied_tools,
            self.session_id,
            self.manifest.total_python_files,
        )
        self.transcript_store.append(f"assistant: {output}")
        self.usage = self.usage.add_turn(prompt, output)
        stop_reason = (
            "max_budget_reached"
            if self.usage.total_tokens > self.config.max_budget_tokens
            else "completed"
        )
        return TurnResult(
            output=output,
            stop_reason=stop_reason,
            matched_commands=matched_commands,
            matched_tools=matched_tools,
            permission_denials=denied_tools,
        )

    def submit_batch(
        self,
        prompts: list[str],
        matched_commands: tuple[str, ...] = (),
        matched_tools: tuple[str, ...] = (),
    ) -> list[TurnResult]:
        """Submit several prompts in one loop, stopping on the first non-completed turn."""
        results: list[TurnResult] = []
        for prompt in prompts:
            result = self.submit_message(prompt, matched_commands, matched_tools, ())
            results.append(result)
            if result.stop_reason != "completed":
                break
        return results

    def stream_submit_message(
        self,
        prompt: str,
        matched_commands: tuple[str, ...] = (),
        matched_tools: tuple[str, ...] = (),
        denied_tools: tuple[PermissionDenial, ...] = (),
    ) -> list[dict]:
        return [
            {"type": "start", "prompt": prompt},
            {"type": "routing", "commands": len(matched_commands), "tools": len(matched_tools)},
            {"type": "complete", "session": self.session_id},
        ]

    def compact(self, keep_last: int = 10) -> None:
        self.transcript_store.compact(keep_last)

    def persist_session(self) -> str:
        session = StoredSession(
            session_id=self.session_id,
            messages=self.transcript_store.entries,
            input_tokens=self.usage.input_tokens,
            output_tokens=self.usage.output_tokens,
        )
        path = save_session(session)
        self.transcript_store.flush()
        return path

    def render_summary(self) -> str:
        return "\n".join(
            [
                "# Query Engine Summary",
                "",
                f"Session: {self.session_id}",
                f"Turns: {self._turn_count}",
                f"Input tokens: {self.usage.input_tokens}",
                f"Output tokens: {self.usage.output_tokens}",
                f"Manifest files: {self.manifest.total_python_files}",
            ]
        )
