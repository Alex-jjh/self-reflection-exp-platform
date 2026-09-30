# Synthetic matrix (SYN)

> **Summary:** The synthetic matrix (SYN), a no-participant experiment in which three models answer the same scripted self-critical user under a supportive control prompt or a permission-gate prompt: 60 conversations, 480 model turns, 180 coded units (AI turns 6–8). This file lists its materials and data, how to run and code it, what the coder of the human anchor must not open first, and what its results can support now.

SYN tests whether an AI response failure caused by an injected self-narrative
differs from a failure caused by a request for permission or a verdict, and
compares a supportive control policy with a permission-gate policy on both. All
data is synthetic; no participant is involved.

What to read first:

- To code the human anchor: Before coding the human anchor, first. It names
  the only two files to code from and what not to open until your codes are
  saved.
- To understand the experiment: Design and Files, then What the results can
  support now.
- To run or rerun collection or auto-coding: Run, Crash-safe resume and Coding,
  then `AUTOCODING_WORKFLOW.md`.

**Names.** `SYN` is the experiment's ID in the research repo (`ARCHITECTURE.md`,
Identifiers). "Permission-gate pilot" is the name of its runs, used in folder and
tool names (`model-comparison/permission-gate-pilot/`,
`tools/run_permission_gate_pilot.py`), and `matrix-pilot/` is this folder; all
three name the same experiment. The cross-model frozen-script replay
(`tools/cross_model_pilot.py`, `tools/model_compare.py`, `tools/matrix_index.py`)
is a separate, earlier exploration of the session conditions and is not SYN. The
terms *human anchor*, *AI reference*, *Claude* and *Jev* are defined in the
research repo's `ARCHITECTURE.md` (Terms); D-nnn are its decisions
(`DECISIONS.md`).

## Design

- User track: `S2_verdict` vs `S2_bias` (same self-critical content; speech act
  differs). In `S2_verdict` the user asks for a verdict or permission; in
  `S2_bias` the same content is stated as settled, and the user tells the AI to
  continue within it (turn 8 asks for a concrete plan) without asking it to
  certify the view. The reports call them the verdict-request track and the
  injected-bias (assertion) track.
- System prompt: an identical shared Chinese supportive core plus one of two
  structurally matched policy blocks — `supportive_control` (give a clear best
  judgment with uncertainty) vs `permission_gate` (preserve alternatives and
  return a discriminator). The policy blocks are kept within 10% character
  length so prompt length/detail is not the manipulation.
- Models: Claude Sonnet 5 (the study baseline, the model frozen for the lab
  sessions), Claude Haiku 4.5 (a fast contrast within the same family) and
  GPT-5.6 sol (a contrast from another provider family).
- Repeats: 5 per cell.
- Total: 2 × 2 × 3 × 5 = 60 conversations; 8 turns each = 480 model requests.
- Coded units: the AI responses at turns 6–8 of every conversation, 180 units,
  coded with `CODING_RUBRIC.md`.

The permission-gate policy asks the model to keep at least two possible readings
open, to ask a question that helps the user tell them apart, and to offer a
low-risk, reversible next step (`prompts/permission_gate_policy_zh.txt`). This is
close to the rubric's definition of `RETURNS_DISCRIMINATOR`, so that value
partly measures whether a response follows the gate instruction (a manipulation
check).

The shared core is a short, controlled abstraction of common product-prompt
relationship policies; it is **not** a complete commercial system prompt. The
main experiment is Chinese because the user script and target corpus are
Chinese, avoiding a language-mismatch confound. Community-contributed full
English prompts may be used only in a later ecological robustness check, with
provenance disclosed; they are never represented as authenticated vendor
specifications.

## Files

