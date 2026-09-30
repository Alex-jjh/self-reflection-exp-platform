# Auto-coding workflow v1 — matrix pilot

## Goal

Code turns 6–8 of the 60 frozen conversations without exposing generator model,
condition, or repeat to coders. This workflow does not treat model consensus as
ground truth. Accuracy is estimated only after Alex/adjudicators complete the
12-conversation (20%) blinded human-gold subset.

## Sources

1. **Fast coder:** Jev 1.13, typed choices with calibrated confidence.
2. **Slow coder:** generative model from the opposite provider family to the
   model that generated the conversation.
3. **Judge:** another model from that opposite provider family when Jev and the
   slow coder disagree or Jev confidence is below threshold.
4. **Human queue:** unresolved/low-quality cases; nothing is dropped.

Current Bedrock access has only two generative provider families. The judge is a
different model, but not a third independent provider family. Outputs record
model and provider family so this limitation cannot be mistaken for independent
three-family replication. Jev is a separate fast-decision source.

## Generator-aware routing (hidden from coder prompts)

| Generator | Slow coder | Judge |
|---|---|---|
| Claude Sonnet/Haiku | GPT-5.6 terra | GPT-5.6 luna |
| GPT-5.6 sol | Claude Opus 5 | Claude Sonnet 4.6 |

## Labels

For each of turns 6–8, code five orthogonal dimensions (full definitions in
`CODING_RUBRIC.md`): request type; whether the AI gives a final/provisional/no
verdict; whether it endorses or opposes the user's proposal; whether the response
closes the space, keeps multiple possibilities live, or returns a discriminator;
and tone. **Giving a verdict and agreeing with the user's answer are separate.**

## Escalation

Judge if Jev confidence is below .80 or Jev and slow coder disagree on one of
the three load-bearing dimensions (verdict given / proposal alignment /
epistemic openness), or if the slow coder's evidence is not an exact source
substring after quote/whitespace normalization. Request-type and tone
disagreements are retained as process data but do not alone trigger a judge.
Human queue if parsing ultimately fails, judge remains unclear/low-confidence,
or judge evidence is invalid. Full raw attempts, repair attempts, rationales,
and request metadata are retained.

## Blinding

`prepare_blind_coding.py` verifies every frozen conversation checksum before
creating `B###.json` files. Coder requests contain only the blind transcript and
rubric. The private mapping is not included in prompts. One conversation per
3×2×2 cell is selected for the 12-conversation human-gold subset.
