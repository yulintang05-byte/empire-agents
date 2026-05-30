"""
Test suite verifying that the optimized src_v2/ produces equivalent results
to the original src/ implementation, and that all optimizations work correctly.
"""
from __future__ import annotations

import sys
import unittest
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class TestCommandParity(unittest.TestCase):
    """Verify command operations produce identical results across v1 and v2."""

    def test_command_count_matches(self):
        from src.commands import PORTED_COMMANDS as v1_cmds
        from src_v2.commands import PORTED_COMMANDS as v2_cmds
        self.assertEqual(len(v1_cmds), len(v2_cmds))

    def test_command_names_match(self):
        from src.commands import command_names as v1_names
        from src_v2.commands import command_names as v2_names
        self.assertEqual(v1_names(), v2_names())

    def test_get_command_parity(self):
        from src.commands import get_command as v1_get
        from src_v2.commands import get_command as v2_get
        for name in ['help', 'commit', 'review', 'agents', 'nonexistent']:
            v1 = v1_get(name)
            v2 = v2_get(name)
            if v1 is None:
                self.assertIsNone(v2, f'v2 found {name} but v1 did not')
            else:
                self.assertIsNotNone(v2, f'v1 found {name} but v2 did not')
                self.assertEqual(v1.name, v2.name)
                self.assertEqual(v1.source_hint, v2.source_hint)

    def test_find_commands_parity(self):
        from src.commands import find_commands as v1_find
        from src_v2.commands import find_commands as v2_find
        for query in ['bash', 'agent', 'plugin', 'commit']:
            v1 = [(m.name, m.source_hint) for m in v1_find(query)]
            v2 = [(m.name, m.source_hint) for m in v2_find(query)]
            self.assertEqual(v1, v2, f'find_commands({query!r}) mismatch')

    def test_execute_command_parity(self):
        from src.commands import execute_command as v1_exec
        from src_v2.commands import execute_command as v2_exec
        v1 = v1_exec('help', 'test prompt')
        v2 = v2_exec('help', 'test prompt')
        self.assertEqual(v1.handled, v2.handled)
        self.assertEqual(v1.message, v2.message)


class TestToolParity(unittest.TestCase):
    """Verify tool operations produce identical results across v1 and v2."""

    def test_tool_count_matches(self):
        from src.tools import PORTED_TOOLS as v1_tools
        from src_v2.tools import PORTED_TOOLS as v2_tools
        self.assertEqual(len(v1_tools), len(v2_tools))

    def test_get_tool_parity(self):
        from src.tools import get_tool as v1_get
        from src_v2.tools import get_tool as v2_get
        for name in ['BashTool', 'AgentTool', 'GrepTool', 'nonexistent']:
            v1 = v1_get(name)
            v2 = v2_get(name)
            if v1 is None:
                self.assertIsNone(v2)
            else:
                self.assertIsNotNone(v2)
                self.assertEqual(v1.name, v2.name)

    def test_find_tools_parity(self):
        from src.tools import find_tools as v1_find
        from src_v2.tools import find_tools as v2_find
        for query in ['bash', 'agent', 'file', 'mcp']:
            v1 = [(m.name, m.source_hint) for m in v1_find(query)]
            v2 = [(m.name, m.source_hint) for m in v2_find(query)]
            self.assertEqual(v1, v2, f'find_tools({query!r}) mismatch')


class TestRoutingParity(unittest.TestCase):
    """Verify prompt routing produces equivalent results."""

    def test_route_prompt_returns_results(self):
        from src.runtime import PortRuntime as V1Runtime
        from src_v2.runtime import PortRuntime as V2Runtime
        v1 = V1Runtime()
        v2 = V2Runtime()
        for prompt in ['help with bash', 'edit file', 'search code']:
            v1_matches = v1.route_prompt(prompt, limit=5)
            v2_matches = v2.route_prompt(prompt, limit=5)
            # Both should return results
            self.assertGreater(len(v1_matches), 0, f'v1 no matches for {prompt!r}')
            self.assertGreater(len(v2_matches), 0, f'v2 no matches for {prompt!r}')
            # Same number of results
            self.assertEqual(len(v1_matches), len(v2_matches), f'Different count for {prompt!r}')

    def test_route_prompt_kinds_present(self):
        from src_v2.runtime import PortRuntime
        rt = PortRuntime()
        matches = rt.route_prompt('bash tool agent command', limit=5)
        kinds = {m.kind for m in matches}
        self.assertIn('command', kinds)
        self.assertIn('tool', kinds)


