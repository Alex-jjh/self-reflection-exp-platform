"""End-to-end tests of the runtime with a fake bedrock-runtime client.

Run from tools/batch_runner:  ../../.venv/bin/python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from helpers import (
    MODEL_A,
    MODEL_B,
    FakeBedrockClient,
    client_error,
    fake_backend,
    fast_config,
    ok_response,
    wait_until,
    write_cells,
)

from botocore.exceptions import CredentialRetrievalError

from experiment_runtime.cells import load_cells
from experiment_runtime.control import AIMDLimiter, CredentialGate
from experiment_runtime.engine import prepare_run
from experiment_runtime.status import compute_status
from experiment_runtime.store import OutputStore
from experiment_runtime.util import (
    EXIT_CREDENTIAL_TIMEOUT,
    EXIT_NEEDS_OPERATOR,
    EXIT_OK,
    ConfigError,
    in_shard,
    order_key,
    setup_logging,
)

TESTS_DIR = Path(__file__).resolve().parent
PYTHON = sys.executable


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def blind_map(out: Path) -> dict[str, str]:
    return {r["cell_id"]: r["blind"] for r in read_jsonl(out / "KEY" / "map.jsonl")}


class RunnerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        setup_logging(level=100)  # silence normal output; assertLogs still captures
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.cells = self.root / "cells.jsonl"
        self.out = self.root / "out"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_with(self, client: FakeBedrockClient, **overrides):
        backend, factory = fake_backend(client)
        runner = prepare_run(fast_config(self.cells, self.out, **overrides), backend)
        code = runner.run()
        return code, runner, factory

    def attempts_for(self, blind: str) -> list[dict]:
        return [r for r in read_jsonl(self.out / "attempts.jsonl") if r["blind"] == blind]


class TestAIMD(unittest.TestCase):
    def test_halves_once_per_congestion_event(self) -> None:
        limiter = AIMDLimiter(max_limit=8, initial=8, increase_after=5)
        tokens = [limiter.acquire() for _ in range(4)]  # all started in epoch 0
        limiter.release(tokens[0], "throttle")
        self.assertEqual(limiter.limit, 4)
        for token in tokens[1:]:  # same burst: must not halve again
            limiter.release(token, "throttle")
        self.assertEqual(limiter.limit, 4)
        for expected in (2, 1, 1):  # later throttles halve again, floor 1
            limiter.release(limiter.acquire(), "throttle")
            self.assertEqual(limiter.limit, expected)
        self.assertEqual(limiter.in_flight, 0)

    def test_additive_increase_after_n_successes_is_bounded(self) -> None:
        limiter = AIMDLimiter(max_limit=3, initial=1, increase_after=2)
        for expected in (1, 2, 2, 3, 3, 3, 3):
            limiter.release(limiter.acquire(), "success")
            self.assertEqual(limiter.limit, expected)
        limiter.release(limiter.acquire(), "throttle")
        self.assertEqual(limiter.limit, 1)
        limiter.release(limiter.acquire(), "success")  # throttle reset the success streak
        self.assertEqual(limiter.limit, 1)

    def test_acquire_blocks_at_the_limit(self) -> None:
        limiter = AIMDLimiter(max_limit=1, initial=1)
        token = limiter.acquire()
        got = threading.Event()
        threading.Thread(target=lambda: (limiter.acquire(), got.set()), daemon=True).start()
        self.assertFalse(got.wait(0.2))
        limiter.release(token, "neutral")
        self.assertTrue(got.wait(2))

    def test_engine_converges_under_simulated_capacity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cells, out = Path(tmp) / "cells.jsonl", Path(tmp) / "out"
            write_cells(cells, per_model=30, models=(MODEL_A,))
            capacity = 2
            client = FakeBedrockClient()
            lock = threading.Lock()
            state = {"now": 0}

            def behaviour(call):
                with lock:
                    state["now"] += 1
                    busy = state["now"]
                try:
                    time.sleep(0.01)
                    if busy > capacity:
                        raise client_error("ThrottlingException", 429, "Too many requests, please wait")
                    return ok_response()
                finally:
                    with lock:
                        state["now"] -= 1

            client.behaviour = behaviour
            setup_logging(level=100)
            backend, _ = fake_backend(client)
            runner = prepare_run(fast_config(cells, out, max_concurrency=8, initial_concurrency=8,
                                             increase_after=4), backend)
            self.assertEqual(runner.run(), EXIT_OK)
            lane = runner.lanes[0]
            self.assertEqual(len(list((out / "raw").glob("*.json"))), 30)
            self.assertGreaterEqual(lane.limiter.decreases, 1)
            self.assertLess(lane.limiter.limit, 8)
            self.assertGreater(lane.stats["throttled"], 0)


class TestCredentialGateUnit(unittest.TestCase):
    def test_banner_text(self) -> None:
        self.assertEqual(CredentialGate(300).banner(),
                         "CREDENTIALS FAILED — run mwinit; runner waits and retries every 5 min")


class TestRun(RunnerTestCase):
    def test_throttle_then_success(self) -> None:
        ids = write_cells(self.cells, per_model=3)
        target = ids[0]

        def behaviour(call):
            if call.cell_id == target and call.n <= 2:
                raise client_error("ThrottlingException", 429, "Too many requests, please wait before trying again.")
            return ok_response(f"reply for {call.cell_id}")

        code, runner, _ = self.run_with(FakeBedrockClient(behaviour))
        self.assertEqual(code, EXIT_OK)
        blind = blind_map(self.out)[target]
        self.assertEqual([a["status"] for a in self.attempts_for(blind)], ["throttled", "throttled", "ok"])
        raw = json.loads((self.out / "raw" / f"{blind}.json").read_text())
        self.assertEqual(raw["attempt"], 3)
        self.assertEqual(raw["text"], f"reply for {target}")
        lane = next(lane for lane in runner.lanes if lane.model == MODEL_A)
        self.assertGreaterEqual(lane.limiter.decreases, 1)
        self.assertEqual(list((self.out / "failed").iterdir()), [])
        self.assertEqual(len(list((self.out / "raw").glob("*.json"))), len(ids))

    def test_credential_failure_pauses_then_resumes(self) -> None:
        ids = write_cells(self.cells, per_model=6)
        broken = threading.Event()
        broken.set()
        client = FakeBedrockClient()
        bad_calls = []

        def behaviour(call):
            if broken.is_set():
                bad_calls.append(call)
                raise client_error("ExpiredTokenException", 403, "The security token included in the request is expired")
            return ok_response()

        client.behaviour = behaviour
        threading.Timer(0.5, broken.clear).start()  # 'mwinit' happens after 0.5 s
        with self.assertLogs("batch_runner", level="CRITICAL") as logs:
            code, runner, factory = self.run_with(client)
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(len(list((self.out / "raw").glob("*.json"))), len(ids))
        self.assertGreaterEqual(runner.gate.pauses, 1)
        self.assertGreaterEqual(runner.gate.canaries, 1)
        self.assertTrue(any("CREDENTIALS FAILED — run mwinit; runner waits and retries every 0.1 s" in line
                            for line in logs.output))
        # paused: only the first in-flight calls plus one canary per interval reached the service
        self.assertLessEqual(len(bad_calls), 2 * 4 + runner.gate.canaries)
        self.assertGreater(factory.created, 2)  # backend.reset() before each canary rebuilt the clients
        self.assertEqual(list((self.out / "failed").iterdir()), [])

    def test_credential_process_failure_pauses_then_resumes(self) -> None:
        write_cells(self.cells, per_model=2, models=(MODEL_A,))
        broken = threading.Event()
        broken.set()

        def behaviour(call):
            if broken.is_set():
                raise CredentialRetrievalError(provider="custom-process",
                                               error_msg="Midway authentication expired; run mwinit")
            return ok_response()

        threading.Timer(0.3, broken.clear).start()
        code, runner, _ = self.run_with(FakeBedrockClient(behaviour))
        self.assertEqual(code, EXIT_OK)
        self.assertGreaterEqual(runner.gate.pauses, 1)
        self.assertEqual(len(list((self.out / "raw").glob("*.json"))), 2)

    def test_credentials_give_up_after_max_wait(self) -> None:
        write_cells(self.cells, per_model=2, models=(MODEL_A,))
        client = FakeBedrockClient(lambda call: (_ for _ in ()).throw(
            client_error("UnrecognizedClientException", 403, "The security token included in the request is invalid.")))
        code, _, _ = self.run_with(client, credential_max_wait=0.4)
        self.assertEqual(code, EXIT_CREDENTIAL_TIMEOUT)
        self.assertEqual(list((self.out / "raw").glob("*.json")), [])

    def test_access_denied_after_success_is_treated_as_credentials(self) -> None:
        write_cells(self.cells, per_model=8, models=(MODEL_A,))
        state = {"ok": 0}
        denied = threading.Event()
        lock = threading.Lock()

        def behaviour(call):
            if denied.is_set():
                raise client_error("AccessDeniedException", 403, "User is not authorized to perform bedrock:InvokeModel")
            with lock:
                state["ok"] += 1
                if state["ok"] == 2:
                    denied.set()
                    threading.Timer(0.4, denied.clear).start()
            return ok_response()

        code, runner, _ = self.run_with(FakeBedrockClient(behaviour), initial_concurrency=1)
        self.assertEqual(code, EXIT_OK)
        self.assertGreaterEqual(runner.gate.pauses, 1)
        self.assertEqual(len(list((self.out / "raw").glob("*.json"))), 8)

    def test_access_denied_before_any_success_disables_only_that_model(self) -> None:
        ids = write_cells(self.cells, per_model=4)

        def behaviour(call):
            if call.model == MODEL_A:
                raise client_error("AccessDeniedException", 403, "explicit deny in a service control policy")
            return ok_response()

        code, runner, _ = self.run_with(FakeBedrockClient(behaviour))
        self.assertEqual(code, EXIT_NEEDS_OPERATOR)
        mapping = blind_map(self.out)
        done = {path.stem for path in (self.out / "raw").glob("*.json")}
        self.assertEqual(done, {mapping[i] for i in ids if MODEL_B in i})
        self.assertEqual(list((self.out / "failed").iterdir()), [])  # model-level, not cell-level
        self.assertTrue(next(l for l in runner.lanes if l.model == MODEL_A).disabled)

    def test_non_retryable_goes_to_failed_and_retry_failed(self) -> None:
        ids = write_cells(self.cells, per_model=3)
        bad = ids[1]
        message = "This model doesn't support the temperature field. Remove temperature and try again."

        def behaviour(call):
            if call.cell_id == bad:
                raise client_error("ValidationException", 400, message)
            return ok_response()

        code, _, _ = self.run_with(FakeBedrockClient(behaviour))
        self.assertEqual(code, EXIT_OK)
        blind = blind_map(self.out)[bad]
        failed = json.loads((self.out / "failed" / f"{blind}.json").read_text())
        self.assertEqual(failed["error_code"], "ValidationException")
        self.assertEqual(failed["http_status"], 400)
        self.assertEqual(failed["error_message"], message)
        self.assertNotIn(bad, json.dumps(failed))
        self.assertFalse((self.out / "raw" / f"{blind}.json").exists())

        again = FakeBedrockClient()
        self.assertEqual(self.run_with(again)[0], EXIT_OK)
        self.assertEqual(again.called_ids(), [])  # failed cells are skipped by default

        fixed = FakeBedrockClient()
        self.assertEqual(self.run_with(fixed, retry_failed=True)[0], EXIT_OK)
        self.assertEqual(fixed.called_ids(), [bad])
        self.assertTrue((self.out / "raw" / f"{blind}.json").exists())
        self.assertFalse((self.out / "failed" / f"{blind}.json").exists())

    def test_invalid_breaker_disables_a_systematically_broken_model(self) -> None:
        write_cells(self.cells, per_model=12, models=(MODEL_B,))
        client = FakeBedrockClient(lambda call: (_ for _ in ()).throw(
            client_error("ValidationException", 400, "Unknown parameter: 'reasoning_effort'.")))
        code, runner, _ = self.run_with(client, invalid_breaker=3, initial_concurrency=1)
        self.assertEqual(code, EXIT_NEEDS_OPERATOR)
        failed = len(list((self.out / "failed").glob("*.json")))
        self.assertGreaterEqual(failed, 3)
        self.assertLessEqual(failed, 3 + 4)  # plus calls already in flight when it tripped
        self.assertLess(failed, 12)
        self.assertIn("consecutive non-retryable", runner.lanes[0].disabled)

    def test_transient_errors_retry_requeue_then_fail(self) -> None:
        ids = write_cells(self.cells, per_model=3, models=(MODEL_A,))
        flaky, broken = ids[0], ids[1]

        def behaviour(call):
            if call.cell_id == flaky and call.n <= 2:
                raise client_error("InternalServerException", 500, "internal")
            if call.cell_id == broken:
                raise client_error("ServiceUnavailableException", 503, "unavailable")
            return ok_response()

        code, runner, _ = self.run_with(FakeBedrockClient(behaviour), max_transient_retries=2,
                                        max_cell_transient_failures=7)
        self.assertEqual(code, EXIT_OK)
        mapping = blind_map(self.out)
        self.assertTrue((self.out / "raw" / f"{mapping[flaky]}.json").exists())
        failed = json.loads((self.out / "failed" / f"{mapping[broken]}.json").read_text())
        self.assertIn("persistent transient", failed["note"])
        self.assertGreaterEqual(runner.lanes[0].stats["requeued"], 2)
        self.assertEqual(len(self.attempts_for(mapping[broken])), 7)

    def test_outputs_are_blind_and_attempts_have_no_content(self) -> None:
        ids = write_cells(self.cells, per_model=3)

        def behaviour(call):
            return ok_response("the reply text", reasoning="hidden chain" if call.model == MODEL_A else None)

        self.assertEqual(self.run_with(FakeBedrockClient(behaviour))[0], EXIT_OK)
        mapping = blind_map(self.out)
        self.assertEqual(set(mapping), set(ids))
        for path in (self.out / "raw").glob("*.json"):
            body = path.read_text()
            record = json.loads(body)
            self.assertEqual(record["blind"], path.stem)
            self.assertNotIn("cond=", body)
            self.assertNotIn("system prompt", body)
            self.assertNotIn("reasoning_effort", body)  # additionalModelRequestFields are not in raw
            self.assertNotIn("hidden chain", body)  # reasoning goes to reasoning/, not raw/
            for key in ("model", "region", "request_sha256", "inference", "text", "usage", "stop_reason",
                        "latency_ms", "started_utc", "finished_utc", "attempt", "runner_sha256",
                        "botocore_version"):
                self.assertIn(key, record)
        self.assertEqual(len(list((self.out / "reasoning").glob("*.json"))), 3)
        attempts = (self.out / "attempts.jsonl").read_text()
        self.assertNotIn("the reply text", attempts)
        self.assertNotIn("cond=", attempts)
        self.assertEqual(len((self.out / "KEY" / "salt.txt").read_text().strip()), 64)

    def test_resume_skips_done_cells_without_duplicates(self) -> None:
        ids = write_cells(self.cells, per_model=6)
        first = FakeBedrockClient()
        self.assertEqual(self.run_with(first, limit=5)[0], EXIT_OK)
        self.assertEqual(len(first.called_ids()), 5)
        second = FakeBedrockClient()
        self.assertEqual(self.run_with(second)[0], EXIT_OK)
        self.assertEqual(set(first.called_ids()) & set(second.called_ids()), set())
        self.assertEqual(set(first.called_ids()) | set(second.called_ids()), set(ids))
        self.assertEqual(len(read_jsonl(self.out / "KEY" / "map.jsonl")), len(ids))
        third = FakeBedrockClient()
        self.assertEqual(self.run_with(third)[0], EXIT_OK)
        self.assertEqual(third.called_ids(), [])

    def test_existing_raw_file_is_never_overwritten(self) -> None:
        ids = write_cells(self.cells, per_model=1, models=(MODEL_A,))
        store = OutputStore(self.out)
        store.ensure_dirs()
        blind = store.sync_map(load_cells(self.cells, {MODEL_A: "us-west-2"}))[ids[0]]
        self.assertTrue(store.write_raw(blind, {"first": True}))
        self.assertFalse(store.write_raw(blind, {"first": False}))
        self.assertEqual(json.loads(store.raw_path(blind).read_text()), {"first": True})
        self.assertEqual(list((self.out / "tmp").iterdir()), [])  # staging file cleaned up

    def test_missing_salt_with_existing_outputs_is_refused(self) -> None:
        write_cells(self.cells, per_model=1)
        self.assertEqual(self.run_with(FakeBedrockClient())[0], EXIT_OK)
        (self.out / "KEY" / "salt.txt").unlink()
        with self.assertRaises(ConfigError):
            self.run_with(FakeBedrockClient())

    def test_second_runner_on_same_shard_is_refused(self) -> None:
        write_cells(self.cells, per_model=1)
        backend, _ = fake_backend(FakeBedrockClient())
        first = prepare_run(fast_config(self.cells, self.out), backend)
        with self.assertRaises(ConfigError):
            prepare_run(fast_config(self.cells, self.out), backend)
        self.assertEqual(first.run(), EXIT_OK)

    def test_shards_partition_and_order_interleaves_conditions(self) -> None:
        ids = [f"cond={c}|item={i}" for c in "ABCDE" for i in range(40)]
        shards = [{i for i in ids if in_shard(i, (k, 3))} for k in range(3)]
        self.assertEqual(sum(len(s) for s in shards), len(ids))
        self.assertEqual(set().union(*shards), set(ids))
        first_25 = sorted(ids, key=lambda i: order_key("0", i))[:25]
        self.assertEqual({i.split("|")[0] for i in first_25}, {f"cond={c}" for c in "ABCDE"})

    def test_status_counts(self) -> None:
        ids = write_cells(self.cells, per_model=4)
        bad = ids[0]
        client = FakeBedrockClient(lambda call: (_ for _ in ()).throw(client_error("ValidationException", 400, "bad"))
                                   if call.cell_id == bad else ok_response())
        self.run_with(client, limit=6)
        status = compute_status(self.cells, self.out, {MODEL_A: "us-west-2", MODEL_B: "us-east-2"})
        totals = status["totals"]
        self.assertEqual(totals["total"], 8)
        self.assertEqual(totals["done"] + totals["failed"], 6)
        self.assertEqual(totals["pending"], 2)
        self.assertEqual(totals["ok_1h"], totals["done"])
        self.assertEqual(status["active_runner_locks"], [])


class TestProcessInterruption(unittest.TestCase):
    """The engine in a child process, killed or terminated mid-run."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.cells = self.root / "cells.jsonl"
        self.out = self.root / "out"
        self.ids = write_cells(self.cells, per_model=20)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def start_child(self, delay: float) -> subprocess.Popen:
        return subprocess.Popen([PYTHON, str(TESTS_DIR / "child_run.py"), str(self.cells), str(self.out), str(delay)],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    def raw_files(self) -> list[Path]:
        return sorted((self.out / "raw").glob("*")) if (self.out / "raw").exists() else []

    def await_raw_files(self, count: int, child: subprocess.Popen, timeout: float = 120.0) -> None:
        """Wait for `count` raw files. Generous timeout: a loaded machine must not fail the test."""
        ok = wait_until(lambda: len(self.raw_files()) >= count or child.poll() is not None, timeout=timeout)
        if child.poll() is not None:
            output, _ = child.communicate(timeout=30)
            self.fail(f"child exited early with {child.returncode} after {len(self.raw_files())} raw file(s):"
                      f"\n{output[-4000:]}")
        self.assertTrue(ok, f"only {len(self.raw_files())} of {count} raw file(s) after {timeout}s")

    def test_kill_mid_run_then_resume_without_duplicates_or_partial_files(self) -> None:
        child = self.start_child(delay=0.3)
        try:
            self.await_raw_files(6, child)
            os.kill(child.pid, signal.SIGKILL)
            child.communicate(timeout=10)
        finally:
            if child.poll() is None:
                child.kill()
                child.communicate()
        self.assertEqual(child.returncode, -signal.SIGKILL)
        before = {path.name: path.read_bytes() for path in self.raw_files()}
        self.assertGreater(len(before), 0)
        self.assertLess(len(before), len(self.ids))
        for name, data in before.items():
            self.assertTrue(name.endswith(".json"))
            self.assertEqual(json.loads(data)["blind"], name[:-5])  # complete JSON, never partial

        setup_logging(level=100)
        resumed = FakeBedrockClient()
        backend, _ = fake_backend(resumed)
        self.assertEqual(prepare_run(fast_config(self.cells, self.out), backend).run(), EXIT_OK)
        mapping = blind_map(self.out)
        done_before = {name[:-5] for name in before}
        called_blinds = {mapping[cell_id] for cell_id in resumed.called_ids()}
        self.assertEqual(called_blinds & done_before, set())  # nothing done twice
        self.assertEqual(len(resumed.called_ids()), len(set(resumed.called_ids())))
        self.assertEqual({p.stem for p in self.raw_files()}, set(mapping.values()))
        for name, data in before.items():
            self.assertEqual((self.out / "raw" / name).read_bytes(), data)  # untouched
        self.assertEqual(len(read_jsonl(self.out / "KEY" / "map.jsonl")), len(self.ids))
        read_jsonl(self.out / "attempts.jsonl")  # every line still parses

    def test_sigterm_finishes_in_flight_calls_and_exits_cleanly(self) -> None:
        child = self.start_child(delay=0.6)
        try:
            self.await_raw_files(2, child)
            at_signal = len(self.raw_files())
            child.send_signal(signal.SIGTERM)
            output, _ = child.communicate(timeout=30)
        finally:
            if child.poll() is None:
                child.kill()
        self.assertEqual(child.returncode, 128 + signal.SIGTERM, output[-2000:])
        self.assertIn("stopping: received SIGTERM", output)
        done = len(self.raw_files())
        # in-flight calls (at most 4 per model) were allowed to finish and were saved; nothing new started
        self.assertGreaterEqual(done, at_signal)
        self.assertLessEqual(done, at_signal + 2 * 4)
        self.assertLess(done, len(self.ids))
        oks = [r for r in read_jsonl(self.out / "attempts.jsonl") if r["status"] == "ok"]
        self.assertEqual(len(oks), done)
        beat = json.loads((self.out / "heartbeat" / "shard0of1.json").read_text())
        self.assertEqual(beat["state"], "exited")
        self.assertEqual(beat["exit_code"], 143)


if __name__ == "__main__":
    unittest.main()
