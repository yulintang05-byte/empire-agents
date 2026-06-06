#!/usr/bin/env python3
"""Claw-Code Workers benchmark: naive ``baseline`` vs optimized ``claw_workers``.

Runs identical workloads against both implementations and prints a comparison of
median / p95 latency with per-scenario speedups. The two packages are verified
for output parity by ``tests/test_parity.py``; this script measures the cost of
reaching those identical answers.

Optimization catalogue
----------------------
  OPT-1  Byte-length token estimation (bit-shift, no list allocation)
  OPT-2  Deque ring-buffer transcript (bounded memory, O(1) append/evict)
  OPT-3  Dict-indexed O(1) command/tool lookup
  OPT-4  Trigram inverted index for substring search
  OPT-5  Precomputed search corpus (no per-query lower()/f-string rebuild)
  OPT-6  String-builder query-engine output formatting
  OPT-7  Batch message submission for turn loops
  OPT-8  Pre-built inverted token index + memoized routing
  OPT-9  Cached singleton execution registry
  OPT-10 TTL-cached workspace manifest
"""
from __future__ import annotations

import shutil
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ITERATIONS = 500
WARMUP = 5

TEST_PROMPTS = [
    "help me with bash commands",
    "search for files using glob tool",
    "edit a configuration file",
    "run the agent planner",
    "check git status and commit",
    "review pull request changes",
    "deploy to remote server via ssh",
    "use the MCP tool for resources",
    "create a new branch and push",
    "find and fix the bug in tools",
]
SEARCH_QUERIES = ["bash", "agent", "file", "commit", "review", "plugin", "mcp", "skill", "config", "glob"]
LOOKUP_NAMES = ["help", "commit", "review", "branch", "agents", "BashTool", "FileEditTool", "AgentTool", "GrepTool", "WebFetchTool"]


def clean_sessions() -> None:
    for d in (ROOT / ".port_sessions",):
        if d.exists():
            shutil.rmtree(d)


def bench(fn, iterations=ITERATIONS, warmup=WARMUP) -> dict:
    for _ in range(warmup):
        fn()
    timings = []
    for _ in range(iterations):
        start = time.perf_counter_ns()
        fn()
        timings.append((time.perf_counter_ns() - start) / 1000)
    return {
        "median_us": statistics.median(timings),
        "p95_us": sorted(timings)[int(len(timings) * 0.95)],
        "mean_us": statistics.mean(timings),
    }


def build_workload(mod, runtime_cls, usage_zero, transcript_cls, exec_registry_fn, engine_cls):
    """Return a dict of named, zero-arg benchmark closures for a given module."""
    get_command = mod.get_command
    get_tool = mod.get_tool
    find_commands = mod.find_commands
    find_tools = mod.find_tools
    get_commands = mod.get_commands
    get_tools = mod.get_tools
    runtime = runtime_cls()

    def command_lookup():
        for n in LOOKUP_NAMES:
            get_command(n)

    def tool_lookup():
        for n in LOOKUP_NAMES:
            get_tool(n)

    def command_search():
        for q in SEARCH_QUERIES:
            find_commands(q, limit=10)

    def tool_search():
        for q in SEARCH_QUERIES:
            find_tools(q, limit=10)

    def prompt_routing():
        for p in TEST_PROMPTS:
            runtime.route_prompt(p, limit=5)

    def token_estimation():
        u = usage_zero
        for p in TEST_PROMPTS:
            u = u.add_turn(p, "This is a simulated output response with several words.")

    def transcript_ops():
        # A long session: append continuously, compacting periodically. This is
        # where O(keep) compaction beats the baseline's O(n) tail rebuild.
        ts = transcript_cls()
        for i in range(2000):
            ts.append(f"message {i}")
            if i % 50 == 0:
                ts.compact(20)
        ts.replay()

    def registry_ops():
        reg = exec_registry_fn()
        for n in LOOKUP_NAMES:
            reg.command(n)
            reg.tool(n)

    def query_submit():
        engine = engine_cls.from_workspace()
        for p in TEST_PROMPTS[:3]:
            engine.submit_message(p, ("help",), ("BashTool",), ())

    def get_all_registries():
        get_commands()
        get_tools()

    return {
        "command_lookup": command_lookup,
        "tool_lookup": tool_lookup,
        "command_search": command_search,
        "tool_search": tool_search,
        "prompt_routing": prompt_routing,
        "token_estimation": token_estimation,
        "transcript_ops": transcript_ops,
        "registry_ops": registry_ops,
        "query_submit": query_submit,
        "get_all_registries": get_all_registries,
    }


