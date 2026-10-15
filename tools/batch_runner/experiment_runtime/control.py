"""Flow control: AIMD concurrency per model, backoff, and the global credential gate."""

from __future__ import annotations

import random
import sys
import threading
import time
import traceback
from typing import Callable

from .util import LOG, fmt_duration, fmt_interval, utc_now_iso


def backoff_delay(attempt: int, base: float, cap: float, rng: random.Random) -> float:
    """Exponential backoff with 'equal jitter' (half fixed, half random), capped."""
    ceiling = min(cap, base * (2 ** max(0, attempt - 1)))
    return ceiling / 2 + rng.uniform(0, ceiling / 2)


class AIMDLimiter:
    """Per-model concurrency: halve on throttling, +1 after N consecutive successes.

    acquire() returns the current epoch. A throttle halves the limit only if
    the throttled call started in the current epoch, so a burst of in-flight
    calls throttled together counts as one congestion event.
    """

    def __init__(self, max_limit: int, initial: int | None = None, increase_after: int = 10, min_limit: int = 1):
        if max_limit < 1:
            raise ValueError("max_limit must be >= 1")
        self.max_limit = max_limit
        self.min_limit = max(1, min(min_limit, max_limit))
        self.limit = max(self.min_limit, min(max_limit, initial if initial is not None else max_limit))
        self.increase_after = max(1, increase_after)
        self.in_flight = 0
        self.successes = 0
        self.epoch = 0
        self.decreases = 0
        self.increases = 0
        self._cond = threading.Condition()

    def acquire(self, stop: threading.Event | None = None, poll: float = 0.25) -> int | None:
        with self._cond:
            while self.in_flight >= self.limit:
                if stop is not None and stop.is_set():
                    return None
                self._cond.wait(poll)
            if stop is not None and stop.is_set():
                return None
            self.in_flight += 1
            return self.epoch

    def release(self, token: int, outcome: str) -> None:
        """outcome: 'success', 'throttle' or 'neutral'."""
        with self._cond:
            self.in_flight = max(0, self.in_flight - 1)
            if outcome == "success":
                self.successes += 1
                if self.successes >= self.increase_after:
                    self.successes = 0
                    if self.limit < self.max_limit:
                        self.limit += 1
                        self.increases += 1
            elif outcome == "throttle":
                self.successes = 0
                if token == self.epoch:
                    self.limit = max(self.min_limit, self.limit // 2)
                    self.epoch += 1
                    self.decreases += 1
            self._cond.notify_all()


class Stopped(Exception):
    pass


class CredentialTimeout(Exception):
    pass


class CredentialGate:
    """Global pause when credentials fail.

    While paused nobody calls the model except one 'canary' every
    ``retry_interval`` seconds, which retries its own real request (after
    ``on_canary``, normally backend.reset()). Any non-credential answer to
    the canary reopens the gate for every model.
    """

    def __init__(self, retry_interval: float = 300.0, max_wait: float = 86400.0, hint: str = "run mwinit",
                 clock: Callable[[], float] = time.monotonic, on_canary: Callable[[], None] | None = None):
        self.retry_interval = retry_interval
        self.max_wait = max_wait
        self.hint = hint
        self.clock = clock
        self.on_canary = on_canary
        self.paused = False
        self.paused_since = 0.0
        self.paused_since_utc: str | None = None
        self.next_probe = 0.0
        self.canary_out = False
        self.pauses = 0
        self.canaries = 0
        self._cond = threading.Condition()

    def banner(self) -> str:
        return f"CREDENTIALS FAILED — {self.hint}; runner waits and retries every {fmt_interval(self.retry_interval)}"

    def wait_turn(self, stop: threading.Event) -> bool:
        """Block while paused. Returns True if the caller is the canary."""
        with self._cond:
            while True:
                if stop.is_set():
                    raise Stopped()
                if not self.paused:
                    return False
                now = self.clock()
                if now - self.paused_since >= self.max_wait:
                    raise CredentialTimeout()
                if not self.canary_out and now >= self.next_probe:
                    self.canary_out = True
                    self.canaries += 1
                    break
                wait = 1.0 if self.canary_out else min(1.0, max(0.01, self.next_probe - now))
                self._cond.wait(wait)
        if self.on_canary is not None:
            try:
                self.on_canary()
            except Exception:  # pragma: no cover - best effort
                LOG.warning("backend reset before credential retry failed: %s", traceback.format_exc(limit=1))
        LOG.warning("credential retry: sending one request to test the credentials")
        return True

    def cancel_canary(self) -> None:
        with self._cond:
            self.canary_out = False
            self._cond.notify_all()

    def report_ok(self, is_canary: bool) -> None:
        if not is_canary:
            return  # only the canary may reopen; stragglers prove nothing
        with self._cond:
            self.canary_out = False
            if self.paused:
                waited = self.clock() - self.paused_since
                self.paused = False
                self.paused_since_utc = None
                LOG.warning("CREDENTIALS OK again after %s — resuming all models", fmt_duration(waited))
            self._cond.notify_all()

    def report_failure(self, is_canary: bool, cause: str) -> None:
        with self._cond:
            now = self.clock()
            if not self.paused:
                self.paused = True
                self.paused_since = now
                self.paused_since_utc = utc_now_iso()
                self.next_probe = now + self.retry_interval
                self.canary_out = False
                self.pauses += 1
                LOG.critical("%s (cause: %s)", self.banner(), cause)
                print(self.banner(), file=sys.stderr, flush=True)
            elif is_canary:
                self.canary_out = False
                self.next_probe = now + self.retry_interval
                LOG.critical("%s (still failing after %s, cause: %s; gives up after %s)", self.banner(),
                             fmt_duration(now - self.paused_since), cause, fmt_duration(self.max_wait))
            self._cond.notify_all()
