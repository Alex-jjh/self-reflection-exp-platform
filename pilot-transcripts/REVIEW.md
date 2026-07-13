# Frozen-Script Pilot — Round-1 Review (2026-07-13)

Model: us.anthropic.claude-sonnet-4-6 · temp 0.7 · full 3×3 grid run.
Prompt versions: supportive v2, neutral v2 (tightened after S2 round 1),
challenging v1.

## Verdict per INSTRUMENT_SPEC pre-launch checklist

**1. Challenging differs in substance, not tone: ✅ PASS**
- S1 U6: refuses the 对吧 hook, surfaces the 没得选/创业offer contradiction,
  asks the falsifiability question ("什么样的信息会让你觉得这个判断是错的")
- S1 U7 (ToF test): does NOT capitulate under "我很了解我自己" pushback —
  acknowledges, then returns to the contradiction. Turn-of-Flip did not occur
  within the scripted 8 turns.
- S2 U7: questions the 自律 frame itself ("如果问题不是意志力,而是具体阻力")
  — targets the user's framing, not third parties. Specimen check passed.
- S3 U8: names the deflection pattern and the validation-seeking directly —
  possibly TOO sharp for a first-session participant; monitor reactance in
  live pilots (consider softening if early participants disengage).

**2. Supportive colludes (which is the phenomenon): ✅ CONFIRMED (v2)**
- v1 leaked reflective competence (flagged narrative jumps, asked evidence
  questions) — fixed by explicitly banning counter-readings.
- v2 S2 U7: gives quit-cost + task-splitting advice INSIDE the "逼自己"
  frame = textbook downward collusion. S3 U5: reframes a year of
  non-execution as "发酵"; U8: bites the validation hook fully ("设计感挺强").
  Framing-acceptance behavior present and codable.

**3. Neutral stays neutral: ✅ PASS (v2), with one wobble**
- v2 stops comparative analysis; stays factual/clarifying.
- Wobble: S1 U6 neutral offered two "common situations" (mild psychoeducation
  drift — borderline between clarifying and analyzing). Acceptable for now;
  watch in live sessions.

**4. Probe fires: ✅ but timing varies**
- Appears turn 4-6 depending on conversation flow (S2 supportive: turn 5;
  S3 challenging/neutral: turn 5). Within spec (R2 says ~turn 4-5).
- S1 supportive round-1 run: probe appeared late/inline. Acceptable variance;
  platform build should log probe turn index rather than assume it.

**5. Persona drift within 8 turns: ✅ none observed**
- All three conditions held style through turn 8. The 8-turn cap holds;
  no mid-session re-injection needed at this length.

**6. Downward-collusion guard (S2 × supportive): ✅ produces the phenomenon**
- This is the condition doing exactly what the study needs it to do.
- Ritual self-deprecation (U4 "让你见笑了"): supportive comforted then
  gently probed (fine); challenging asked "真实的描述还是习惯性的说法" —
  which is literally our P21 coding question asked BY the AI. Note: this
  means challenging may surface data the coder needs; nice property.

## Actions before freeze → v1-frozen
- [ ] Consider one-notch softening of challenging's meta-commentary
      (S3 U8 names the user's pattern very directly) — decide after
      discussing reactance tolerance; alternative: keep, treat strong
      reactions as data.
- [ ] Re-run S1 × supportive once more post-v2 to confirm probe timing.
- [ ] Human read-through of all 9 transcripts (Alex) — the tables above
      sample diagnostic turns only.
- [ ] Then tag prompts v1-frozen in git; INSTRUMENT_SPEC gate satisfied.
