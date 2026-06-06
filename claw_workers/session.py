"""JSON-backed session persistence."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

SESSION_DIR = Path(__file__).resolve().parent.parent / ".port_sessions"


@dataclass(slots=True)
class StoredSession:
    session_id: str
    messages: list[str]
    input_tokens: int
    output_tokens: int


def save_session(session: StoredSession) -> str:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    path = SESSION_DIR / f"{session.session_id}.json"
    path.write_text(
        json.dumps(
            {
                "session_id": session.session_id,
                "messages": session.messages,
                "input_tokens": session.input_tokens,
                "output_tokens": session.output_tokens,
            }
        )
    )
    return str(path)


def load_session(session_id: str) -> StoredSession:
    path = SESSION_DIR / f"{session_id}.json"
    data = json.loads(path.read_text())
    return StoredSession(**data)
