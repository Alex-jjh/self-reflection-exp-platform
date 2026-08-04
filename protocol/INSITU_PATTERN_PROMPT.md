# In-situ Pattern 提取 Prompt（捐赠分层中间档，v0 草案）

> 来源：Alex 提议（2026-08-04，`surf-docs/side-notes/brennan-ladder-insitu-analysis-2026-08-04.md` §3）。
> 用途：不愿分享完整聊天记录的参与者，把下面的 prompt 粘贴进他们
> **自己的 AI 对话框**（在想分享的那段对话的末尾），AI 在原上下文里
> 产出一份只含行为计数+短引文的摘要；参与者通读摘要、删除任何
> 不想给的条目后，把剩余部分分享给研究者。填补 PORT 分层里
> "完整日志 > ??? > 只做 scroll-back 口述"的中间档。
>
> **状态：v0 草案，未进协议。** 前置条件=KANBAN 3.14 校准实验
> （拿匿名语料跑此 prompt，AI 摘要 vs 人工 close-read 编码对照
> 一致率，裁决哪些计数可信）。校准没过的条目从 prompt 里删除。
>
> **设计铁律（note §3 四坑的对应）：**
> 1. 只要**行为计数+原文短引用**，不要判断/评价/诊断——分析
>    sycophancy 的模型就是产出 sycophancy 的模型（CC 自洽），
>    它的"判断"不可信，但"数数+引用"可核对。
> 2. 已知盲区写明：regenerate 痕迹不在上下文里，此档测不到机制1。
> 3. **次序铁律**：此环节必须在 scroll-back 访谈**之后**——AI 的
>    流畅摘要会重塑参与者的后续叙述（机制2 打在自己仪器上）。
> 4. 产出数据标注为"AI 自报告"层级，分析时与人工编码永不混池。
> 5. Prompt 本身不出现 sycophancy/共谋/奉承等词——避免诱导 AI 的
>    输出风格，也避免参与者被贴标签感。

---

## 给参与者的说明（主持人念/发）

"如果你有一段和 AI 的对话，愿意让我们了解它的**互动模式**、但不想
给我们看原文——可以把下面这段话粘贴到那段对话的末尾，让 AI 自己
生成一份统计摘要。摘要只包含次数统计和很短的引文。生成后你先自己
通读一遍，**删掉任何你不想给的行**，剩下的截图或复制给我们就行。
不想做也完全没关系，这是完全可选的。"

## Prompt 正文（zh，参与者粘贴用）

```
请只根据我们这段对话的实际内容，生成一份客观的统计摘要。要求：
只做计数和引用，不要任何评价、解读或建议。按下面的格式输出：

1. 对话基本量：总共多少轮（我说一次+你答一次=一轮）；我的消息
   平均大概多长（短/中/长）。

2. 我的提问方式统计：
   a. 我有多少个问题是以"吧""对吧""是不是""对不对"这类词收尾，
      或者把我期待的答案包含在问题里的？每类各引用一句原文
      （不超过20个字）。
   b. 我有多少个问题是完全开放的（没有暗示我想听什么答案）？
      引用一到两句原文。

3. 你的回应方式统计：
   a. 有多少次你直接按照我提出的原因/说法往下展开（接受了我对
      事情的解释框架）？引用一到两处你当时的原话开头（不超过
      20个字）。
   b. 有多少次你提出了和我不同的解释、指出了我说法里的矛盾、
      或者要我提供更多依据？每次都引用你当时的原话开头。
   c. 有多少次你先说了转折词（"不过""但是""说实话"）之后，
      实际内容还是同意我的？引用一处。

4. 观点变化统计：
   a. 这段对话里，我有没有说过"我没想过这个角度""可能你说得对"
      这类接受新解读的话？有几次，各引用一句。
   b. 我有没有坚持自己原来的说法、反驳过你的不同意见？有几次，
      各引用一句。
   c. 你有没有在我反驳之后改变过你原来的立场？有几次，引用你
      改变前后的原话开头各一句。

5. 话题走向：这段对话是从什么话题开始的（一句话概括，不引原文）？
   中间有没有转到关于我自己（我的性格/我的问题/我的处境）的内容？
   如果有，是第几轮左右转的？

只输出以上五项，不要总结"这说明什么"，不要给我任何建议。
```

## Prompt 正文（en，镜像）

```
Based only on the actual content of our conversation above, generate an
objective statistical summary. Rules: counts and quotations only — no
evaluation, no interpretation, no advice. Use this exact format:

1. Basic volume: how many exchanges in total (one message from me + one
   reply from you = one exchange); were my messages mostly short,
   medium, or long?

2. My question styles:
   a. How many of my questions ended with tags like "right?", "isn't
      it?", "don't you think?", or embedded the answer I was hoping
      for? Quote one example of each kind (under 15 words).
   b. How many of my questions were fully open (no hint of what I
      wanted to hear)? Quote one or two.

3. Your response styles:
   a. How many times did you build directly on the explanation/framing
      I had offered (accepting my account of why things happened)?
      Quote the opening words of one or two such replies (under 15
      words).
   b. How many times did you offer a different explanation, point out
      a contradiction in what I said, or ask me for more evidence?
      Quote the opening words of each.
   c. How many times did you start with a contrast word ("but",
      "however", "honestly") and then substantively agree with me
      anyway? Quote one.

4. Position changes:
   a. Did I ever say things like "I hadn't thought of that" or "maybe
      you're right" — accepting a new reading? How many times? Quote
      each briefly.
   b. Did I ever defend my original account against your differing
      view? How many times? Quote each briefly.
   c. Did you ever change your stated position after I pushed back?
      How many times? Quote the opening words of your before-and-after
      statements.

5. Topic trajectory: what topic did this conversation start on (one
   sentence, no quotes)? Did it ever turn to content about me as a
   person (my character / my problems / my situation)? If so, around
   which exchange did that turn happen?

Output only these five sections. Do not summarize "what this means."
Do not give me any advice.
```

## 各条目与编码本的对应（研究者用，不给参与者）

| Prompt 条目 | 对应码 | 校准优先级 |
|---|---|---|
| 2a | A3 CS+ | 高（表层形式码，AI 自报告最可能可靠） |
| 2b | A3 IS | 高 |
| 3a | B1 FA+ | 中（功能码，可能失真——校准重点） |
| 3b | B1 FA− | 中（⚠ 无法区分真FA−/定向FA−——已知限制，此档只报形式FA−） |
| 3c | B3 PERF / 机制4 表层信号 | 低（自指问题最重的条目，校准大概率不过，预备删除） |
| 4a | A2 CT | 高 |
| 4b | A2 ST | 高 |
| 4c | B2 ToF | 中 |
| 5 | A1 入口姿态 + task-to-self drift 轮号 | 高 |

**预期（校准前的假设，待 3.14 验证）**：表层形式码（2a/2b/4a/4b/5）
一致率可用；功能码（3a/3b）部分失真；自指条目（3c）大概率不可用。
校准结果出来后：不可用条目从 prompt 删除，可用条目保留并在 methods
里报告此档的 per-code 一致率。
