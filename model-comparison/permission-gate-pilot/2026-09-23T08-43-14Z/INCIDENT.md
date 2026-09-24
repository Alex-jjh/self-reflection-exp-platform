# Incident — GPT-5.6 response serialization (2026-09-23)

The first full pilot attempt was stopped during the first batch. Bedrock model
invocation succeeded, but GPT-5.6 Converse content included opaque binary fields.
Gateway v0.1 passed the raw provider `output` object to `json.dumps`, which raised
`TypeError: Object of type bytes is not JSON serializable`; three GPT conversation
starts received HTTP 500. Sonnet and Haiku checkpointing behaved correctly.

Fix: the gateway now constructs a fresh portable response containing only
allowlisted text blocks, string stop reason, and numeric usage/metrics. It never
recursively serializes the provider body. Added two regression tests (binary
fields removed; no-text output rejected) and a live GPT-5.6 smoke test. Gateway
suite 15/15 passed; live GPT returned expected text, usage, stop reason, and hash.

This run is retained as an incident artifact and must NOT be resumed. The runner
and prompt code changed after its manifest was created; the drift guard correctly
requires a new run ID. No conversation in this run reached completion.
