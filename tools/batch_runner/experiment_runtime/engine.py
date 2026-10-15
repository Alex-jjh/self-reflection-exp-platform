"""The run engine: per-model lanes of worker threads over a resumable store."""

from __future__ import annotations

import collections
import dataclasses
import logging
import os
import random
import signal
import socket
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import Any

from .cells import Cell, load_cells
from .contract import (
    ACCESS_DENIED,
    CREDENTIAL,
    MODEL_UNAVAILABLE,
    THROTTLED,
    TRANSIENT,
    Failure,
    failure_from_exception,
)
from .control import AIMDLimiter, CredentialGate, CredentialTimeout, Stopped, backoff_delay
from .store import OutputStore
from .util import (
    EXIT_CRASH,
    EXIT_CREDENTIAL_TIMEOUT,
    EXIT_INCOMPLETE,
    EXIT_NEEDS_OPERATOR,
    EXIT_OK,
    LOG,
    ConfigError,
    canonical_json,
    fmt_duration,
    in_shard,
    order_key,
    sha256_hex,
    utc_now_iso,
)

RAW_SCHEMA = "batch_runner.raw/1"
FAILED_SCHEMA = "batch_runner.failed/1"
REASONING_SCHEMA = "batch_runner.reasoning/1"


@dataclasses.dataclass
class RunConfig:
    cells_path: Path
    out_dir: Path
    max_concurrency: int = 8
    initial_concurrency: int = 2
    increase_after: int = 10
    shard: tuple[int, int] = (0, 1)
    limit: int | None = None
    seed: str = "0"
    models: set[str] | None = None
    retry_failed: bool = False
    backoff_base: float = 2.0
    backoff_cap: float = 120.0
    max_transient_retries: int = 8
    max_cell_transient_failures: int = 40
    invalid_breaker: int = 20
    credential_retry_interval: float = 300.0
    credential_max_wait: float = 86400.0
    shutdown_timeout: float = 600.0
    progress_interval: float = 60.0
    code_sha256: str = "unknown"

    @property
    def shard_name(self) -> str:
        return f"shard{self.shard[0]}of{self.shard[1]}"


class Lane:
    """Queue, limiter and counters for one model."""

    def __init__(self, model: str, location: str, cells: list[Cell], limiter: AIMDLimiter, ever_succeeded: bool):
        self.model = model
        self.location = location
        self.queue: collections.deque[Cell] = collections.deque(cells)
        self.limiter = limiter
        self.ever_succeeded = ever_succeeded
        self.disabled: str | None = None
        self.invalid_streak = 0
        self.stats: collections.Counter[str] = collections.Counter()
        self.total = len(cells)
        self._lock = threading.Lock()

    def next_cell(self) -> Cell | None:
        with self._lock:
            if self.disabled or not self.queue:
                return None
            return self.queue.popleft()

    def put_back(self, cell: Cell, front: bool) -> None:
        with self._lock:
            (self.queue.appendleft if front else self.queue.append)(cell)

    def remaining(self) -> int:
        with self._lock:
            return len(self.queue)


