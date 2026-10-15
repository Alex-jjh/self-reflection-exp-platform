# batch_runner — resumable Bedrock reply collection

A batch runner for multi-day model-reply collection on AWS Bedrock (Converse API).
It survives crashes, `kill -9`, throttling and expired credentials. When restarted
with the same command it carries on where it stopped and never repeats a finished
cell.

```
tools/batch_runner/
  runner.py              CLI (run / status / probe / ramp); the only file that imports both packages
  run_forever.sh         supervisor: restarts `run` after an abnormal exit
  bedrock_access/        WHERE THE AI CREDENTIALS COME FROM + how a request reaches a model
    credentials.py         token source: boto3 Session on profile codex-DO-NOT-DELETE (credential_process)
    models.py              allowlist model -> region
    backend.py             Converse request shape, call, reply parsing
    errors.py              botocore/Bedrock errors -> kinds (throttled, transient, credential, ...)
    diagnostics.py         probe and ramp
  experiment_runtime/    THE EXPERIMENT RUNTIME (knows nothing about AWS)
    contract.py            the small duck-typed interface the runtime needs from a backend
    cells.py               cells.jsonl schema and validation
    store.py               blind ids, atomic writes, attempts log, locks, heartbeat
    control.py             AIMD concurrency, backoff, global credential pause
    engine.py              per-model worker lanes, retry policy, shutdown
    status.py              progress / throughput / ETA
  tests/                 unittest suite with a fake bedrock-runtime client
```

**Two separate packages.** `experiment_runtime` never imports boto3, botocore or
`bedrock_access`. `bedrock_access` never imports `experiment_runtime`. A test
checks both directions. To use a different token source or provider (for example
the local gateway, another profile or another API), write a new backend that
satisfies `experiment_runtime/contract.py` and wire it in `runner.py`. The
runtime stays the same.

Everything runs with the repository's interpreter. The commands below assume
`cd /home/alexjia/.workspace/self-reflection-exp-platform`.

## Credentials

The runner follows `/home/alexjia/.workspace/CODEX_BEDROCK_TEMP_CREDENTIAL_RUNBOOK.md`:

- It keeps one long-lived `boto3.Session(profile_name="codex-DO-NOT-DELETE")`, so
  botocore re-runs `credential_process` before the STS credentials expire. A
  4-day run therefore needs no restarts.
- It never reads, prints, exports or writes credential values, and it never
  touches `.bedrock_key`. Any `AWS_BEARER_TOKEN_*` variable is removed from the
  runner's own environment at start-up, so a bearer token cannot be used by
  accident.
- At start-up `run` calls `sts:GetCallerIdentity` and stops (exit 2) unless the
  role name contains `CaminusBedrockAccess` (`--expect-role ''` skips this
  check). The probe on 2026-10-11 saw account `848172273356`, role
  `CaminusBedrockAccess`.

## 1. Build cells.jsonl

Write one JSON object per line. The runner checks the shape only; it does not
interpret conditions.

```json
{"cell_id": "S03|cond=reflect|rep=2|model=sonnet5",
 "model": "us.anthropic.claude-sonnet-5",
 "system": "…system prompt…",
 "messages": [{"role": "user", "text": "…"}, {"role": "assistant", "text": "…"}, {"role": "user", "text": "…"}],
 "inference": {"maxTokens": 1500},
 "additional": {"thinking": {"type": "disabled"}},
 "meta": {"anything": "ignored, never sent, never stored"}}
```

- `cell_id`: unique, single line, at most 512 characters. It may encode the
  condition; it never appears in `raw/`.
- `model`: one of the 8 allowlisted ids (see `bedrock_access/models.py`).
- `system`: a string or `null`. `messages`: non-empty, roles `user`/`assistant`,
  first role `user`.
- `inference`: `maxTokens` (required), `temperature`, `topP`, `stopSequences`.
- `additional`: passed unchanged as `additionalModelRequestFields`, or `null`.

A minimal generator:

```python
import json
with open("cells.jsonl", "w", encoding="utf-8") as f:
    for model in MODELS:
        for cond in CONDITIONS:
            for rep in range(N_REPS):
                f.write(json.dumps({
                    "cell_id": f"{cond.name}|rep={rep}|{model}",
                    "model": model, "system": cond.system,
                    "messages": cond.messages,
                    "inference": {"maxTokens": 1500},
                    "additional": cond.additional_for(model),
                }, ensure_ascii=False) + "\n")
```

**What each model accepts (probe 2026-10-11; rerun `probe` before a new batch):**

