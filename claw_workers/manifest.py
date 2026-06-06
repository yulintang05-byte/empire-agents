"""Workspace manifest with TTL-cached filesystem scanning.

Scanning the source tree on every call (as the baseline does) is wasteful when
the tree changes rarely. A short TTL cache amortises the walk across the many
manifest reads a single CLI invocation performs, while still picking up changes
within ``_CACHE_TTL`` seconds.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from .models import Subsystem

_PACKAGE_ROOT = Path(__file__).resolve().parent
_CACHE_TTL = 10.0
_cache: dict[str, tuple[float, "PortManifest"]] = {}


@dataclass(slots=True)
class PortManifest:
    top_level_modules: list[Subsystem] = field(default_factory=list)
    total_python_files: int = 0
    total_lines: int = 0

    def to_markdown(self) -> str:
        lines = [
            "# Port Manifest",
            "",
            f"Total Python files: {self.total_python_files}",
            f"Total lines (est.): {self.total_lines}",
            "",
            "## Top-level Modules",
        ]
        lines.extend(
            f"- {s.name}: {s.file_count} files — {s.notes}" for s in self.top_level_modules
        )
        return "\n".join(lines)


def _scan() -> PortManifest:
    modules: list[Subsystem] = []
    total_files = 0
    total_lines = 0
    for item in sorted(_PACKAGE_ROOT.iterdir()):
        if item.name.startswith("_") or item.name == "reference_data":
            continue
        if item.is_dir():
            py_count = sum(1 for _ in item.rglob("*.py"))
            modules.append(Subsystem(name=item.name, file_count=py_count, notes="directory"))
        elif item.suffix == ".py":
            modules.append(Subsystem(name=item.stem, file_count=1, notes="module"))
    for py_file in _PACKAGE_ROOT.rglob("*.py"):
        total_files += 1
        try:
            total_lines += len(py_file.read_text().splitlines())
        except OSError:
            pass
    return PortManifest(
        top_level_modules=modules, total_python_files=total_files, total_lines=total_lines
    )


def build_port_manifest() -> PortManifest:
    now = time.monotonic()
    cached = _cache.get("default")
    if cached is not None and (now - cached[0]) < _CACHE_TTL:
        return cached[1]
    manifest = _scan()
    _cache["default"] = (now, manifest)
    return manifest
