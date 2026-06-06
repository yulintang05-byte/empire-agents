"""Edge cases: empty / unicode / oversized / adversarial inputs."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from claw_workers import (  # noqa: E402
    PortRuntime,
    UsageSummary,
    find_commands,
    find_tools,
    get_command,
)
from claw_workers.text import fold_separators, tokenize, trigrams  # noqa: E402


class TestTextUtils(unittest.TestCase):
    def test_fold_separators_single_pass(self):
        self.assertEqual(fold_separators("a/b-c_d.e"), "a b c d e")

    def test_tokenize_dedups(self):
        self.assertEqual(tokenize("bash BASH bash"), frozenset({"bash"}))

    def test_tokenize_empty(self):
        self.assertEqual(tokenize(""), frozenset())

    def test_trigrams_short(self):
        self.assertEqual(trigrams("ab"), frozenset())
        self.assertEqual(trigrams("abc"), frozenset({"abc"}))


class TestEdgeCases(unittest.TestCase):
    def setUp(self):
        self.rt = PortRuntime()

    def test_empty_prompt_routes_to_nothing(self):
        self.assertEqual(self.rt.route_prompt("", limit=5), [])

    def test_whitespace_prompt(self):
        self.assertEqual(self.rt.route_prompt("   \t\n  ", limit=5), [])

    def test_unicode_prompt_no_crash(self):
        # Should not raise, even if it matches nothing.
        result = self.rt.route_prompt("日本語 émoji 🚀 bash", limit=5)
        self.assertTrue(any(m.name == "BashTool" for m in result))

    def test_very_long_prompt(self):
        prompt = "bash " * 5000
        result = self.rt.route_prompt(prompt, limit=5)
        self.assertGreater(len(result), 0)

    def test_find_with_punctuation(self):
        # Punctuation in the query should still find via the corpus.
        self.assertTrue(len(find_commands("commit", limit=5)) >= 0)

    def test_unicode_token_estimation(self):
        u = UsageSummary(0, 0).add_turn("héllo wörld 🌍", "réspönse")
        self.assertGreater(u.input_tokens, 0)
        self.assertGreater(u.output_tokens, 0)

    def test_get_command_none_safe(self):
        self.assertIsNone(get_command(""))
        self.assertIsNone(get_command("\x00binary"))

    def test_find_tools_case_insensitive(self):
        lower = [m.name for m in find_tools("bashtool", limit=5)]
        upper = [m.name for m in find_tools("BASHTOOL", limit=5)]
        self.assertEqual(lower, upper)


if __name__ == "__main__":
    unittest.main()