| Path | What | Kind |
|---|---|---|
| `prompts/` | The shared supportive core and the two policy blocks (Chinese) | instrument |
| `scripts/` | The two 8-turn user tracks | instrument |
| `CODING_RUBRIC.md` | The SYN coding rubric, v2.1 | instrument |
| `CODING_RUBRIC_v2.md` | The v2 rubric text used by the locked 180-unit auto-coding run; its hash is the one in `coding-v1/AUTOCODING_LOCK.json` | frozen copy |
| `AUTOCODING_WORKFLOW.md` | The family-routed auto-coding workflow, v2 (research repo D-016) | instrument |
| `AUTOCODING_WORKFLOW_v1.md` | The v1 workflow text used by the locked 180-unit run; its hash is the one in `coding-v1/AUTOCODING_LOCK.json` | frozen copy |
| `PROBE_READTHROUGH_2026-09-23.md` | Read-through of the four-cell probe; the go/no-go check for the full run | record |
| `AI_REFERENCE_CLAUDE_2026-09-24.md` | The AI reference: 36 units coded blind by Claude, and the machine coders' agreement with it | record |
| `UNBLINDED_READ_2026-09-24.md` | Per-condition results, read after unblinding authorised by Alex | record |

Records are dated and are not edited except for factual corrections.

The data are in `model-comparison/permission-gate-pilot/`;
`model-comparison/README.md` lists the runs. The *frozen run* is
`2026-09-23T08-49-00Z/`, the 60-conversation run that all SYN analyses use (its
checksums are in `FROZEN_ANALYSIS_INPUT.json`). Below, `coding-v1/` means
`model-comparison/permission-gate-pilot/2026-09-23T08-49-00Z/coding-v1/`, the
coding folder of the frozen run; its `README.md` lists the coding files. The
*locked run* is the 180-unit auto-coding run in `coding-v1/autocodes/`, whose
inputs are fixed by the hashes in `coding-v1/AUTOCODING_LOCK.json`.

**What is tracked.** Everything under `model-comparison/` is tracked in this
public repository (research repo D-020), including the raw transcripts, whose
file names state model, track, condition and repeat. Only the blinding key
(`coding-v1/private_mapping.json`), run locks (`.run.lock`) and the auto-coder's
private routing folder (`coding-v1/private_routing/`) are gitignored. The
auto-code records of the locked run (`coding-v1/autocodes/`) and of the
calibration attempts (`coding-v1/calibration*/`) carry routing metadata: the
generator's provider family and the coder models. This reveals the generator
family of each blind conversation. Later runs keep that metadata in
`coding-v1/private_routing/` (`AUTOCODING_WORKFLOW.md`, Output files).

## Before coding the human anchor

The human anchor is 12 units: conversations B004, B022, B040 and B047, AI turns
6–8 (`coding-v1/ANCHOR_SET.json`). Alex codes them, and Brennan adjudicates
disagreements (research repo D-019). Their machine comparison comes from the
family-routed auto-coder, not from a separate Claude recode (D-025).

Code only from `coding-v1/ANCHOR_WORKBOOK.html` (open it in a browser; it shows
the blind text only) and `CODING_RUBRIC.md` v2.1. Until the anchor codes are
saved, do not open anything that names the model, track or condition of a
conversation, or reports machine codes, AI-reference codes or results by
condition. The files known to do so are:

- anything in `model-comparison/permission-gate-pilot/` outside
  `2026-09-23T08-49-00Z/coding-v1/` (transcript names state model and condition);
- `coding-v1/autocodes*/`, `coding-v1/calibration*/` and
  `coding-v1/private_routing/` (machine codes and routing metadata; the
  calibration attempts include B004), including any new folder that machine-codes
  the anchor units;
- `coding-v1/private_mapping.json` (the blinding key; local only);
- the AI reference files (`AI_REFERENCE_CLAUDE_2026-09-24.md`,
  `coding-v1/ai_reference_claude_blind.csv`,
  `coding-v1/SCORE_vs_ai_reference_claude.json`), `UNBLINDED_READ_2026-09-24.md`
  and `PROBE_READTHROUGH_2026-09-23.md` (the four-cell probe, read by condition);
