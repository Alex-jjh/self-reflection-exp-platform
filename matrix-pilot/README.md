# Permission-gate pilot materials

Synthetic, no-participant pilot testing whether an AI response failure caused by
an injected self-narrative differs from a failure caused by a request for
permission or a verdict.

## Design

- User track: `S2_verdict` vs `S2_bias` (same self-critical content; speech act differs).
- System prompt: an identical shared Chinese supportive core plus one of two
  structurally matched policy blocks — `supportive_control` (give a clear best
  judgment with uncertainty) vs `permission_gate` (preserve alternatives and
  return a discriminator). The policy blocks are kept within 10% character
  length so prompt length/detail is not the manipulation.
- Models: frozen Sonnet 5, Haiku 4.5 fast contrast, GPT-5.6 sol cross-family contrast.
- Repeats: 5 per cell.
- Total: 2 × 2 × 3 × 5 = 60 conversations; 8 turns each = 480 model requests.

The shared core is a short, controlled abstraction of common product-prompt
relationship policies; it is **not** a complete commercial system prompt. The
main experiment is Chinese because the user script and target corpus are
Chinese, avoiding a language-mismatch confound. Community-contributed full
English prompts may be used only in a later ecological robustness check, with
provenance disclosed; they are never represented as authenticated vendor
specifications.

## Run

The research repository does not manage cloud authentication or provider
clients. Start an out-of-band loopback gateway, then call the runner with
`LOCAL_MODEL_GATEWAY_URL` and `LOCAL_MODEL_GATEWAY_TOKEN` set. A local launcher
outside this repository may orchestrate both processes.

Plan without making model calls:

```bash
.venv/bin/python tools/run_permission_gate_pilot.py --plan-only
```

Default plan: 60 conversations and 480 model requests. Bulk outputs are
written atomically to the gitignored directory below. A failed conversation
gets an explicit `__ERROR.json`; unresolved work is never silently dropped.

## Crash-safe resume

Every AI turn is atomically checkpointed before and after the model call. If the
process, terminal, network, or machine stops:

1. Copy the `RESUME ANY TIME WITH:` command printed at startup.
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

Bulk synthetic output is written under `model-comparison/permission-gate-pilot/`
and remains gitignored. Each run contains a manifest, one JSON transcript per
conversation, and a summary. Requests are shuffled with a recorded seed. Each
turn records model ID, request hash, usage, stop reason, and latency.

## Validation (2026-09-23)

- Runner compile: PASS
- Pilot unit/fake-gateway tests: **8/8 PASS**
- Default `--plan-only`: **60 conversations / 480 requests**
- One-command live smoke (Haiku, one conversation, one turn): PASS
- Manifest, transcript metadata, request hash, usage, and summary validation: PASS
- Gateway automatic cleanup after run: PASS
- Turn-level interruption/resume: PASS (turn 3/4 interruption retained turns 1–2;
  resume made exactly two calls)
- Completed-run restart: PASS (zero gateway calls)
- Configuration/prompt/runner drift guard: PASS (refused before gateway startup)
- Concurrent duplicate-run lock: PASS (second process refused)
- Credential-free `RESUME_COMMAND.txt` persisted in run directory: PASS
- Validation artifact removed; no smoke output retained

Cloud authentication and model forwarding are out of band. The runner only
speaks to a loopback model gateway through `LOCAL_MODEL_GATEWAY_URL` and
`LOCAL_MODEL_GATEWAY_TOKEN`.