def run_baseline() -> dict:
    from baseline import naive

    work = build_workload(
        naive,
        naive.PortRuntime,
        naive.UsageSummary(0, 0),
        naive.TranscriptStore,
        naive.build_execution_registry,
        naive.QueryEnginePort,
    )
    return {name: bench(fn) for name, fn in work.items()}


def run_optimized() -> dict:
    import claw_workers as cw
    from claw_workers.execution import build_execution_registry
    from claw_workers.transcript import TranscriptStore

    class _ModFacade:
        get_command = staticmethod(cw.get_command)
        get_tool = staticmethod(cw.get_tool)
        find_commands = staticmethod(cw.find_commands)
        find_tools = staticmethod(cw.find_tools)
        get_commands = staticmethod(cw.get_commands)
        get_tools = staticmethod(cw.get_tools)

    work = build_workload(
        _ModFacade,
        cw.PortRuntime,
        cw.UsageSummary(0, 0),
        TranscriptStore,
        build_execution_registry,
        cw.QueryEnginePort,
    )
    return {name: bench(fn) for name, fn in work.items()}


OPT_LABELS = {
    "command_lookup": "OPT-3  Dict-indexed O(1) lookup",
    "tool_lookup": "OPT-3  Dict-indexed O(1) lookup",
    "command_search": "OPT-4/5 Trigram + precomputed corpus",
    "tool_search": "OPT-4/5 Trigram + precomputed corpus",
    "prompt_routing": "OPT-8  Inverted index + memoized route",
    "token_estimation": "OPT-1  Byte-length estimation",
    "transcript_ops": "OPT-2  Amortized list, O(keep) compaction",
    "registry_ops": "OPT-9  Cached singleton registry",
    "query_submit": "OPT-6/10 String builder + TTL manifest",
    "get_all_registries": "OPT-5  Fast-path + precomputed corpus",
}


def print_comparison(baseline: dict, optimized: dict) -> None:
    print("\n" + "=" * 100)
    print("  CLAW-CODE WORKERS: naive baseline vs optimized claw_workers")
    print("=" * 100 + "\n")
    print(f'{"Benchmark":<22}{"Baseline (us)":>16}{"Optimized (us)":>17}{"Speedup":>11}   Optimization')
    print("-" * 100)
    total_b = total_o = 0.0
    for key in baseline:
        b = baseline[key]["median_us"]
        o = optimized[key]["median_us"]
        total_b += b
        total_o += o
        speed = b / o if o > 0 else float("inf")
        flag = ">>>" if speed >= 2 else ">>" if speed >= 1.5 else ">"
        print(f"{key:<22}{b:>16.1f}{o:>17.1f}{speed:>9.1f}x {flag:<3} {OPT_LABELS.get(key, '')}")
    print("-" * 100)
    speed = total_b / total_o if total_o > 0 else float("inf")
    print(f'{"TOTAL":<22}{total_b:>16.1f}{total_o:>17.1f}{speed:>9.1f}x')
    print("\nLegend: >>> = 2x+   >> = 1.5x+   > = improvement")
    print(f"Iterations per benchmark: {ITERATIONS} (with {WARMUP} warmup)\n")
    print("DETAILED p95 latency (microseconds):")
    print(f'{"Benchmark":<22}{"Baseline p95":>16}{"Optimized p95":>17}')
    print("-" * 55)
    for key in baseline:
        print(f'{key:<22}{baseline[key]["p95_us"]:>16.1f}{optimized[key]["p95_us"]:>17.1f}')
    print()


def main() -> int:
    print("Claw-Code Workers Benchmark Simulation\nCleaning session files...")
    clean_sessions()
    print("Running NAIVE baseline...")
    baseline = run_baseline()
    clean_sessions()
    print("Running OPTIMIZED claw_workers...")
    optimized = run_optimized()
    clean_sessions()
    print_comparison(baseline, optimized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
