from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class PortContext:
    python_file_count: int
    archive_available: bool
    workspace_root: str


def build_port_context() -> PortContext:
    python_files = sum(1 for _ in WORKSPACE_ROOT.rglob('*.py'))
    archive_available = (WORKSPACE_ROOT / 'archive' / 'claude_code_ts_snapshot' / 'src').exists()
    return PortContext(
        python_file_count=python_files,
        archive_available=archive_available,
        workspace_root=str(WORKSPACE_ROOT),
    )


def render_context(ctx: PortContext) -> str:
    return (
        f'Python files: {ctx.python_file_count}\n'
        f'Archive available: {ctx.archive_available}\n'
        f'Workspace root: {ctx.workspace_root}'
    )