| model | `temperature` | `topP` | thinking / reasoning by default | how to set it (`additional`) |
|---|---|---|---|---|
| GPT-5.6 sol / terra / luna | rejected, any value | rejected | on (encrypted `redactedContent` only) | `{"reasoning": {"effort": "none"\|"low"\|"medium"\|"high"\|"xhigh"\|"max"}}` |
| Claude Opus 5 | only `1.0` (the default) | rejected | **on** (adaptive) | `{"thinking": {"type": "disabled"}}` (not with effort `max`); `{"output_config": {"effort": …}}` |
| Claude Sonnet 5 | only `1.0` | rejected | on (adaptive; skips easy prompts) | same as Opus 5 |
| Claude Opus 4.7 | only `1.0` | rejected | off | `{"thinking": {"type": "adaptive"}}`, `{"output_config": {"effort": …}}` |
| Claude Sonnet 4.6 | yes | yes, but not together with `temperature` | off | `adaptive`, or `{"type": "enabled", "budget_tokens": N}`; effort `low/medium/high/max` (no `xhigh`) |
| Claude Haiku 4.5 | yes | yes, but not together | off | only `{"thinking": {"type": "enabled", "budget_tokens": N}}`; no effort, no adaptive |

All 8 models accept a system prompt and user/assistant/user history. Unknown
`additional` fields are rejected by every model, so a typo fails loudly and is
never silently ignored. **Reasoning tokens count against `maxTokens`**: with
`maxTokens: 60`, GPT-5.6 and Opus 5 sometimes returned an empty or truncated
reply (`stop_reason: max_tokens`). Leave headroom. The full report with verbatim
errors is in `AQ1_PREP/runs/_probe/probe/`.

## 2. Smoke test, then run

Run a few cells first into the real output directory. Finished cells count, so
nothing is wasted:

```bash
.venv/bin/python tools/batch_runner/runner.py run --cells CELLS.jsonl --out DIR --limit 24
.venv/bin/python tools/batch_runner/runner.py status --cells CELLS.jsonl --out DIR
ls DIR/failed/        # should be empty; if not, read one file and fix the cells
```

Then start the supervised 4-day run (it survives logout; output goes to
`DIR/logs/run_forever.log`):

```bash
nohup tools/batch_runner/run_forever.sh --cells CELLS.jsonl --out DIR >/dev/null 2>&1 &
tail -F DIR/logs/run_forever.log            # follow
kill "$(cat DIR/run_forever.pid)"           # stop gracefully (in-flight calls finish)
```

Extra options after `--out DIR` are passed to `runner.py run` unchanged. Useful
ones: `--max-concurrency-per-model 8` (default 8, AIMD upper bound),
`--initial-concurrency 2`, `--models a,b`, `--shard i/n`, `--limit N`,
`--seed S` (shuffle seed, default `0`) and `--retry-failed`.

`nohup` does not survive a reboot or restart of the DevSpace host. After one,
start the same command again.

## 3. Resume

Run the same command again. A cell is done when `raw/<blind>.json` exists. Each
run skips done cells, and `failed/` cells too unless you pass `--retry-failed`. A
crash or kill loses only the calls that were in flight. Files are written to
`tmp/`, fsynced, then published atomically, so `raw/` never holds a partial file.
A raw file is never overwritten: if two runners finish the same cell, the first
file is kept. Each `--shard` takes a lock, so a second runner on the same shard
refuses to start.

## 4. Status

```bash
.venv/bin/python tools/batch_runner/runner.py status --cells CELLS.jsonl --out DIR [--verify] [--json]
```

This shows done / failed / pending per model, successful calls, throttles and
other errors in the last hour, mean latency, and an ETA at the last-hour rate
(overall ETA = the slowest model). It also shows which runners hold a lock, each
runner's heartbeat, and any disabled model or credential pause. `--verify`
re-hashes every done cell's request against the current cells file and counts
mismatches (cells edited after they finished).

## 5. When credentials fail

ExpiredToken, UnrecognizedClient, invalid signature, a `credential_process`
error (Midway or Caminus), or AccessDenied from a model that had already
succeeded all pause every model. The log shows, every 5 minutes:

```
CREDENTIALS FAILED — run mwinit; runner waits and retries every 5 min
```

Run `mwinit`. Within 5 minutes one request retries (on a fresh Session, so
`credential_process` runs again), and when it succeeds all models resume on
their own. After 24 hours of failures `run` exits with code 4. The supervisor
then restarts it, so it keeps waiting.

## 6. What goes where, and who may open it

| path | content | coders |
|---|---|---|
| `raw/<blind>.json` | one completed reply: `blind`, `model`, `region`, `request_sha256`, `inference`, `text`, `usage`, `metrics`, `stop_reason`, `latency_ms`, `started_utc`, `finished_utc`, `attempt`, `runner_sha256`, `botocore_version` | **yes, the only thing coders open** |
| `KEY/salt.txt`, `KEY/map.jsonl` | the salt and `cell_id -> blind` | **never** (unblinds everything) |
| `failed/<blind>.json` | non-retryable error, verbatim message | no (operator) |
| `reasoning/<blind>.json` | reasoning blocks, if a model returned any | no (whether a model "thought" can reveal the condition) |
| `attempts.jsonl` | one line per attempt: blind, model, status, error class, latency, usage, UTC, AIMD limit; no content | no (operator) |
| `heartbeat/`, `locks/`, `logs/`, `tmp/` | runner state | no |

`blind` = the first 16 hex characters of `sha256(salt + cell_id)`. Raw files
contain neither the cell id, the prompt nor `additionalModelRequestFields`, so
a coder sees the model and the reply only. Two caveats:

