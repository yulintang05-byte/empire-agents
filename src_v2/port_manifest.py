from __future__ import annotations
import time
from dataclasses import dataclass, field
from pathlib import Path
from .models import Subsystem

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

_CACHE_TTL = 10.0
_manifest_cache: dict[str, tuple[float, 'PortManifest']] = {}


@dataclass
class PortManifest:
    top_level_modules: list[Subsystem] = field(default_factory=list)
    total_python_files: int = 0
    total_lines: int = 0

    def to_markdown(self) -> str:
        lines = [
            '# Port Manifest', '',
            f'Total Python files: {self.total_python_files}',
            f'Total lines (est.): {self.total_lines}',
            '', '## Top-level Modules',
        ]
        for sub in self.top_level_modules:
            lines.append(f'- {sub.name}: {sub.file_count} files — {sub.notes}')
        return '\n'.join(lines)


def build_port_manifest() -> PortManifest:
    # [OPT-5] TTL-based caching: avoid re-scanning filesystem every call
    cache_key = 'default'
    now = time.monotonic()
    cached = _manifest_cache.get(cache_key)
    if cached and (now - cached[0]) < _CACHE_TTL:
        return cached[1]

    src_root = Path(__file__).resolve().parent
    modules = []
    for item in sorted(src_root.iterdir()):
        if item.name.startswith('_'):
            continue
        if item.is_dir():
            py_count = sum(1 for _ in item.rglob('*.py'))
            modules.append(Subsystem(name=item.name, file_count=py_count, notes='directory'))
        elif item.suffix == '.py':
            modules.append(Subsystem(name=item.stem, file_count=1, notes='module'))
    total_files = sum(1 for _ in src_root.rglob('*.py'))
    total_lines = 0
    for py_file in src_root.rglob('*.py'):
        try:
            total_lines += len(py_file.read_text().splitlines())
        except Exception:
            pass
    manifest = PortManifest(top_level_modules=modules, total_python_files=total_files, total_lines=total_lines)
    _manifest_cache[cache_key] = (now, manifest)
    return manifest