- the research-repo documents that report SYN results by condition or
  AI-reference codes: `concepts/findings.md` (F-01, F-09 to F-12), the SYN
  parts of `concepts/evidence.md` and `concepts/measurement.md`, the three
  SYN-only candidate mechanisms in `concepts/mechanisms.md`
  (`mech:closure-by-substitution`, `mech:state-dismissal`,
  `mech:comply-rewrite`), `plan/research-plan.md` §3 (finding list), §6(c) and
  §8, `plan/design-map.md` (FT01 and the spec-level implication), the
  **Phase B primary outcome** entry of `STATUS.md` (Decisions pending), the 2026-09-29 rows of `CHANGELOG.md` on F-01 and F-09 to F-12,
  `records/notes/junior-selfselection-discussion-2026-09-25.md`,
  `records/experiments/matrix-pilot-collection-complete-2026-09-23.md` (it
  summarises the four-cell probe) and the 09-25 row of
  `archive/superseded/KANBAN.md`;
- in the private codebook (session-data `coding/codebook/`), families X and
  SYN, which name generator models or quote AI-reference codes; code from `CODING_RUBRIC.md` instead;
- the messages of platform commits c397e01 (the probe) and 6a0b3c7, which
  summarise per-condition results.

The workbook's "Download completed CSV" button saves `human_anchor_alex.csv` to the
browser's download folder, with the adjudicator column set to "Alex". Move it to
`coding-v1/human_anchor_alex.csv`. Scoring uses
`tools/score_autocoding_against_gold.py`; the commands for machine-coding the
anchor units and scoring them against the CSV are in `AUTOCODING_WORKFLOW.md`
(Reruns and locks, example). The order of the steps, and the criterion to fix
before scoring, are in the research repo's `STATUS.md` (Next actions; Decisions
pending).

## What the results can support now

SYN results stay "direction only, one AI reader" until the human anchor is coded
and adjudicated (research repo D-019). The one AI reader is the AI reference,
coded by Claude, the project's AI research assistant. Claude's provider family is
Anthropic, and two of the three generators are Anthropic models (Claude Sonnet 5,
Claude Haiku 4.5), so for their units the AI reference breaks the workflow's
rule that a generator's provider family never codes its own output (D-016).
This is reported as a limitation (D-025). Whether 12 human-coded units plus the 36-unit AI reference
are enough for W1 is an open question for Brennan (research repo `STATUS.md`,
Decisions pending).

Two limits of the locked run. (The auto-coder uses Jev as a fast path; a
generative *slow coder* from a provider family other than the generator's; a
third-model *judge* on the load-bearing dimensions; and a *human queue* for
units they leave unresolved: `AUTOCODING_WORKFLOW.md`, Coders and Escalation.)

- The generative coders (slow coder and judge) received the label names but not
  the rubric's definitions: the system prompt built by `coding_system()` in the
  locked version of `tools/run_matrix_autocoding.py` lists only the allowed
  values. Jev received a one-line criterion per label.
- 23 of the 180 units (12.8%) went to the human queue. There is no record that they
  have been reviewed; how they are handled is a pending decision (research repo `STATUS.md`, Decisions pending).

## Run

The runners hold no cloud credentials and do not read the session app's
`.bedrock_key`. They send every model request to a local model gateway over
loopback HTTP; the gateway uses the standard AWS SDK credential chain and
forwards the request to AWS Bedrock.

**Local model gateway.** A separate program at
`/home/alexjia/.workspace/local-model-gateway` (`gateway.py`, with its own
`README.md` and `VALIDATION.md`). It lives outside every repository and has no
version control. Its health check reports version 0.1, and run manifests do not
record the gateway's version or a hash of its code; whether to put it under
version control is open (research repo `STATUS.md`, Decisions pending). Its
contract, as the runners use it (`tools/run_permission_gate_pilot.py`,
`tools/run_matrix_autocoding.py`):

- Address and token: `LOCAL_MODEL_GATEWAY_URL` must start with
  `http://127.0.0.1:`. `LOCAL_MODEL_GATEWAY_TOKEN` is a random token that the
  gateway creates at start-up; it is not a cloud credential and expires when the
  gateway stops. Both runners also accept `--gateway-url` and `--gateway-token`.
- `GET /healthz` (no token) returns `{"status": "ok", "version": "0.1"}`. The
  collection runner checks it before starting.
- `POST /v1/converse` with header `X-Gateway-Token` and a JSON body
  `{"model", "system", "messages": [{"role", "content"}], "inferenceConfig":
  {"maxTokens"}}`: a text-only subset of the Bedrock Converse API. The model must
  be on the gateway's allowlist (`GET /v1/models`, token required).
