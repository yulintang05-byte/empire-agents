"""Parity: the optimized claw_workers must match the naive baseline exactly."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from baseline import naive  # noqa: E402
from claw_workers import (  # noqa: E402
    PortRuntime,
    command_names,
    find_commands,
    find_tools,
    get_command,
    get_commands,
    get_tool,
    get_tools,
)

LOOKUP_NAMES = ["help", "commit", "review", "agents", "BashTool", "AgentTool", "nonexistent"]
SEARCH_QUERIES = ["bash", "agent", "plugin", "commit", "file", "mcp", "skill", "review", "xyzzy"]


class TestRegistryParity(unittest.TestCase):
    def test_command_count(self):
        self.assertEqual(len(command_names()), len(naive.PORTED_COMMANDS))

    def test_command_names_match(self):
        self.assertEqual(command_names(), naive.command_names())

    def test_get_command_parity(self):
        for name in LOOKUP_NAMES:
            opt = get_command(name)
            base = naive.get_command(name)
            self.assertEqual(opt is None, base is None, name)
            if opt and base:
                self.assertEqual((opt.name, opt.source_hint), (base.name, base.source_hint))

    def test_get_tool_parity(self):
        for name in LOOKUP_NAMES:
            opt = get_tool(name)
            base = naive.get_tool(name)
            self.assertEqual(opt is None, base is None, name)
            if opt and base:
                self.assertEqual(opt.name, base.name)

    def test_find_commands_parity(self):
        for q in SEARCH_QUERIES:
            opt = [(m.name, m.source_hint) for m in find_commands(q, limit=10)]
            base = [(m.name, m.source_hint) for m in naive.find_commands(q, limit=10)]
            self.assertEqual(opt, base, f"find_commands({q!r})")

    def test_find_tools_parity(self):
        for q in SEARCH_QUERIES:
            opt = [(m.name, m.source_hint) for m in find_tools(q, limit=10)]
            base = [(m.name, m.source_hint) for m in naive.find_tools(q, limit=10)]
            self.assertEqual(opt, base, f"find_tools({q!r})")

    def test_get_commands_filter_parity(self):
        for plug in (True, False):
            for skill in (True, False):
                opt = [m.name for m in get_commands(plug, skill)]
                base = [m.name for m in naive.get_commands(plug, skill)]
                self.assertEqual(opt, base, f"plugins={plug} skills={skill}")

    def test_get_tools_filter_parity(self):
        for simple in (True, False):
            for mcp in (True, False):
                opt = [m.name for m in get_tools(simple_mode=simple, include_mcp=mcp)]
                base = [m.name for m in naive.get_tools(simple_mode=simple, include_mcp=mcp)]
                self.assertEqual(opt, base, f"simple={simple} mcp={mcp}")


class TestRoutingParity(unittest.TestCase):
    PROMPTS = [
        "help me with bash commands",
        "search for files using glob tool",
        "edit a configuration file",
        "review pull request changes",
        "deploy to remote server via ssh",
        "completely unrelated zzz query",
    ]

    def test_route_prompt_parity(self):
        opt_rt = PortRuntime()
        base_rt = naive.PortRuntime()
        for prompt in self.PROMPTS:
            opt = [(m.kind, m.name, m.score) for m in opt_rt.route_prompt(prompt, limit=5)]
            base = [(m.kind, m.name, m.score) for m in base_rt.route_prompt(prompt, limit=5)]
            self.assertEqual(opt, base, f"route({prompt!r})")


if __name__ == "__main__":
    unittest.main()