class Runner:
    def __init__(self, cfg: RunConfig, store: OutputStore, lanes: list[Lane], blinds: dict[str, str],
                 backend: Any, history: dict[str, list[int]], lock_fd: int | None = None,
                 rng: random.Random | None = None):
        self.cfg = cfg
        self.store = store
        self.lanes = lanes
        self.blinds = blinds
        self.backend = backend
        self.backend_versions = dict(backend.versions())
        self.history = history
        self.lock_fd = lock_fd
        self.rng = rng or random.Random()
        self.run_id = uuid.uuid4().hex[:12]
        self.stop_event = threading.Event()
        self.finished = threading.Event()
        self.exit_code: int | None = None
        self.stop_reason: str | None = None
        self.abandoned_threads = 0
        self.started_monotonic = time.monotonic()
        self._history_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self.gate = CredentialGate(cfg.credential_retry_interval, cfg.credential_max_wait,
                                   hint=getattr(backend, "credential_hint", "refresh credentials"),
                                   on_canary=getattr(backend, "reset", None))

    # -- control -------------------------------------------------------------------

    def request_stop(self, code: int, reason: str) -> None:
        with self._state_lock:
            if self.exit_code is None:
                self.exit_code = code
                self.stop_reason = reason
            first = not self.stop_event.is_set()
            self.stop_event.set()
        if first:
            LOG.warning("stopping: %s — taking no new cells; waiting up to %s for in-flight calls",
                        reason, fmt_duration(self.cfg.shutdown_timeout))

    def _sleep(self, seconds: float) -> bool:
        """Interruptible sleep; False if a stop was requested."""
        return not self.stop_event.wait(seconds)

    # -- main loop -----------------------------------------------------------------

    def run(self) -> int:
        workers: list[threading.Thread] = []
        try:
            for lane in self.lanes:
                for index in range(min(self.cfg.max_concurrency, max(1, lane.total))):
                    workers.append(threading.Thread(target=self._worker_main, args=(lane,),
                                                    name=f"{lane.model}#{index}", daemon=True))
            threading.Thread(target=self._progress_loop, name="progress", daemon=True).start()
            for thread in workers:
                thread.start()

            while any(thread.is_alive() for thread in workers) and not self.stop_event.is_set():
                for thread in workers:
                    thread.join(timeout=0.2)
                    if self.stop_event.is_set():
                        break

            if self.stop_event.is_set():
                deadline = time.monotonic() + self.cfg.shutdown_timeout
                for thread in workers:
                    thread.join(timeout=max(0.0, deadline - time.monotonic()))
                self.abandoned_threads = sum(thread.is_alive() for thread in workers)
                if self.abandoned_threads:
                    LOG.warning("%d call(s) still in flight after %s; exiting without them (their cells stay pending)",
                                self.abandoned_threads, fmt_duration(self.cfg.shutdown_timeout))
            self.finished.set()
            code = self._exit_code()
            self._log_summary(code)
            self._write_heartbeat("exited", code)
            return code
        finally:
            self.finished.set()
            self.store.close()
            if self.lock_fd is not None:
                os.close(self.lock_fd)
                self.lock_fd = None

    def _exit_code(self) -> int:
        if self.exit_code is not None:
            return self.exit_code
        if any(lane.disabled for lane in self.lanes):
            return EXIT_NEEDS_OPERATOR
        if any(lane.remaining() for lane in self.lanes):
            return EXIT_INCOMPLETE
        return EXIT_OK

    def _worker_main(self, lane: Lane) -> None:
        try:
            while not self.stop_event.is_set():
                cell = lane.next_cell()
                if cell is None:
                    return
                outcome = self._process(lane, cell)
                if outcome == "requeue":
                    lane.put_back(cell, front=False)
                elif outcome in ("stopped", "lane_disabled"):
                    lane.put_back(cell, front=True)
                    return
        except Exception:
            LOG.critical("worker %s crashed:\n%s", threading.current_thread().name, traceback.format_exc())
            self.request_stop(EXIT_CRASH, "worker crashed")

    def _bump_history(self, blind: str, transient: bool) -> int:
        with self._history_lock:
            entry = self.history.setdefault(blind, [0, 0])
            entry[0] += 1
            if transient:
                entry[1] += 1
            return entry[1]

    def _attempt_number(self, blind: str) -> int:
        with self._history_lock:
            return self.history.get(blind, [0, 0])[0] + 1

    # -- one cell ----------------------------------------------------------------------

    def _process(self, lane: Lane, cell: Cell) -> str:
        blind = self.blinds[cell.cell_id]
        try:
            request = self.backend.prepare(cell.model, cell.system, cell.messages, cell.inference, cell.additional)
            request_hash = sha256_hex(canonical_json(request))
        except Exception as exc:
            failure = Failure("invalid", type(exc).__name__, None, None, str(exc)[:500])
            self._write_failed(blind, cell, None, failure, self._attempt_number(blind), "request could not be built")
            lane.stats["failed"] += 1
            LOG.error("invalid model=%s blind=%s request could not be built: %s", cell.model, blind, failure.message)
            return "failed"
        throttles = 0
        transient_streak = 0

        while True:
            if self.stop_event.is_set():
                return "stopped"
            if lane.disabled:
                return "lane_disabled"
            try:
                is_canary = self.gate.wait_turn(self.stop_event)
            except Stopped:
                return "stopped"
            except CredentialTimeout:
                self.request_stop(EXIT_CREDENTIAL_TIMEOUT,
                                  f"credentials still failing after {fmt_duration(self.cfg.credential_max_wait)}")
                return "stopped"
            token = lane.limiter.acquire(self.stop_event)
            if token is None:
                if is_canary:
                    self.gate.cancel_canary()
                return "stopped"

            attempt = self._attempt_number(blind)
            started_utc = utc_now_iso()
            started = time.monotonic()
            reply: Any = None
            failure: Failure | None = None
            try:
                reply = self.backend.invoke(cell.model, request)
            except Exception as exc:  # classified by the backend; never re-raised
                failure = failure_from_exception(exc)
            latency_ms = round((time.monotonic() - started) * 1000)
            finished_utc = utc_now_iso()

            if failure is not None and failure.kind == ACCESS_DENIED and lane.ever_succeeded:
                failure.kind = CREDENTIAL  # this model worked before: a credential/session problem
            if failure is None:
                lane.ever_succeeded = True  # before releasing the slot, so concurrent workers see it
            outcome = "success" if failure is None else ("throttle" if failure.kind == THROTTLED else "neutral")
            lane.limiter.release(token, outcome)

            if failure is None:
                self._finish_success(lane, cell, blind, request_hash, reply, attempt, latency_ms,
                                     started_utc, finished_utc)
                self.gate.report_ok(is_canary)
                return "done"

            transient_total = self._bump_history(blind, transient=failure.kind == TRANSIENT)
            self._log_attempt(blind, cell.model, failure.kind, failure.error_class, latency_ms, None,
                              attempt, lane.limiter.limit, finished_utc)
            lane.stats[failure.kind] += 1

            if failure.kind == CREDENTIAL:
                self.gate.report_failure(is_canary, failure.error_class)
                continue
            self.gate.report_ok(is_canary)  # the service answered, so authentication works

            if failure.kind == THROTTLED:
                throttles += 1
                delay = backoff_delay(throttles, self.cfg.backoff_base, self.cfg.backoff_cap, self.rng)
                LOG.info("throttled model=%s blind=%s attempt=%d limit=%d backoff=%.1fs",
                         cell.model, blind, attempt, lane.limiter.limit, delay)
                if not self._sleep(delay):
                    return "stopped"
                continue

            if failure.kind == TRANSIENT:
                transient_streak += 1
                if transient_total >= self.cfg.max_cell_transient_failures:
                    LOG.error("giving up on model=%s blind=%s after %d transient failures (last %s) -> failed/",
                              cell.model, blind, transient_total, failure.error_class)
                    self._write_failed(blind, cell, request_hash, failure, attempt,
                                       f"persistent transient failure ({transient_total} attempts)")
                    lane.stats["failed"] += 1
                    return "failed"
                if transient_streak > self.cfg.max_transient_retries:
                    LOG.warning("requeue model=%s blind=%s after %d consecutive %s",
                                cell.model, blind, transient_streak, failure.error_class)
                    lane.stats["requeued"] += 1
                    return "requeue"
                delay = backoff_delay(transient_streak, self.cfg.backoff_base, self.cfg.backoff_cap, self.rng)
                LOG.warning("transient model=%s blind=%s attempt=%d error=%s backoff=%.1fs",
                            cell.model, blind, attempt, failure.error_class, delay)
                if not self._sleep(delay):
                    return "stopped"
                continue

            if failure.kind in (ACCESS_DENIED, MODEL_UNAVAILABLE):
                self._disable_lane(lane, f"{failure.error_class}: {failure.message[:300]}")
                return "lane_disabled"

            # invalid: this request is wrong for this model; record it and move on
            lane.invalid_streak += 1
            self._write_failed(blind, cell, request_hash, failure, attempt, "non-retryable")
            lane.stats["failed"] += 1
            LOG.error("invalid model=%s blind=%s error=%s message=%s -> failed/",
                      cell.model, blind, failure.error_class, failure.message[:300])
            if lane.invalid_streak >= self.cfg.invalid_breaker:
                self._disable_lane(lane, f"{lane.invalid_streak} consecutive non-retryable errors, last "
                                         f"{failure.error_class}: {failure.message[:300]}")
            return "failed"

    def _finish_success(self, lane: Lane, cell: Cell, blind: str, request_hash: str, reply: Any, attempt: int,
                        latency_ms: int, started_utc: str, finished_utc: str) -> None:
        text = getattr(reply, "text", "") or ""
        usage = dict(getattr(reply, "usage", {}) or {})
        stop_reason = getattr(reply, "stop_reason", None)
        reasoning = list(getattr(reply, "reasoning", []) or [])
        redacted = int(getattr(reply, "redacted_reasoning_blocks", 0) or 0)
        self._bump_history(blind, transient=False)
        if reasoning or redacted:
            # kept out of raw/: whether a model 'thought' can reveal the condition
            self.store.write_reasoning(blind, {
                "schema": REASONING_SCHEMA, "blind": blind, "model": cell.model,
                "request_sha256": request_hash, "reasoning_text": reasoning, "redacted_blocks": redacted,
            })
        record = {
            "schema": RAW_SCHEMA,
            "blind": blind,
            "model": cell.model,
            "region": lane.location,
            "request_sha256": request_hash,
            "inference": cell.inference,
            "text": text,
            "usage": usage,
            "metrics": dict(getattr(reply, "metrics", {}) or {}),
            "stop_reason": stop_reason,
            "latency_ms": latency_ms,
            "started_utc": started_utc,
            "finished_utc": finished_utc,
            "attempt": attempt,
            "runner_sha256": self.cfg.code_sha256,
            **self.backend_versions,
        }
        published = self.store.write_raw(blind, record)
        self._log_attempt(blind, cell.model, "ok" if published else "duplicate", None, latency_ms, usage,
                          attempt, lane.limiter.limit, finished_utc)
        self.store.clear_failed(blind)
        lane.invalid_streak = 0
        lane.stats["done" if published else "duplicate"] += 1
        if not text:
            LOG.warning("empty reply text model=%s blind=%s stop_reason=%s out_tokens=%s",
                        cell.model, blind, stop_reason, usage.get("outputTokens"))
        LOG.info("ok model=%s blind=%s attempt=%d latency_ms=%d out_tokens=%s stop=%s limit=%d%s",
                 cell.model, blind, attempt, latency_ms, usage.get("outputTokens"), stop_reason,
                 lane.limiter.limit, "" if published else " (raw file already existed; kept the first)")

    def _disable_lane(self, lane: Lane, reason: str) -> None:
        if lane.disabled is None:
            lane.disabled = reason
            LOG.critical("MODEL DISABLED for this run: %s — %s (other models continue; fix, then rerun)",
                         lane.model, reason)

    def _write_failed(self, blind: str, cell: Cell, request_hash: str | None, failure: Failure,
                      attempt: int, note: str) -> None:
        self.store.write_failed(blind, {
            "schema": FAILED_SCHEMA,
            "blind": blind,
            "model": cell.model,
            "request_sha256": request_hash,
            "error_kind": failure.kind,
            "error_class": failure.error_class,
            "error_code": failure.code,
            "http_status": failure.http_status,
            "error_message": failure.message,
            "note": note,
            "attempt": attempt,
            "utc": utc_now_iso(),
            "runner_sha256": self.cfg.code_sha256,
            **self.backend_versions,
        })

    def _log_attempt(self, blind: str, model: str, status: str, error_class: str | None, latency_ms: int,
                     usage: dict[str, Any] | None, attempt: int, limit: int, utc: str) -> None:
        self.store.append_attempt({
            "utc": utc, "blind": blind, "model": model, "status": status, "error_class": error_class,
            "latency_ms": latency_ms, "usage": usage, "attempt": attempt, "limit": limit, "run": self.run_id,
        })

    # -- reporting ---------------------------------------------------------------------

    def snapshot(self, state: str) -> dict[str, Any]:
        return {
            "state": state,
            "utc": utc_now_iso(),
            "pid": os.getpid(),
            "host": socket.gethostname(),
            "run_id": self.run_id,
            "shard": f"{self.cfg.shard[0]}/{self.cfg.shard[1]}",
            "runner_sha256": self.cfg.code_sha256,
            "uptime_s": round(time.monotonic() - self.started_monotonic),
            "credentials_paused_since": self.gate.paused_since_utc if self.gate.paused else None,
            "lanes": {
                lane.model: {
                    "queued": lane.remaining(),
                    "in_flight": lane.limiter.in_flight,
                    "limit": lane.limiter.limit,
                    "limit_decreases": lane.limiter.decreases,
                    "this_run": dict(lane.stats),
                    "disabled": lane.disabled,
                }
                for lane in self.lanes
            },
        }

    def _write_heartbeat(self, state: str, exit_code: int | None = None) -> None:
        record = self.snapshot(state)
        if exit_code is not None:
            record["exit_code"] = exit_code
        try:
            self.store.write_heartbeat(self.cfg.shard_name, record)
        except OSError as error:
            LOG.warning("heartbeat write failed: %s", error)

    def _progress_loop(self) -> None:
        while not self.finished.wait(self.cfg.progress_interval):
            state = "paused_credentials" if self.gate.paused else ("stopping" if self.stop_event.is_set() else "running")
            self._write_heartbeat(state)
            parts = [
                f"{lane.model.split('.', 1)[-1]}: done={lane.stats['done']} queued={lane.remaining()} "
                f"inflight={lane.limiter.in_flight} limit={lane.limiter.limit} thr={lane.stats[THROTTLED]}"
                f"{' DISABLED' if lane.disabled else ''}"
                for lane in self.lanes
            ]
            LOG.info("progress [%s] %s", state, " | ".join(parts))
            if self.gate.paused:
                LOG.critical("%s (paused %s so far)", self.gate.banner(),
                             fmt_duration(self.gate.clock() - self.gate.paused_since))

    def _log_summary(self, code: int) -> None:
        total: collections.Counter[str] = collections.Counter()
        for lane in self.lanes:
            total.update(lane.stats)
            LOG.info("summary model=%s done=%d failed=%d throttled=%d transient=%d credential=%d requeued=%d "
                     "remaining=%d final_limit=%d%s", lane.model, lane.stats["done"], lane.stats["failed"],
                     lane.stats[THROTTLED], lane.stats[TRANSIENT], lane.stats[CREDENTIAL], lane.stats["requeued"],
                     lane.remaining(), lane.limiter.limit, f" DISABLED: {lane.disabled}" if lane.disabled else "")
        LOG.info("run finished exit=%d reason=%s done=%d failed=%d remaining=%d", code,
                 self.stop_reason or "complete", total["done"], total["failed"],
                 sum(lane.remaining() for lane in self.lanes))
        if total["failed"]:
            LOG.info("non-retryable failures are in failed/; rerun with --retry-failed to try them again")


