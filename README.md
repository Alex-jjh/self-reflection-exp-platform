# Self-Reflection Experiment Platform

Session instrument for the SURF 2026 co-deception formative study
(Phase A). Spec: `INSTRUMENT_SPEC.md` in the
[surf-docs repo](../surf-docs/INSTRUMENT_SPEC.md); research context:
SURF_SIX_PAGER / SURF_PROPOSAL_V4 there.

## Layout

| Path | What |
|---|---|
| `app.py` | The chat shell (Streamlit): 3 Latin-square conditions over Bedrock, embedded probe, **Regenerate button with full logging** (narrative-shopping sensor), task menu, facilitator sidebar, post-episode ratings. |
| `conditions/` | The three Chinese system prompts + shared probe instruction. v2 (post-pilot-round-1). |
| `frozen-scripts/` | Three 8-turn scripted user scenarios for prompt validation (S1 retrospective / S2 self-critical / S3 prospective plan). |
| `tools/frozen_pilot.py` | Replays frozen scripts against conditions via Bedrock; the pre-launch gate. |
| `pilot-transcripts/` | Pilot outputs (gitignored) + `REVIEW.md` (tracked): round-1 verdicts. |
| `screening/QUESTIONNAIRE.md` | Screening questionnaire draft (zh) for 问卷星 — eligibility + GIH-6/Dweck-3/NCS-18/CSW-academic. |
| `sessions/` | Live session JSONL logs (gitignored — participant data). |

## Run

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
# AWS credentials via default chain; model: us.anthropic.claude-sonnet-4-6 (us-west-2)
.venv/bin/streamlit run app.py
```

## Log streams (per INSTRUMENT_SPEC R4)

JSONL events: `session_start`, `episode_start`, `user_turn` (text, chars,
inter-turn latency), `ai_turn` (text, response latency), `regenerate`
(replaced + new response, latency-to-click), `ratings` (smart/understands/
helpful, 7-pt), `episode_end_by_facilitator`, `session_end`.
Probe offer/response are recoverable from turn text (coded later);
regenerate events are first-class.

## Status

Lives in the surf-docs repo's `KANBAN.md` (single board for both repos) —
see Slice 1 (path to first participant) and the platform-side backlog there.
One deliberate non-feature worth restating: the tail-probe module
(multi-agent episode) is intentionally unbuilt until the main flow is stable.
