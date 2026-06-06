"""Unit tests for the indexed registry and its optimizations."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from claw_workers import command_registry, find_commands, get_command, get_commands, tool_registry  # noqa: E402
from claw_workers.registry import Registry  # noqa: E402


class TestRegistry(unittest.TestCase):
    def test_singleton_cached(self):
        self.assertIs(command_registry(), command_registry())
        self.assertIs(tool_registry(), tool_registry())

    def test_o1_lookup_correct(self):
        self.assertEqual(get_command("help").name, "help")
        self.assertIsNone(get_command("does-not-exist"))

    def test_precomputed_search_text(self):
        # Every module must carry a non-empty, lowercased corpus.
        for m in command_registry():
            self.assertTrue(m.search_text)
            self.assertEqual(m.search_text, m.search_text.lower())
            self.assertIn(m.name.lower(), m.search_text)

    def test_trigram_find_matches_linear(self):
        reg = command_registry()
        for q in ["plugin", "skill", "commit", "help"]:
            trigram = list(reg.find(q, limit=100))
            linear = [m for m in reg if q.lower() in m.search_text]
            self.assertEqual(trigram, linear, q)

    def test_find_respects_limit(self):
        self.assertLessEqual(len(find_commands("plugin", limit=5)), 5)

    def test_find_short_query_fallback(self):
        # Queries shorter than a trigram still work via the linear fallback.
        results = find_commands("a", limit=3)
        self.assertTrue(all("a" in m.search_text for m in results))

    def test_find_empty_query(self):
        self.assertEqual(find_commands("", limit=5), ())

    def test_find_absent_query(self):
        self.assertEqual(find_commands("qqzzxx", limit=5), ())

    def test_fast_path_returns_same_object(self):
        # The no-filter path returns the cached tuple without rebuilding it.
        self.assertIs(get_commands(True, True), command_registry().modules)

    def test_generic_registry_construction(self):
        from claw_workers.models import PortingModule

        mods = [PortingModule.create("Alpha", "src/a.ts", "demo one"),
                PortingModule.create("Beta", "src/b.ts", "demo two")]
        reg = Registry(mods, label="Demo")
        self.assertEqual(len(reg), 2)
        self.assertEqual(reg.get("Alpha").name, "Alpha")
        self.assertEqual([m.name for m in reg.find("demo", 10)], ["Alpha", "Beta"])


if __name__ == "__main__":
    unittest.main()
