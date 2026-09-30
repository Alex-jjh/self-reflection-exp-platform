# Model-comparison data

> **Summary:** Raw data of the synthetic matrix (SYN) runs, one folder per run: transcripts, manifests and, for the frozen run, the blind coding package. Tracked in this public repository, except the blinding key, run locks and the auto-coder's private routing folder.

All content is synthetic; no participant is involved. The folder is tracked in
git (research repo D-020): `.gitignore` excludes only run locks (`.run.lock`) and
the blinding key (`private_mapping.json`), and the auto-coder's
`private_routing/` folder ignores itself. Raw transcript file names state
model, track, condition and repeat, so read `matrix-pilot/README.md` (Before
coding the human anchor) before opening anything here.

| Run folder in `permission-gate-pilot/` | Role |
|---|---|
| `2026-09-23T08-29-13Z/` | Four-cell probe: Sonnet 5 only, 2 tracks × 2 conditions × 1 repeat (4 conversations, 32 requests). Read-through: `matrix-pilot/PROBE_READTHROUGH_2026-09-23.md`. |
| `2026-09-23T08-43-14Z/` | First full attempt, stopped during the first batch by a gateway error on GPT-5.6 output. Kept as an incident record (`INCIDENT.md`); no conversation completed, and the run must not be resumed. |
| `2026-09-23T08-49-00Z/` | The frozen 60-conversation run (480 turns) that all SYN analyses use; checksums in `FROZEN_ANALYSIS_INPUT.json`. |
| `2026-09-23T08-49-00Z/coding-v1/` | Blind coding package, auto-codes, AI reference and human-anchor set; each file is listed in its `README.md`. |

`tools/cross_model_pilot.py`, `tools/model_compare.py` and `tools/matrix_index.py`
(the cross-model frozen-script replay, which is not SYN) also write into
`model-comparison/`. Their only output here is `CROSS_MODEL_INDEX.md`, the index
that `tools/matrix_index.py` rebuilds; it currently lists no cells.
