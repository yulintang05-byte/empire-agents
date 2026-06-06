"""Shared, allocation-frugal text utilities.

Centralising tokenisation here means every subsystem (registry search, prompt
routing, manifest scanning) shares one fast, correct implementation instead of
re-deriving ad-hoc ``str.replace`` chains.

Key upgrades over the naive baseline
------------------------------------
* **Single-pass separator folding** via :func:`str.translate` with a prebuilt
  translation table, replacing four chained ``str.replace`` calls (each of which
  allocates a fresh intermediate string).
* **Frozenset tokens** so callers can do O(1) membership tests and cache results
  with ``functools.lru_cache`` (frozensets are hashable; sets are not).
"""
from __future__ import annotations

from functools import lru_cache

# Characters that should be treated as token boundaries. Folding them to spaces
# in one C-level pass is dramatically cheaper than chained ``replace`` calls.
_SEPARATORS = "/-_.\t\n\r,:;()[]{}<>\"'`|"
_FOLD_TABLE = str.maketrans({ch: " " for ch in _SEPARATORS})


def normalize(text: str) -> str:
    """Lower-case ``text`` once, for reuse as a search corpus."""
    return text.lower()


def fold_separators(text: str) -> str:
    """Replace every separator character with a space in a single pass."""
    return text.translate(_FOLD_TABLE)


def tokenize(text: str) -> frozenset[str]:
    """Split ``text`` into a frozenset of lower-cased, separator-free tokens."""
    return frozenset(fold_separators(text.lower()).split())


@lru_cache(maxsize=4096)
def tokenize_cached(text: str) -> frozenset[str]:
    """Memoised :func:`tokenize` for hot, repeated inputs (e.g. prompts)."""
    return tokenize(text)


def trigrams(text: str) -> frozenset[str]:
    """Return the set of 3-character shingles of ``text`` (already normalised)."""
    if len(text) < 3:
        return frozenset()
    return frozenset(text[i : i + 3] for i in range(len(text) - 2))
