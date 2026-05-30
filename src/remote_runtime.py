from __future__ import annotations
from dataclasses import dataclass


@dataclass
class RemoteModeReport:
    mode: str
    target: str
    status: str = 'simulated'

    def as_text(self) -> str:
        return f'[{self.mode}] target={self.target} status={self.status}'


def run_remote_mode(target: str) -> RemoteModeReport:
    return RemoteModeReport(mode='remote', target=target)


def run_ssh_mode(target: str) -> RemoteModeReport:
    return RemoteModeReport(mode='ssh', target=target)


def run_teleport_mode(target: str) -> RemoteModeReport:
    return RemoteModeReport(mode='teleport', target=target)
