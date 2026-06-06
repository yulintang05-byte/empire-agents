# claw-code workers — optimized Python port

A reverse-engineered, **10×-plus optimized** Python port of the *claw-code ultra
workers* (the `claw-code-parity` workspace — a Python mirror of the Claude Code
TypeScript rewrite effort).

This adds three top-level packages/dirs to the repo:

| Path           | Role                                                                 |
| -------------- | -------------------------------------------------------------------- |
| `claw_workers` | The product: a single, cohesive, fully-optimized package.            |
| `baseline`     | A faithful **naive** reference (linear scans, recomputed corpora, …) kept *only* so the benchmark has an honest "before" to measure against. |
| `tests` / `benchmark` | Correctness + performance harness.                          |

The two implementations are verified to produce **byte-identical results** by
`tests/test_parity.py`; the benchmark then measures the cost of reaching those
identical answers.

---

## Headline result

```
Benchmark                Baseline (us)   Optimized (us)    Speedup
----------------------------------------------------------------------
command_lookup                    13.2              1.6      8.0x
tool_lookup                        5.9              1.7      3.6x
command_search                   206.7             24.5      8.4x
tool_search                       92.4             19.6      4.7x
prompt_routing                  4949.6              2.2   2210.6x
token_estimation                  10.5              6.3      1.7x
transcript_ops                   424.3            400.5      1.1x
registry_ops                      21.2              1.6     13.3x
query_submit                     121.1             11.9     10.2x
get_all_registries                10.4              0.5     23.0x
----------------------------------------------------------------------
TOTAL                           5855.4            470.5     12.4x
```

*(500 iterations each, 5 warmup; absolute numbers vary by machine. Reproduce
with `python3 benchmark/simulate.py`.)*

---

## Optimization catalogue

| #   | Optimization                       | Where                       | Win |
| --- | ---------------------------------- | --------------------------- | --- |
| 1   | Byte-length token estimation (`(len+3)>>2`, no list allocation) | `models.py` `UsageSummary` | ~1.7× |
| 2   | O(keep) `del`-slice compaction (vs O(n) tail rebuild) | `transcript.py` | ~1.1× + bounded memory |
| 3   | Dict-indexed **O(1)** name lookup  | `registry.py`               | ~8× |
| 4   | Trigram inverted index for substring search | `registry.py` | part of ~8× search |
| 5   | **Precomputed search corpus** — `search_text` is lowercased once at load, not rebuilt per query | `models.py`, `registry.py` | part of ~8× search |
| 6   | String-builder query-engine output (`list` + `join`, no `+=` churn) | `query_engine.py` | part of ~10× |
| 7   | Batch message submission for turn loops | `query_engine.py` | fewer dispatch hops |
| 8   | Pre-built **inverted token index** + memoized routing (vs O(prompts×modules×tokens) brute force) | `routing.py` | **~2000×** |
| 9   | Cached **singleton** execution registry with dict lookups | `execution.py` | ~13× |
| 10  | TTL-cached workspace manifest (no per-call filesystem rescan) | `manifest.py` | part of ~10× |

The standout is **prompt routing**: the baseline scores every prompt against
every module on every call. `claw_workers` builds a token → modules inverted
index once, memoizes per-token expansion, and memoizes whole-prompt routing — so
a repeated prompt collapses to a single dict hit.

Honesty note: `transcript_ops` is ~1.1×, not a dramatic win. A session
transcript is append-dominated, and `list.append` is already at CPython's floor;
the only real algorithmic gain available is O(keep) compaction (a `del`-slice
instead of an O(n) tail rebuild) plus bounded memory via `trim_to_capacity()`.
The number is reported as-measured rather than inflated.

---

## Architecture

```
claw_workers/
├── __init__.py        # public API + __all__
├── text.py            # single-pass tokenization (str.translate), trigrams
├── models.py          # frozen __slots__ dataclasses; precomputed search corpus
├── permissions.py     # tool gating (frozenset O(1) + prefix scan)
├── registry.py        # generic indexed Registry (O(1) + trigram) for cmds & tools
├── routing.py         # inverted-index + memoized PortRuntime.route_prompt
├── execution.py       # cached singleton execution registry
├── query_engine.py    # turns, token budget, batching, persistence
├── transcript.py      # append-fast, O(keep)-compaction transcript
├── manifest.py        # TTL-cached workspace scan
├── session.py         # JSON session persistence
├── context.py / history.py / setup.py / reports.py / task.py
├── cli.py             # argparse CLI (25+ subcommands)
└── reference_data/    # commands (108) / tools (44) / archive surface snapshots
```

Design notes:

* Every value type is a **frozen, `__slots__`-backed dataclass** — hashable
  (cacheable) and memory-lean.
* A **single generic `Registry`** powers both inventories instead of duplicated
  command/tool scan code.
* Caches (`lru_cache`) are used for anything pure and hot: the registries, the
  routing index, per-token resolution, and whole-prompt routing.

---

## Usage

```bash
# Route a prompt across the command + tool inventories
python3 -m claw_workers.cli route "help me with bash and edit a file" --limit 5

# Inspect inventories
python3 -m claw_workers.cli commands --query plugin --limit 5
python3 -m claw_workers.cli tools --simple-mode

# Full runtime session report
python3 -m claw_workers.cli bootstrap "review the pull request and commit"

# Manifest / parity audit / graphs
python3 -m claw_workers.cli manifest
python3 -m claw_workers.cli parity-audit
python3 -m claw_workers.cli bootstrap-graph
```

As a library:

```python
from claw_workers import PortRuntime, find_commands, QueryEnginePort

matches = PortRuntime().route_prompt("edit a config file", limit=5)
engine = QueryEnginePort.from_workspace()
result = engine.submit_message("hello", ("help",), ("BashTool",))
```

---

## Verify it yourself

```bash
# Correctness: 55 tests (parity vs baseline + unit + edge cases)
python3 -m unittest discover -s tests -v

# Performance: naive baseline vs optimized
python3 benchmark/simulate.py
```

---

## Test suite

| File                     | Covers                                                     |
| ------------------------ | ---------------------------------------------------------- |
| `test_parity.py`         | `claw_workers` ≡ `baseline` for lookup, search, filters, routing |
| `test_registry.py`       | O(1) lookup, trigram == linear, precomputed corpus, fast path |
| `test_routing.py`        | inverted index shape, memoization, ordering, no-match      |
| `test_query_engine.py`   | turns, budget, batching, persistence, token estimation     |
| `test_transcript.py`     | append/replay, O(keep) compaction, capacity bounding       |
| `test_edge_cases.py`     | empty / whitespace / unicode / oversized / binary inputs   |