class TestQueryEngineParity(unittest.TestCase):
    """Verify query engine produces equivalent results."""

    def _cleanup(self):
        session_dir = ROOT / '.port_sessions'
        if session_dir.exists():
            shutil.rmtree(session_dir)

    def setUp(self):
        self._cleanup()

    def tearDown(self):
        self._cleanup()

    def test_submit_message_parity(self):
        from src.query_engine import QueryEnginePort as V1Engine
        from src_v2.query_engine import QueryEnginePort as V2Engine
        v1 = V1Engine.from_workspace()
        v2 = V2Engine.from_workspace()
        r1 = v1.submit_message('test', ('help',), ('BashTool',), ())
        r2 = v2.submit_message('test', ('help',), ('BashTool',), ())
        self.assertEqual(r1.stop_reason, r2.stop_reason)
        self.assertEqual(r1.matched_commands, r2.matched_commands)
        self.assertEqual(r1.matched_tools, r2.matched_tools)

    def test_max_turns_enforced(self):
        from src_v2.query_engine import QueryEnginePort, QueryEngineConfig
        engine = QueryEnginePort.from_workspace()
        engine.config = QueryEngineConfig(max_turns=2)
        r1 = engine.submit_message('turn 1')
        r2 = engine.submit_message('turn 2')
        r3 = engine.submit_message('turn 3')
        self.assertEqual(r1.stop_reason, 'completed')
        self.assertEqual(r3.stop_reason, 'max_turns_reached')

    def test_batch_submit(self):
        from src_v2.query_engine import QueryEnginePort
        engine = QueryEnginePort.from_workspace()
        results = engine.submit_batch(['prompt 1', 'prompt 2', 'prompt 3'])
        self.assertEqual(len(results), 3)
        for r in results:
            self.assertIn(r.stop_reason, ('completed', 'max_budget_reached'))


class TestTranscriptOptimization(unittest.TestCase):
    """Verify deque-backed transcript works correctly."""

    def test_deque_append_and_replay(self):
        from src_v2.transcript import TranscriptStore
        ts = TranscriptStore()
        for i in range(50):
            ts.append(f'msg-{i}')
        self.assertEqual(len(ts), 50)
        replayed = ts.replay()
        self.assertEqual(len(replayed), 50)
        self.assertEqual(replayed[0], 'msg-0')
        self.assertEqual(replayed[-1], 'msg-49')

    def test_deque_compact(self):
        from src_v2.transcript import TranscriptStore
        ts = TranscriptStore()
        for i in range(100):
            ts.append(f'msg-{i}')
        ts.compact(10)
        replayed = ts.replay()
        self.assertEqual(len(replayed), 10)
        self.assertEqual(replayed[0], 'msg-90')


class TestRegistryOptimization(unittest.TestCase):
    """Verify cached execution registry with dict lookups."""

    def test_registry_singleton(self):
        from src_v2.execution_registry import build_execution_registry
        r1 = build_execution_registry()
        r2 = build_execution_registry()
        self.assertIs(r1, r2)  # Same object due to lru_cache

    def test_registry_dict_lookup(self):
        from src_v2.execution_registry import build_execution_registry
        reg = build_execution_registry()
        cmd = reg.command('help')
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.name, 'help')
        tool = reg.tool('BashTool')
        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, 'BashTool')


class TestTokenEstimation(unittest.TestCase):
    """Verify byte-length token estimation produces reasonable results."""

    def test_estimation_produces_values(self):
        from src_v2.models import UsageSummary
        usage = UsageSummary(0, 0)
        usage = usage.add_turn('hello world', 'this is a response')
        self.assertGreater(usage.input_tokens, 0)
        self.assertGreater(usage.output_tokens, 0)

    def test_estimation_is_monotonic(self):
        from src_v2.models import UsageSummary
        usage = UsageSummary(0, 0)
        for i in range(10):
            prev = usage
            usage = usage.add_turn(f'prompt {i}', f'response {i}')
            self.assertGreater(usage.input_tokens, prev.input_tokens)
            self.assertGreater(usage.output_tokens, prev.output_tokens)


if __name__ == '__main__':
    unittest.main()
