"""Naive reference implementation of the claw-code workers.

This package exists purely so the benchmark has an honest, unoptimized point of
comparison. It mirrors the *original* claw-code-parity behaviour: linear scans,
search corpora rebuilt on every query, ``split()``-based token counting, a fresh
registry per call, per-call manifest rescans and brute-force O(n*m) routing.

Do not build on this — it is the "before" picture. The real package is
``claw_workers``.
"""
