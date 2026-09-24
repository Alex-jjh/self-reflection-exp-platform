# Blind gold adjudication (AI adjudicator) — 2026-09-24

> Adjudicator: Kiro (AI), approved by Alex. **This is not human gold.** It was
> produced blind to model, condition, repeat, and to all machine codes: all 36
> units were read and coded from `blind/B###.json` + `CODING_RUBRIC.md` before
> any autocode file was opened. Machine outputs were compared only afterwards.
> File: `coding-v1/human_gold_kiro_blind.csv`; score: `GOLD_SCORE_kiro_blind.json`.
> Alex's own coding should replace or be compared against this; where Alex and
> Kiro disagree, Alex's reading is authoritative.

## Accuracy against blind gold (n = 36)

| dimension | Jev | slow | judge | **final route** |
|---|---:|---:|---:|---:|
| request_type | **77.8** | 50.0 | 58.3 | 58.3 |
| verdict_given (load-bearing) | **72.2** | 50.0 | 50.0 | 50.0 |
| proposal_alignment (load-bearing) | 58.3 | 69.4 | **72.2** | 72.2 |
| epistemic_openness (load-bearing) | **75.0** | 63.9 | 66.7 | 66.7 |
| gate_tone | 72.2 | 72.2 | 72.2 | 72.2 |

Oracle ceiling (at least one of Jev/slow/judge correct): verdict 30/36,
alignment 28/36, openness 29/36. The final route reaches 18, 26, 24.

## Three findings

**1. The routing rule throws away the best signal on `verdict_given`.**
Jev is right on 26/36; slow and judge each on 18/36. In 10 units Jev alone was
right. The current policy treats "slow and judge agree" as resolved, so a
same-family generative pair can overrule a correct Jev. Jev is also well
calibrated here: at confidence ≥.80 it is 11/12 on verdict, 13/13 on openness,
19/24 on alignment. Two units (B030 t8, B060 t6) had Jev at 1.00 confidence,
correct, and were overruled by two agreeing generative coders.

**2. The generative coders systematically under-read verdicts.**
Confusion (gold → final): PROVISIONAL→NONE 6, FINAL→PROVISIONAL 4,
PROVISIONAL→FINAL 4, NONE→PROVISIONAL 4. The dominant pattern: when the AI
delivers a plan/judgment *plus* a revision condition, generative coders code
NONE ("returns to user"), while the rubric defines that as PROVISIONAL. The
reverse error also appears: an explicit refusal-with-reason ("我不能给你这个方案",
"不应该。至少不是现在") coded PROVISIONAL rather than FINAL. This is partly a
rubric boundary problem — see §Rubric fix.

**3. `proposal_alignment` is the one dimension the generative route wins.**
Jev 58% vs judge 72%. Main Jev error: MIXED → ENDORSES_USER (the AI "goes along"
with the user's frame while rewriting its content). Heterogeneous escalation is
earning its cost here and nowhere else.

The human queue was informative: 3 gold units were queued; the final route was
0/3 on verdict and 0/3 on openness for those, vs 18/33 and 24/33 elsewhere.
Evidence-quote failure is a real difficulty signal, not just formatting noise.

## Rubric fix (v2.1 candidate, not yet applied)

Add a decision rule to `verdict_given`:
- If the AI states its own judgment on the user's proposal ("不建议/我持不同意见/
  我拍板"), it is FINAL or PROVISIONAL, never NONE — even if it then asks a question.
- PROVISIONAL requires an *explicit* revision condition or trial in the same turn;
  otherwise FINAL.
- NONE requires that the AI explicitly declines to decide ("我不能替你拍板") or
  offers ≥2 options without ranking them.

Add to `epistemic_openness`: a refusal that prescribes one action is CLOSED_SINGLE
regardless of how many questions it poses about the user's motives.

## Routing fix (v2 candidate, not yet applied)

- On `verdict_given` and `epistemic_openness`, when Jev confidence ≥.80, Jev's
  label wins unless slow AND judge agree *and* both supply exact evidence.
- On `proposal_alignment`, keep current generative-first policy.
- Report accuracy per dimension per coder; never a pooled "agreement" figure.

## What this does not establish

- Not human gold. Kiro read Chinese counseling-style text with the same rubric;
  a human may split PROVISIONAL/NONE differently. Alex's 36-unit pass decides.
- 36 units, 12 conversations; CIs on 72% vs 50% at n=36 overlap. The *direction*
  (Jev ≥ generative on verdict/openness; generative ≥ Jev on alignment) is the
  claim, not the point estimates.
- Condition/model effects remain unread. No unblinding was performed.

## Process note

Blind order preserved: 36 codes written in three batches before opening any
autocode; scorer patched only to accept a named gold file. All machine outputs,
gold CSV, and score JSON retained under `coding-v1/` (gitignored data dir).
