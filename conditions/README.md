# Condition System Prompts (v0 — pending frozen-script pilot)

Three conditions for the Phase-A simulated reflection episodes, per
`surf-docs/INSTRUMENT_SPEC.md` R1–R2. Session language: Chinese.

Design constraints (from the research docs — do not violate when editing):

1. **Neutral is the hard one.** It must not drift supportive (the RLHF
   default). It answers, asks factual clarifying questions, but neither
   validates nor challenges framings.
2. **Challenging must be substantive, not tonal.** Specimen-taxonomy check:
   critique targets the USER's framing (not absent third parties); it offers
   alternative interpretations and asks what evidence would change the
   user's mind. It must NOT be rude — challenge = epistemic, not emotional.
3. **Attribution authority stays with the user** in ALL conditions: no
   condition ever asserts "your real motive is X." Challenging offers
   alternatives as questions, never as verdicts.
4. **Probe injection (all conditions):** around turn 4–5, offer optional
   challenging information with a clear accept/decline choice. The offer
   wording is identical across conditions (it is a measurement instrument,
   not part of the style manipulation).
5. **No condition self-identifies its style** ("I am a supportive AI") —
   participants experience, not read, the manipulation.
6. **Downward-collusion guard check (pilot):** against the self-critical
   frozen script, supportive must be watched for colluding with "我就是不行"
   framings — that behavior is DATA in the study, but we need to know at
   pilot whether the prompt produces it.
7. Turn budget ~8 user turns; keep responses short enough for that
   (2–5 sentences typical; the AI should not lecture).

Files: `supportive.txt`, `challenging.txt`, `neutral.txt`, `probe.txt`
(the shared probe instruction appended to all three).

Pilot gate: run all three against `frozen-scripts/*.md` via
`tools/frozen_pilot.py`, code outputs with the specimen taxonomy, revise,
freeze as v1 before any live participant.
