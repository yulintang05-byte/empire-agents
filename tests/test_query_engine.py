"""Unit tests for the query engine, transcript, and token estimation."""
from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from claw_workers import QueryEngineConfig, QueryEnginePort, UsageSummary  # noqa: E402
from claw_workers.execution import build_execution_registry  # noqa: E402


class TestQueryEngine(unittest.TestCase):
    def _cleanup(self):
        d = ROOT / ".port_sessions"
        if d.exists():
            shutil.rmtree(d)

    def setUp(self):
        self._cleanup()

    def tearDown(self):
        self._cleanup()

    def test_submit_completes(self):
        engine = QueryEnginePort.from_workspace()
        r = engine.submit_message("test", ("help",), ("BashTool",), ())
        self.assertEqual(r.stop_reason, "completed")
        self.assertEqual(r.matched_commands, ("help",))
        self.assertEqual(r.matched_tools, ("BashTool",))
        self.assertIn("Processed: test", r.output)

    def test_max_turns_enforced(self):
        engine = QueryEnginePort.from_workspace()
        engine.config = QueryEngineConfig(max_turns=2)
        self.assertEqual(engine.submit_message("t1").stop_reason, "completed")
        engine.submit_message("t2")
        self.assertEqual(engine.submit_message("t3").stop_reason, "max_turns_reached")

    def test_batch_submit(self):
        engine = QueryEnginePort.from_workspace()
        results = engine.submit_batch(["p1", "p2", "p3"])
        self.assertEqual(len(results), 3)
        self.assertTrue(all(r.stop_reason == "completed" for r in results))

    def test_batch_stops_on_max_turns(self):
        engine = QueryEnginePort.from_workspace()
        engine.config = QueryEngineConfig(max_turns=2)
        results = engine.submit_batch(["p1", "p2", "p3", "p4"])
        self.assertEqual(len(results), 3)  # 2 ok + 1 that trips max_turns, then stop
        self.assertEqual(results[-1].stop_reason, "max_turns_reached")

    def test_persist_and_flush(self):
        engine = QueryEnginePort.from_workspace()
        engine.submit_message("hello")
        path = engine.persist_session()
        self.assertTrue(Path(path).exists())
        self.assertTrue(engine.transcript_store.flushed)

    def test_registry_singleton(self):
        self.assertIs(build_execution_registry(), build_execution_registry())

    def test_registry_dict_lookup(self):
        reg = build_execution_registry()
        self.assertEqual(reg.command("help").name, "help")
        self.assertEqual(reg.tool("BashTool").name, "BashTool")
        self.assertIsNone(reg.command("nope"))


class TestTokenEstimation(unittest.TestCase):
    def test_produces_values(self):
        u = UsageSummary(0, 0).add_turn("hello world", "a response here")
        self.assertGreater(u.input_tokens, 0)
        self.assertGreater(u.output_tokens, 0)

    def test_monotonic(self):
        u = UsageSummary(0, 0)
        for i in range(10):
            prev = u
            u = u.add_turn(f"prompt {i}", f"response {i}")
            self.assertGreater(u.input_tokens, prev.input_tokens)
            self.assertGreater(u.output_tokens, prev.output_tokens)

    def test_total(self):
        u = UsageSummary(5, 7)
        self.assertEqual(u.total_tokens, 12)


if __name__ == "__main__":
    unittest.main()
