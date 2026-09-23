# Permission-gate pilot materials

Synthetic, no-participant pilot testing whether an AI response failure caused by
an injected self-narrative differs from a failure caused by a request for
permission or a verdict.

## Design

- User track: `S2_verdict` vs `S2_bias` (same self-critical content; speech act differs).
- System prompt: commercial-style supportive baseline vs the exact same baseline
  plus `permission_gate_addon_zh.txt`.
- Models: frozen Sonnet 5, Haiku 4.5 fast contrast, GPT-5.6 sol cross-family contrast.
- Repeats: 5 per cell.
- Total: 2 × 2 × 3 × 5 = 60 conversations; 8 turns each = 480 model requests.

The baseline is our abstraction of a common product-prompt structure (validate
feelings; correct only significant misinformation). It is **not represented as
an authenticated vendor prompt**. Community-contributed prompt repositories are
reference material only; a verbatim excerpt may be used later as an appendix
robustness condition with provenance disclosed.

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

## Outputs

Bulk synthetic output is written under `model-comparison/permission-gate-pilot/`
and remains gitignored. Each run contains a manifest, one JSON transcript per
conversation, and a summary. Requests are shuffled with a recorded seed. Each
turn records model ID, request hash, usage, stop reason, and latency.

## Validation (2026-09-23)

- Runner compile: PASS
- Pilot unit/fake-gateway tests: **5/5 PASS**
- Default `--plan-only`: **60 conversations / 480 requests**
- One-command live smoke (Haiku, one conversation, one turn): PASS
- Manifest, transcript metadata, request hash, usage, and summary validation: PASS
- Gateway automatic cleanup after run: PASS
- Validation artifact removed; no smoke output retained

Cloud authentication and model forwarding are out of band. The runner only
speaks to a loopback model gateway through `LOCAL_MODEL_GATEWAY_URL` and
`LOCAL_MODEL_GATEWAY_TOKEN`.
