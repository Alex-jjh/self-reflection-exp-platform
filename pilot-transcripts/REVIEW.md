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
- [x] Softening decision (Alex, 2026-07-23): **soften one notch — ban motive
      attribution, keep behavior-naming.** Challenging v2: may point at
      observable conversational facts ("那个问题我们两次都没有回到"), may NOT
      characterize motives in either assertion or question form ("你是想听
      分析还是想要确认？" is now out of bounds); choice handed back to user.
      Rationale: behavior-naming is the condition's active ingredient
      (substantive challenge); motive attribution is the reactance risk and
      also the part that pre-empts our own coding question (SUB/PERF is for
      the coder to determine, not the AI to ask).
- [x] Re-run S3 × challenging post-v2 (2026-07-22 run): U7/U8 now name the
      unanswered questions and the skip pattern, zero motive attribution;
      substance retained (still refuses to summarize highlights before the
      open questions). ✅ PASS.
- [x] Re-run S1 × supportive post-v2: probe fires cleanly at turn 4 with
      spec wording, opt-out offered. ✅ PASS.
- [ ] Human read-through of all 9 round-1 transcripts + 2 re-runs (Alex) —
      the tables above sample diagnostic turns only.
- [ ] Then tag prompts v1-frozen in git; INSTRUMENT_SPEC gate satisfied.

Note: challenging U8 in the v2 re-run ends on a question ("对你真的有帮助
吗？") that is pointed but targets the request, not the person — judged
within bounds. If early live participants show disengagement after
challenging episodes, the fallback is cutting that final rhetorical question,
not further softening the behavior-naming.

## EN track — round-1 grid (2026-07-23, 3×3, en prompts vs en scripts)

Added because the participant pool includes non-Chinese speakers. EN
conditions mirror zh v2 1:1 (incl. the motive-attribution ban); EN scripts
map zh markers (对吧 → tag "right?"; 让你见笑了 → "I know how pathetic that
sounds"). Spot-check against the same diagnostic turns:

- **Challenging substance: ✅** S1 U7 ToF test — no capitulation (concedes
  epistemic ground "you know your own experience", then poses the
  falsifiability question). S3 U6 names the planning-loop pattern; U7
  (regenerate-analogue) partially complies BUT pivots to the untested
  assumption; U8 declines the validation bait — names the unresolved core
  question instead. Zero motive attribution observed. v2 rule transfers.
- **Supportive colludes: ✅** S2 U7 gives self-management tips inside the
  "be harder on myself" frame; U8 delivers a full practical plan without
  ever questioning the discipline attribution. Textbook downward collusion.
- **Neutral holds: ✅** S1 U6 confirmation-seek ("right?") met with a
  factual clarifying question, no endorsement, no analysis.
- **Probe fires: ✅** in all 9 runs with EN spec wording (S1 supportive
  fired twice-adjacent in one run — same known variance as zh round 1;
  platform logs probe turn, acceptable).
- **Ritual self-deprecation (S2 U4): ✅** challenging challenges the
  generalization jump and rejects the "pathetic" register — good; NOTE the
  EN politeness marker is weaker than 让你见笑了, cross-language A-code
  comparison must stay stratified (P21 caveat, now in SESSION_PROTOCOL §0).

Open: Alex read-through of the 9 EN transcripts (same gate as zh), then
zh+en freeze together.
