"""src/littrans/utils/bench.py — Benchmark instrumentation."""
from __future__ import annotations
import time
import functools
import json
from pathlib import Path
from contextlib import contextmanager

BENCH_LOG = Path(__file__).resolve().parents[3] / "data" / "bench.jsonl"


@contextmanager
def measure(label: str, **meta):
    t0 = time.perf_counter()
    try:
        yield
    finally:
        dt = time.perf_counter() - t0
        BENCH_LOG.parent.mkdir(parents=True, exist_ok=True)
        with BENCH_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"label": label, "ms": round(dt * 1000, 2), **meta}) + "\n")


def timed(label: str):
    def deco(fn):
        @functools.wraps(fn)
        def wrap(*a, **kw):
            with measure(label):
                return fn(*a, **kw)
        return wrap
    return deco
