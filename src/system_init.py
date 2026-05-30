from __future__ import annotations


def build_system_init_message(trusted: bool = False) -> str:
    lines = [
        'System initialized.',
        f'Trusted mode: {trusted}',
        'Port workspace ready.',
    ]
    return '\n'.join(lines)
