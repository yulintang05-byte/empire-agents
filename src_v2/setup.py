from __future__ import annotations
import platform
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class WorkspaceSetup:
    python_version: str
    implementation: str
    platform_name: str
    test_command: str

    def startup_steps(self) -> list[str]:
        return [
            f'Detected Python {self.python_version}',
            f'Platform: {self.platform_name}',
            f'Test runner: {self.test_command}',
        ]


@dataclass
class SetupReport:
    setup: WorkspaceSetup
    trusted: bool = False

    def as_markdown(self) -> str:
        lines = [
            '# Setup Report', '',
            f'- Python: {self.setup.python_version} ({self.setup.implementation})',
            f'- Platform: {self.setup.platform_name}',
            f'- Test command: {self.setup.test_command}',
            f'- Trusted: {self.trusted}',
            '', '## Startup Steps',
        ]
        lines.extend(f'- {step}' for step in self.setup.startup_steps())
        return '\n'.join(lines)


def run_setup(trusted: bool = False) -> SetupReport:
    setup = WorkspaceSetup(
        python_version=platform.python_version(),
        implementation=platform.python_implementation(),
        platform_name=platform.system(),
        test_command='python -m unittest',
    )
    return SetupReport(setup=setup, trusted=trusted)
