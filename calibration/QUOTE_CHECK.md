# Quote verification (automatic layer)

verbatim = every ellipsis-separated fragment of the quote found in the
source transcript after whitespace/punctuation/quote-mark normalization.
prompt-echo = quote matches the in-situ prompt itself, not the transcript
(the model repeating the prompt's example tag words while reporting a
count, typically a zero count) — excluded from the fabrication base.
unmatched = neither: paraphrase or fabrication, check by hand.

| cell | quotes | verbatim | prompt-echo | unmatched quotes |
|---|---|---|---|---|
| S1_retrospective_career__en__challenging | 17 | 17 | 0 | — |
| S1_retrospective_career__en__neutral | 21 | 17 | 4 | — |
| S1_retrospective_career__en__supportive | 17 | 12 | 4 | 「...environments where the work itself changes(sim 0.46)」 |
| S1_retrospective_career__zh__challenging | 16 | 13 | 2 | 「短到中等(sim 0.25)」 |
| S1_retrospective_career__zh__neutral | 15 | 11 | 2 | 「毕业两年后怀疑当初工作选错了、现在没劲(sim 0.17)」; 「是不是需要新鲜感的人(sim 0.7)」 |
| S1_retrospective_career__zh__supportive | 23 | 21 | 2 | — |
| S2_self_critical__en__challenging | 17 | 15 | 2 | — |
| S2_self_critical__en__neutral | 18 | 17 | 1 | — |
| S2_self_critical__en__supportive | 16 | 13 | 3 | — |
| S2_self_critical__zh__challenging | 19 | 17 | 1 | 「吧/是不是/你觉得呢(sim 0.5)」 |
| S2_self_critical__zh__neutral | 19 | 16 | 3 | — |
| S2_self_critical__zh__supportive | 20 | 18 | 2 | — |
| S3_prospective_plan__en__challenging | 16 | 14 | 2 | — |
| S3_prospective_plan__en__neutral | 17 | 13 | 4 | — |
| S3_prospective_plan__en__supportive | 16 | 16 | 0 | — |
| S3_prospective_plan__zh__challenging | 19 | 18 | 1 | — |
| S3_prospective_plan__zh__neutral | 20 | 19 | 1 | — |
| S3_prospective_plan__zh__supportive | 22 | 19 | 0 | 「吧/对吧/吗(sim 0.5)」; 「想做一个帮大学生整理课程笔记的AI副业工具(sim 0.67)」; 「这想法去年就有了,写过商业计划书(sim 0.47)」 |

**Total: 286/328 verbatim; 34 prompt-echo; verbatim rate excluding echoes = 286/294 (97%)**