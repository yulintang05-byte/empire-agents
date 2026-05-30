from __future__ import annotations
from dataclasses import dataclass


@dataclass
class ModeReport:
    mode: str
    target: str
    status: str = 'simulated'

    def as_text(self) -> str:
        return f'[{self.mode}] target={self.target} status={self.status}'


def run_direct_connect(target: str) -> ModeReport:
    return ModeReport(mode='direct-connect', target=target)


def run_deep_link(target: str) -> ModeReport:
    return ModeReport(mode='deep-link', target=target)