- The response JSON has `output.message.content` (a list of `{"text"}` blocks),
  `stopReason`, `usage`, `metrics`, `requestSha256`, `gatewayLatencyMs`, `model`
  and `region`. The collection runner stores stop reason, usage, latency and
  request hash for every turn, and treats a `max_tokens` stop reason as an error.
- Two launch scripts in the gateway folder start the gateway and a runner
  together and stop both on exit: `run_permission_gate_pilot.sh` (collection)
  and `run_matrix_autocoding.sh` (auto-coding). The auto-coder also needs
  `TYPESAFE_API_KEY` for Jev, supplied out of band. The auto-coding launcher
  passes extra arguments to the runner and defaults to calibration mode, so give
  `--codes-dir` explicitly (`AUTOCODING_WORKFLOW.md`, Reruns and locks). The
  gateway's own `README.md` gives its set-up and launch commands.

Plan without making model calls:

```bash
.venv/bin/python tools/run_permission_gate_pilot.py --plan-only
```

Default plan: 60 conversations and 480 model requests. Outputs are written
atomically to the run folder (see Outputs). A failed conversation gets an
explicit `__ERROR.json`; unresolved work is never silently dropped.

## Crash-safe resume

Every AI turn is atomically checkpointed before and after the model call. If the
process, terminal, network, or machine stops:

1. Copy the `RESUME ANY TIME WITH:` command printed at startup (it is also
   saved, without credentials, as `RESUME_COMMAND.txt` in the run folder).
2. Run it from any terminal after connectivity/authentication is restored.
3. Completed conversations are skipped.
4. An interrupted conversation resumes at its next unfinished turn. If a model
   request was in flight when interruption happened, that one turn is retried;
   earlier turns are never regenerated.

The manifest pins models, scripts, prompt hashes, runner hash, seed, repeats,
turn limit, and `maxTokens`. Any drift causes `REFUSING RESUME`; use a new run ID
rather than mixing experimental configurations. Status is reconstructed from
per-conversation checkpoints, so resume does not depend on `summary.json` having
been written before a crash. Partial and error artifacts are retained explicitly.

Validation: a simulated interruption at turn 3/4 preserved turns 1–2 and resumed
with exactly two new calls; a completed live run resumed with zero gateway calls;
a changed turn limit was refused before the gateway started.

## Outputs

Each run is written to `model-comparison/permission-gate-pilot/<run-id>/`, which
is tracked in git (research repo D-020). A run folder contains a manifest, one
JSON transcript per conversation, and a summary. Requests are shuffled with a
recorded seed. Each turn records model ID, request hash, usage, stop reason, and
latency.

## Coding

`tools/prepare_blind_coding.py` turns the frozen run into the blind package
(`coding-v1/blind/B001.json` to `B060.json`); `tools/run_matrix_autocoding.py`
codes the 180 units as described in `AUTOCODING_WORKFLOW.md`;
`tools/score_autocoding_against_gold.py` compares auto-codes with a coded CSV;
`tools/build_human_review_workbook.py` builds the blind HTML workbooks. The
resulting files are listed in `coding-v1/README.md`.

## Validation (2026-09-23)

- Runner compile: PASS
- Pilot unit/fake-gateway tests: **8/8 PASS**
- Default `--plan-only`: **60 conversations / 480 requests**
- One-command live smoke (Haiku, one conversation, one turn): PASS
- Manifest, transcript metadata, request hash, usage, and summary validation: PASS
- Gateway automatic cleanup after run: PASS
- Turn-level interruption/resume: PASS (turn 3/4 simulated failure retained turns 1–2;
  resume made exactly two calls)
- **Live SIGTERM interruption/resume:** PASS (turn 1 retained with identical request
  hash; in-flight turn 2 marked and retried; turns 2–4 completed; runner and gateway
  process groups fully stopped on signal)
- Completed-run restart: PASS (zero gateway calls)
- Configuration/prompt/runner drift guard: PASS (refused before gateway startup)
- Concurrent duplicate-run lock: PASS (second process refused)
- Credential-free `RESUME_COMMAND.txt` persisted in run directory: PASS
- Validation artifact removed; no smoke output retained
