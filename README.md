# Self-Reflection Experiment Platform

> **Summary:** The session instrument (chat shell, conditions, frozen scripts, protocol), the synthetic matrix experiment (SYN) and its data, and the tools that run them.

Session instrument for the SURF 2026 co-deception formative study
(Phase A, the L1 lab sessions) and the synthetic matrix experiment (SYN,
`matrix-pilot/`). Research context, status and decisions live in the research
repo (`surf-work-reflection-research`: `STATUS.md`, `DECISIONS.md`); its
`ARCHITECTURE.md` defines the terms used here (Terms) and the IDs (Identifiers:
L1–L4 and SYN are evidence sources, D-nnn are decisions). The original instrument
specification is archived there at `archive/superseded/INSTRUMENT_SPEC.md`.

What to read first:

- To run a lab session: Run, then Log streams (below), then
  `protocol/SESSION_PROTOCOL.md`.
- To run, rerun or code the synthetic matrix: `matrix-pilot/README.md`. Before
  coding the human anchor, read its section "Before coding the human anchor"
  before opening anything else in `matrix-pilot/` or `model-comparison/`.
- To change a tool: Tests (below).

## Layout

| Path | What |
|---|---|
| `app.py` | The chat shell (Streamlit): the three conditions (supportive, neutral, challenging; their order is set by a Latin square on the participant number), sent to Claude Sonnet 5 on AWS Bedrock; embedded probe, logged Regenerate button, task menu, facilitator sidebar, post-episode ratings. |
| `bedrock_auth.py` | Credential loading for Bedrock (key file or default AWS chain). |
| `conditions/` | System prompts and the shared probe, per language (`zh/`, `en/`). Session language is the one the participant normally uses with AI for personal topics. |
| `frozen-scripts/` | Three 8-turn scripted user scenarios per language (S1 retrospective, S2 self-critical, S3 prospective plan) for prompt validation. |
| `pilot-transcripts/` | Frozen-script pilot outputs, `REVIEW.md` (round-1 verdicts) and `READTHROUGH_SHEET.md`. |
| `calibration/` | In-situ self-summary calibration: per-transcript summaries, `CALIBRATION_REPORT.md`, disagreement worksheet, quote check. |
| `protocol/` | Session protocol, consent outline (with an English summary of the open ethics questions), participant brief, in-situ prompt and calibration plan, topic map. `CODEBOOK_V0.md` is the frozen first codebook; the current codebook is in the private session-data repo, `coding/codebook/`. |
| `consent/` | The official Participant Information Sheet and Consent Form (V1, 2026-06-09) of the umbrella study; see `protocol/CONSENT_OUTLINE.md`. |
| `screening/` | Screening questionnaire items (`QUESTIONNAIRE.md`) and item-retrieval guides. The questionnaire runs on Wenjuanxing as one bilingual form (research repo D-004); the Qualtrics and LimeSurvey build files here (`QUALTRICS_BUILD_SHEET.md`, `IMPORT_README.md`, `REF_qualtrics-encoding.md`, `survey_*`) belong to that abandoned route. Licensed scale items (`screening/items/`) are not tracked. |
| `matrix-pilot/` | The synthetic matrix (SYN): prompts, user scripts, coding rubric, auto-coding workflow, the AI reference and the unblinded read. Its README has the file map, how to run and code it, and what not to open before coding the human anchor. |
| `model-comparison/` | Raw data of the SYN runs: conversations, manifests, blind coding package, auto-codes, AI reference, human-anchor set. Tracked (research repo D-020); only the blinding key, run locks and the auto-coder's private routing folder are not. See its README. |
| `tools/` | `frozen_pilot.py` (pre-launch check of the condition prompts); `insitu_calibration.py` and `insitu_realworld_test.py` (in-situ summary calibration); for SYN, `run_permission_gate_pilot.py` (collection), `prepare_blind_coding.py`, `run_matrix_autocoding.py` (auto-coder), `score_autocoding_against_gold.py` and `build_human_review_workbook.py`; `cross_model_pilot.py`, `model_compare.py` and `matrix_index.py` (cross-model frozen-script replay, not SYN); unit tests `test_*.py`. |
| `refsrc/` | Cloned public system-prompt corpora (gitignored). |
| `sessions/` | Fallback folder for session logs, used only when the private session-data repo is not cloned next to this one; otherwise `app.py` writes logs to session-data `sessions/`. Gitignored. |

## Run

1. Install. The session laptop runs Python 3.9, so keep the code
   3.9-compatible (`requirements.txt`):

   ```bash
   python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
   ```

2. Add the Bedrock key of the study account: `cp .bedrock_key.example
   .bedrock_key`, then paste the long-term Bedrock API key as the first
   non-comment line (the template explains where to generate it). The key must
   be rotated **every 7 days**: the facilitator sidebar shows a yellow warning
   after 6 days and a red one at 7. If `.bedrock_key` is absent, the app falls
   back to the default AWS credential chain.
3. Start the app. It calls `us.anthropic.claude-sonnet-5` in `us-west-2`.

   ```bash
   .venv/bin/streamlit run app.py
   ```

Session logs go to session-data `sessions/` when the private
`self-reflection-session-data` repository is cloned next to this one, otherwise
to `sessions/` here (Layout).

The other key templates (`.gemini_key.example`, `.openai_key.example`,
`.xjtlu_key.example`) are for the cross-model comparison tool
(`tools/model_compare.py`); `app.py` does not use them. All key files are
gitignored. The SYN runners use none of these files: they call a local model
gateway (`matrix-pilot/README.md`, Run).

## Log streams

JSONL events: `session_start`, `episode_start`, `user_turn` (text, chars,
inter-turn latency), `ai_turn` (text, response latency), `regenerate`
(replaced + new response, latency-to-click), `ratings` (smart/understands/
helpful, 7-pt), `episode_end_by_facilitator`, `session_end`,
`session_resumed` (after a refresh), `model_error` (a turn that failed and
was rolled back — the participant's text is kept in the log even though it
never reached the model), `response_truncated` (the reply hit the token limit;
it is still shown, and the event tells the coder the turn is incomplete).

Each event is appended and the file closed before the next render, so a
crash, a kill, or a power loss cannot lose a turn that already happened.
The log is the complete record: **if the browser is refreshed mid-session,
enter the same participant ID and choose "恢复这份 session"** (resume this
session) — state is rebuilt from the log (current episode's history only, so
conditions stay isolated). Choosing "忽略，新建一份" (ignore, start a new one)
instead splits one participant across two files.
Probe offer/response are recoverable from turn text (coded later);
regenerate events are first-class.

## Tests

Unit tests for the tools (`tools/test_*.py`) run from the repository root:

```bash
.venv/bin/python -m unittest discover -s tools -p "test_*.py"
```

## Status

Lives in the research repo's `STATUS.md` (one status file for all repositories).
The tail-probe module, an optional multi-agent episode after the three
one-to-one episodes (research repo `plan/design-map.md`, FT11), is intentionally
not built.
