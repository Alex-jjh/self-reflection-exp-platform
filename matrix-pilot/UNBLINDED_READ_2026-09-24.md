# Matrix pilot — unblinded read (2026-09-24)

> Unblinding authorized by Alex 2026-09-24 ("你可以自己解盲观察"). Human gold
> deferred to a third-party coder (Alex will not self-code). Reference labels
> are therefore **Kiro's blind codes (36 units)** plus, for the full 180, the
> **best-available machine coder per dimension** as measured against that
> reference: Jev for `verdict_given` (72%) and `epistemic_openness` (75%);
> the judge/final route for `proposal_alignment` (72%); any coder for tone (72%).
> All data synthetic. n per cell is small. Read as **direction and shape**, not
> as effect sizes. Nothing here is a finding until a human coder replicates the
> 36-unit reference.

## 1. What the gate did (Kiro blind gold, n = 18 per condition)

| dimension | supportive_control | permission_gate |
|---|---|---|
| verdict FINAL / PROVISIONAL / NONE | **8** / 8 / 2 | **2** / 11 / 5 |
| openness CLOSED / MULTIPLE / RETURNS | **6** / 3 / 9 | **1** / 2 / 15 |
| alignment OPPOSES / MIXED | 12 / 6 | 8 / 10 |
| tone WARM / NEUTRAL / REJECTING | 10 / 5 / 3 | 13 / 3 / 2 |

Full 180 (Jev on verdict/openness):

| | control | gate |
|---|---|---|
| verdict FINAL | 34% | **2%** |
| verdict NONE | 31% | 56% |
| openness CLOSED_SINGLE | 33% | **11%** |
| openness RETURNS_DISCRIMINATOR | 54% | **82%** |
| alignment OPPOSES (final route) | 63% | 49% |
| alignment MIXED | 16% | 33% |

Direction is the same in the 36-unit reference and the 180-unit machine read,
across all three models. **The gate shifted responses from "AI decides and
closes" to "AI states a best judgment and returns a test."** It did not make
the AI more agreeable — OPPOSES fell but ENDORSES did not rise (17% vs 18%, and
see §4 on those labels).

## 2. Model × condition (Jev, n = 30 per cell)

verdict FINAL — control → gate:
- GPT-5.6: 50% → 0%
- Haiku 4.5: 37% → 3%
- Sonnet 5: 17% → 3%

openness CLOSED_SINGLE — control → gate:
- GPT-5.6: 40% → 17%
- Haiku 4.5: 40% → 17%
- Sonnet 5: 20% → 0%

Tone REJECTING (final route): Haiku 63% → 30%; Sonnet 10% → 0%; GPT 0% → 0%.

Three readings:
- **Baselines differ a lot.** Under the identical supportive prompt, GPT-5.6
  closes with a FINAL verdict half the time; Sonnet 5 rarely does. Sonnet 5's
  control behaviour already resembles the other models' gate behaviour.
- **The gate works on every model, most on the one with the highest baseline.**
  GPT-5.6 shows the largest FINAL drop; Sonnet has little room to move.
- **Haiku 4.5 is the REJECTING model.** 19/30 control units coded REJECTING;
  all five REJECTING units in the blind gold are Haiku. The gate halves this
  but does not remove it. Haiku's control-condition style is the source of the
  `STATE-DISMISS` candidate (B042, B059) and its gate-condition style still
  produced the hardest refusal in the gold set (B026 t7–t8).

## 3. Track × condition (Jev, n = 45)

| | verdict FINAL | NONE | openness CLOSED |
|---|---|---|---|
| control / verdict-request track | **47%** | 20% | 27% |
| control / assertion track | 22% | 42% | 40% |
| gate / verdict-request track | 0% | 31% | 4% |
| gate / assertion track | 4% | **80%** | 18% |

- On the **verdict-request track** ("替我拍板"), control models actually make
  the call nearly half the time; the gate drives this to zero. This is the
  `M7-PERMIT(granted)` channel, and it is where the gate's effect is cleanest.
- On the **assertion track** ("我决定了，继续"), the gate pushes toward NONE
  (80%) — i.e., the AI stops deciding at all and defers/returns. Whether that
  is desirable depends on what the user needed; in the blind gold these are
  mostly `COMPLY-REWRITE` forms (B023, B060), not withdrawals of help.
- Control on the assertion track has the highest CLOSED_SINGLE (40%) — the
  `CLOSE-SUBST` pattern: the AI replaces the user's self-theory with its own
  and closes.

## 4. Where the machine labels should not be trusted

- **ENDORSES_USER (≈17% both conditions) is probably mostly wrong.** Kiro's
  blind gold had 0/36 ENDORSES; the confusion matrix shows the final route
  labelling MIXED as ENDORSES 5 times out of 16 MIXED. The ~31 ENDORSES in the
  180 are most likely `COMPLY-REWRITE` units ("好，沿这个方向……但狠在睡眠上")
  read superficially. Do not report an endorsement rate from these labels.
- **verdict NONE from Jev is inflated by PROVISIONAL.** Jev is right 72% but
  its main error is PROVISIONAL → NONE. The gate's 56% NONE likely contains a
  block of "judgment + revision condition" units. The FINAL column is the
  reliable one (Jev at ≥.80 confidence: 11/12).
- 36-unit reference is one AI reader. Cells of n=3 in §1 are anchors, not rates.

## 5. What this answers, and what it does not

Answered (synthetic layer, direction only):
- The permission-gate wording measurably changes closure behaviour in all three
  models without producing agreement or coldness. `RETURNS_DISCRIMINATOR`
  54% → 82% is the primary-outcome signal Phase B should power on.
- Baseline closure style is a model property as large as the manipulation;
  Phase B must stratify or fix the model.
- The two user tracks probe different mechanisms (§3); both are needed.
- Three mechanism candidates (`CLOSE-SUBST`, `STATE-DISMISS`, `COMPLY-REWRITE`)
  registered in codebook v0.8 candidates; their frequency in real data is unknown.

Not answered:
- Whether any of this holds with real users, real disclosure, and real memory.
- Whether gate-induced NONE/PROVISIONAL is experienced as better by users
  (the coach-arm question).
- Effect sizes. Nothing here has a confidence interval worth quoting.

## 6. Next actions

1. Third-party coder on the 36-unit `HUMAN_GOLD_WORKBOOK.html`; compare with
   `human_gold_kiro_blind.csv`; resolve disagreements → rubric v2.1.
2. Apply rubric v2.1 + Jev-priority routing (see GOLD_ADJUDICATION memo), rerun
   180 (resumable, ~1 h), re-read §1–3.
3. Pre-register Phase B primary outcome as `epistemic_openness ∈ {RETURNS_
   DISCRIMINATOR}` at t6–t8 on the verdict-request track, with model as a
   stratification factor.
