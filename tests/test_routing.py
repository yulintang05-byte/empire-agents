"""Unit tests for prompt routing and its inverted-index optimizations."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from claw_workers import PortRuntime  # noqa: E402
from claw_workers.routing import _build_routing_index, _resolve_token, _route_cached  # noqa: E402


class TestRouting(unittest.TestCase):
    def setUp(self):
        self.rt = PortRuntime()

    def test_returns_results(self):
        for prompt in ["help with bash", "edit file", "review commit"]:
            self.assertGreater(len(self.rt.route_prompt(prompt, limit=5)), 0, prompt)

    def test_respects_limit(self):
        self.assertLessEqual(len(self.rt.route_prompt("bash tool agent command file", 3)), 3)

    def test_both_kinds_present(self):
        matches = self.rt.route_prompt("bash tool agent command", limit=5)
        kinds = {m.kind for m in matches}
        self.assertIn("command", kinds)
        self.assertIn("tool", kinds)

    def test_scores_descending(self):
        matches = self.rt.route_prompt("help bash commit file agent", limit=10)
        # After the guaranteed one-of-each header, the remainder is score-ordered.
        rest = matches[2:]
        scores = [m.score for m in rest]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_empty_prompt(self):
        self.assertEqual(self.rt.route_prompt("", limit=5), [])

    def test_no_match_prompt(self):
        self.assertEqual(self.rt.route_prompt("zzzqqq wwww", limit=5), [])

    def test_route_cache_hit(self):
        _route_cached.cache_clear()
        self.rt.route_prompt("help with bash", limit=5)
        self.rt.route_prompt("help with bash", limit=5)
        info = _route_cached.cache_info()
        self.assertGreaterEqual(info.hits, 1)

    def test_inverted_index_shape(self):
        index = _build_routing_index()
        # Index keys are whole corpus tokens (e.g. 'commit', 'bashtool'); the
        # substring query 'bash' is resolved separately by _resolve_token.
        self.assertIn("commit", index)
        self.assertIn("bashtool", index)
        # Every entry is a (kind, idx) tuple.
        for entries in index.values():
            for kind, idx in entries:
                self.assertIn(kind, ("command", "tool"))
                self.assertIsInstance(idx, int)

    def test_resolve_token_substring(self):
        # "bash" should resolve to at least the BashTool entry.
        entries = _resolve_token("bash")
        self.assertTrue(any(kind == "tool" for kind, _ in entries))


if __name__ == "__main__":
    unittest.main()