- `inference` is in every raw file. If temperature or `maxTokens` is a
  manipulated condition, raw files are not blind to it.
- `usage` (output tokens) can hint at whether a model reasoned.

`runner_sha256` is a hash of `runner.py`, `experiment_runtime/*.py` and
`bedrock_access/*.py` (excluding `diagnostics.py`). It changes whenever the code
that produced a reply changes.

**Back up `KEY/` separately.** If `salt.txt` is lost, the runner refuses to
create a new one while outputs exist, because every blind id would change.

## 7. Behaviour

- **Order.** Pending cells are shuffled by `sha256(seed, cell_id)`, a fixed
  order that does not depend on the file order. Each model has its own lane and
  all lanes run at once. A run cut short therefore covers every condition
  partially. `--shard i/n` picks cells whose `sha256(cell_id) mod n == i`.
  `--limit N` takes the first N of the shuffled pending cells.
- **Concurrency (AIMD), per model.** It starts at `--initial-concurrency` (2).
  Any throttle halves the limit, counted once per burst. After
  `--aimd-increase-after` (10) consecutive successes it grows by 1, up to
  `--max-concurrency-per-model` (8).
- **Throttling** (429, ThrottlingException, ServiceQuotaExceeded): exponential
  backoff with jitter, capped at 120 s, retried without limit.
- **5xx, timeouts, connection errors**: the same backoff. After 8 consecutive
  retries the cell goes to the back of its queue. After 40 failures in total
  (across runs) it goes to `failed/`.
- **Non-retryable** (ValidationException and other 4xx): written to `failed/`
  and the run continues. After 20 in a row on one model, that model is disabled
  for the run (exit 5) so a systematic mistake does not fill `failed/`.
- **Model-level errors** (AccessDenied before any success,
  ResourceNotFoundException): that model is disabled, its cells stay pending,
  the other models continue, and the run exits 5.
- **SIGTERM / SIGINT**: no new cells start. In-flight calls finish and are saved
  (up to `--shutdown-timeout`, 600 s). Exit code is 143 / 130. A second signal
  exits immediately.
- **Exit codes**: 0 done · 1 crash · 2 config error · 3 incomplete · 4
  credentials failed for 24 h · 5 a model was disabled · 130/143 signal.
  `run_forever.sh` stops on 0, 2, 5, 130 and 143, and restarts on everything
  else (delay 30 s, doubling up to 10 min).
- botocore's own retries are off (`total_max_attempts: 1`), so every attempt is
  logged and the AIMD controller sees every throttle. Read timeout is 900 s.

## 8. probe and ramp

```bash
.venv/bin/python tools/batch_runner/runner.py probe --out AQ1_PREP/runs/_probe
.venv/bin/python tools/batch_runner/runner.py ramp  --out AQ1_PREP/runs/_probe [--gpt-additional '{"reasoning":{"effort":"low"}}']
```

- `probe` makes small real calls per model: format checks, sampling parameters,
  candidate reasoning/effort/thinking fields (each with a bogus value to prove
  the field is parsed), and effort sweeps. It writes `probe/probe-<utc>.json`
  and `.md` with verbatim errors.
- `ramp` sends a ~300-token Chinese reply to a short Chinese message at
  concurrency 1, 2, 4, 8 and 16 (10 calls per step, or 16 at the last step), with
  no retries. It writes `ramp/ramp-<utc>.json` and `.md`, metadata only.

Ramps on 2026-10-11 (up to 16 per model) and 2026-10-12 (up to 8, on a second
machine), all 8 models ramped at once each time:
- No throttles and no errors at any step: 448 + 320 calls, all successful.
- Latency stayed flat as concurrency rose. Mean latency per 300-token reply:
  Haiku 4.5 ≈ 2.9 s, Sonnet 4.6 ≈ 3.8 s, Opus 4.7 ≈ 5.9 s, Sonnet 5 ≈ 5.5 s,
  Opus 5 ≈ 7.0 s, GPT-5.6 ≈ 2.7–4.0 s.
- So the default limit of 8 per model is conservative for short replies. Longer
  replies use more tokens per minute; AIMD backs off by itself if a quota binds.

## 9. Tests

```bash
cd tools/batch_runner && ../../.venv/bin/python -m unittest discover -s tests -v
```

The suite covers:
- AIMD halving once per burst, additive increase, bounds, and convergence under
  simulated capacity;
- throttling followed by success;
- credential failure: pause, one canary per interval, resume (both an
  ExpiredToken and a `credential_process` failure); give-up after max wait; and
  AccessDenied before vs. after a success;
- a `kill -9` mid-run followed by resume, with no duplicate calls, no partial
  files, and earlier raw files byte-for-byte unchanged;
- SIGTERM finishing in-flight calls;
- `failed/` with `--retry-failed`, and the breaker;
- transient requeue and the persistent-failure limit;
- blinding of `raw/` and `attempts.jsonl`;
- the salt guard, the shard lock, interleaving, and status;
- the package boundary (no imports in either direction, matching error kinds).
