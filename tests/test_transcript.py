"""Unit tests for the deque-backed bounded transcript."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from claw_workers import TranscriptStore  # noqa: E402


class TestTranscript(unittest.TestCase):
    def test_append_and_replay(self):
        ts = TranscriptStore()
        for i in range(50):
            ts.append(f"msg-{i}")
        self.assertEqual(len(ts), 50)
        replay = ts.replay()
        self.assertEqual(replay[0], "msg-0")
        self.assertEqual(replay[-1], "msg-49")

    def test_compact_keeps_last(self):
        ts = TranscriptStore()
        for i in range(100):
            ts.append(f"msg-{i}")
        ts.compact(10)
        replay = ts.replay()
        self.assertEqual(len(replay), 10)
        self.assertEqual(replay[0], "msg-90")
        self.assertEqual(replay[-1], "msg-99")

    def test_trim_to_capacity_bounds_memory(self):
        ts = TranscriptStore(capacity=8)
        for i in range(1000):
            ts.append(f"msg-{i}")
        ts.trim_to_capacity()
        # Keeps exactly the most recent `capacity` entries.
        self.assertEqual(len(ts), 8)
        self.assertEqual(ts.replay()[0], "msg-992")
        self.assertEqual(ts.replay()[-1], "msg-999")

    def test_append_clears_flushed(self):
        ts = TranscriptStore()
        ts.flush()
        self.assertTrue(ts.flushed)
        ts.append("x")
        self.assertFalse(ts.flushed)

    def test_entries_is_list_copy(self):
        ts = TranscriptStore()
        ts.append("a")
        snapshot = ts.entries
        snapshot.append("mutation")
        self.assertEqual(len(ts), 1)  # internal state untouched


if __name__ == "__main__":
    unittest.main()
