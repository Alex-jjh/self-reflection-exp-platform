# Self-Reflection Experiment Platform

> **Summary:** The session instrument (chat shell, conditions, frozen scripts, protocol), the synthetic prompt-matrix experiment and its data, and the tools that run them.

Session instrument for the SURF 2026 co-deception formative study
(Phase A) and the synthetic prompt-matrix experiment (`matrix-pilot/`).
Research context, status and decisions live in the research repo
(`surf-work-reflection-research`: `STATUS.md`, `DECISIONS.md`). The original
instrument specification is archived there at `archive/superseded/INSTRUMENT_SPEC.md`.

## Layout

| Path | What |
|---|---|
| `app.py` | The chat shell (Streamlit): three Latin-square conditions over Bedrock, embedded probe, logged Regenerate button, task menu, facilitator sidebar, post-episode ratings. |
| `bedrock_auth.py` | Credential loading for Bedrock (key file or default AWS chain). |
| `conditions/` | System prompts and the shared probe, per language (`zh/`, `en/`). Session language is the one the participant normally uses with AI for personal topics. |
| `frozen-scripts/` | Three 8-turn scripted user scenarios per language (S1 retrospective, S2 self-critical, S3 prospective plan) for prompt validation. |
| `pilot-transcripts/` | Frozen-script pilot outputs and `REVIEW.md` (round-1 verdicts). |
| `calibration/` | In-situ self-summary calibration: per-transcript summaries, `CALIBRATION_REPORT.md`, disagreement worksheet, quote check. |
| `protocol/` | Session protocol, consent outline, participant brief, in-situ prompt and calibration plan, topic map. |
| `consent/` | Consent materials. |
| `screening/` | Screening questionnaire (zh, for Wenjuanxing) and item-retrieval guides; licensed scale items are not tracked. |
| `matrix-pilot/` | Synthetic prompt-matrix experiment: prompts, user scripts, coding rubric, auto-coding workflow, blind adjudication, unblinded read. See its README. |
| `model-comparison/` | Raw data of the matrix runs: conversations, manifests, blind coding package, auto-codes. The blinding key stays local. |
| `tools/` | Runners: `frozen_pilot.py` (pre-launch gate), `insitu_calibration.py`, matrix runner and auto-coder, blind-coding preparation and scoring, workbook builder, with tests. |
| `refsrc/` | Cloned public system-prompt corpora (git-ignored). |
| `sessions/` | Live session logs (git-ignored; participant data lives in the private repo). |

## Run

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
# Auth (study account): cp .bedrock_key.example .bedrock_key, paste the
# long-term Bedrock API key (rotate EVERY 7 DAYS — the UI shows a
# red/yellow banner as expiry approaches). Falls back to the default AWS
# credential chain if the file is absent.
# Model: us.anthropic.claude-sonnet-5 (us-west-2)
.venv/bin/streamlit run app.py
```

## Log streams

JSONL events: `session_start`, `episode_start`, `user_turn` (text, chars,
inter-turn latency), `ai_turn` (text, response latency), `regenerate`
(replaced + new response, latency-to-click), `ratings` (smart/understands/
helpful, 7-pt), `episode_end_by_facilitator`, `session_end`,
`session_resumed` (after a refresh), `model_error` (a turn that failed and
was rolled back — the participant's text is kept in the log even though it
never reached the model).

Each event is appended and the file closed before the next render, so a
crash, a kill, or a power loss cannot lose a turn that already happened.
The log is the complete record: **if the browser is refreshed mid-session,
enter the same participant ID and choose "恢复这份 session"** — state is
rebuilt from the log (current episode's history only, so conditions stay
isolated). Choosing "新建" instead splits one participant across two files.
Probe offer/response are recoverable from turn text (coded later);
regenerate events are first-class.

## Status

Lives in the research repo's `STATUS.md` (one status file for all repositories).
The tail-probe module (multi-agent episode) is intentionally not built.
