"""src/littrans/utils/retry_utils.py — Unified retry decorator.

Pattern after tenacity (jd/tenacity). HTTP codes after Scrapy RetryMiddleware.
No external deps — stdlib only.
"""
from __future__ import annotations

import asyncio
import time
import random
import functools
import re
from dataclasses import dataclass
from typing import Callable

# Scrapy-standard retriable HTTP codes + Gemini/Cloudflare extras
RETRIABLE_HTTP = frozenset({408, 429, 500, 502, 503, 504, 522, 524})

RATE_LIMIT_MARKERS = (
    "429", "rate_limit", "rate limit", "RATE_LIMIT", "RESOURCE_EXHAUSTED",
    "quota", "too many requests", "overloaded", "529",
)
NETWORK_MARKERS = (
    "connection", "timeout", "timed out", "reset by peer", "connection reset",
    "remote end closed", "connection aborted", "connection refused",
    "SSL", "EOF", "dns", "network", "socket",
    "10060", "10061", "winerror", "connecttimeout", "readtimeout",
    "broken pipe",
)

_RETRY_DELAY_RE = re.compile(r"retry_delay\s*\{[^}]*seconds:\s*(\d+)", re.I)


def parse_retry_after(err: BaseException) -> float | None:
    """Extract Gemini 429 embedded 'retry_delay { seconds: N }'. Return N or None."""
    m = _RETRY_DELAY_RE.search(str(err))
    return float(m.group(1)) if m else None


def is_rate_limit(err: BaseException) -> bool:
    s = str(err).lower()
    return any(m.lower() in s for m in RATE_LIMIT_MARKERS)


def is_network(err: BaseException) -> bool:
    s = str(err).lower()
    return any(m.lower() in s for m in NETWORK_MARKERS)


def is_retriable(err: BaseException) -> bool:
    code = getattr(err, "status_code", None) or getattr(err, "code", None)
    if code in RETRIABLE_HTTP:
        return True
    return is_rate_limit(err) or is_network(err)


@dataclass
class Backoff:
    base: float = 1.0      # initial wait (seconds)
    cap: float = 60.0      # max wait
    factor: float = 2.0    # exponential multiplier
    jitter: float = 0.2    # ±jitter fraction

    def wait(self, attempt: int, hint: float | None = None) -> float:
        """Return sleep time for given attempt. hint = server-provided delay."""
        if hint is not None:
            return max(hint, 0.5)
        raw = min(self.cap, self.base * (self.factor ** attempt))
        j = raw * self.jitter * (random.random() * 2 - 1)
        return max(0.5, raw + j)


def with_retry(
    *,
    max_attempts: int = 5,
    retry_on: Callable[[BaseException], bool] = is_retriable,
    backoff: Backoff | None = None,
    on_retry: Callable[[int, BaseException, float], None] | None = None,
):
    """Decorator — retry sync or async function on retriable errors.

    Usage:
        @with_retry(max_attempts=5, backoff=Backoff(base=2.0, cap=60.0))
        def my_fn(...): ...

        @with_retry(max_attempts=4)
        async def my_async_fn(...): ...
    """
    bo = backoff or Backoff()

    def deco(fn):
        if asyncio.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def awrap(*a, **kw):
                for attempt in range(max_attempts):
                    try:
                        return await fn(*a, **kw)
                    except BaseException as e:
                        if isinstance(e, asyncio.CancelledError):
                            raise
                        if attempt == max_attempts - 1 or not retry_on(e):
                            raise
                        wait = bo.wait(attempt, parse_retry_after(e))
                        if on_retry:
                            on_retry(attempt, e, wait)
                        await asyncio.sleep(wait)
            return awrap

        @functools.wraps(fn)
        def swrap(*a, **kw):
            for attempt in range(max_attempts):
                try:
                    return fn(*a, **kw)
                except BaseException as e:
                    if attempt == max_attempts - 1 or not retry_on(e):
                        raise
                    wait = bo.wait(attempt, parse_retry_after(e))
                    if on_retry:
                        on_retry(attempt, e, wait)
                    time.sleep(wait)
        return swrap

    return deco