def prepare_run(cfg: RunConfig, backend: Any, take_lock: bool = True) -> Runner:
    locations = dict(backend.models())
    if cfg.models is not None:
        unknown = cfg.models - set(locations)
        if unknown:
            raise ConfigError(f"--models not in allowlist: {', '.join(sorted(unknown))}")
    if cfg.max_concurrency < 1 or cfg.initial_concurrency < 1:
        raise ConfigError("concurrency values must be >= 1")
    cells = load_cells(cfg.cells_path, locations)
    store = OutputStore(cfg.out_dir)
    store.ensure_dirs()
    lock_fd = store.lock_run(cfg.shard_name) if take_lock else None
    try:
        store.cleanup_tmp()
        blinds = store.sync_map(cells)
        done = store.done_blinds()
        failed = store.failed_blinds()
        history = store.attempt_history()
        models_with_results = {cell.model for cell in cells if blinds[cell.cell_id] in done}

        selected = [cell for cell in cells
                    if in_shard(cell.cell_id, cfg.shard) and (cfg.models is None or cell.model in cfg.models)]
        done_selected = sum(blinds[cell.cell_id] in done for cell in selected)
        failed_skipped = 0 if cfg.retry_failed else sum(
            blinds[cell.cell_id] in failed and blinds[cell.cell_id] not in done for cell in selected)
        pending = [cell for cell in selected
                   if blinds[cell.cell_id] not in done and (cfg.retry_failed or blinds[cell.cell_id] not in failed)]
        pending.sort(key=lambda cell: order_key(cfg.seed, cell.cell_id))  # interleave conditions
        if cfg.limit is not None:
            pending = pending[: max(0, cfg.limit)]

        by_model: dict[str, list[Cell]] = {}
        for cell in pending:
            by_model.setdefault(cell.model, []).append(cell)
        initial = min(cfg.initial_concurrency, cfg.max_concurrency)
        lanes = [Lane(model, locations[model], model_cells,
                      AIMDLimiter(cfg.max_concurrency, initial, cfg.increase_after),
                      ever_succeeded=model in models_with_results)
                 for model, model_cells in sorted(by_model.items())]
        LOG.info("cells=%d in_shard=%d already_done=%d failed_skipped=%d pending_this_run=%d shard=%d/%d seed=%s%s",
                 len(cells), len(selected), done_selected, failed_skipped, len(pending), cfg.shard[0], cfg.shard[1],
                 cfg.seed, f" limit={cfg.limit}" if cfg.limit is not None else "")
        for lane in lanes:
            LOG.info("lane model=%s region=%s pending=%d", lane.model, lane.location, lane.total)
    except BaseException:
        if lock_fd is not None:
            os.close(lock_fd)
        raise
    return Runner(cfg, store, lanes, blinds, backend, history, lock_fd=lock_fd)


def install_signal_handlers(runner: Runner) -> None:
    """First SIGINT/SIGTERM: graceful stop. Second: exit at once."""
    received = {"count": 0}

    def handler(signum: int, _frame: Any) -> None:
        received["count"] += 1
        name = signal.Signals(signum).name
        if received["count"] > 1:
            LOG.warning("second %s: exiting immediately (in-flight cells stay pending)", name)
            logging.shutdown()
            os._exit(128 + signum)
        runner.request_stop(128 + signum, f"received {name}")

    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)
