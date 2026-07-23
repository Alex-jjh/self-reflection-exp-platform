# 筛选问卷（v1 草案）— Qualtrics 双语搭建规格

> 用途：session 前数天发放。筛资格 + 个体差异变量。约 10–12 分钟。
> 平台：**Qualtrics 单份问卷，内置 zh/en 语言切换**（Survey Options →
> Translations；被试自选语言，`Q_Language` 字段自动记录，作为 session
> 语言分配的参考——见 SESSION_PROTOCOL 阶段 0）。
> 数据管理：平台只存量表分与联系方式（低敏），与对话转录（高敏）分离，
> 用参与者编号关联。
>
> **量表包（2026-07-23 裁决，P27 后替换 NCS-18 方案）：**
> GIH-6 + Dweck-3 + NFCS-15 + CIUSC-12 + RRS-brooding-5 + CSW-academic-5。
> 全部量表同时存在中英文验证版/原版——EN 轨道零额外翻译负担。
>
> 条目来源状态（2026-07-23 文献核实后更新）：
> - **闭合需求 15 项**：EN 用 Roets & Van Hiel 2011 原版条目（下列，发布前核对）。
>   ⚠ P27 声称的"NFCS-15 zh 2024 验证"经核实为错引（详见 ITEM_RETRIEVAL_GUIDE ①）；
>   zh 改用**刘雪峰、梁钧平 2007 修订版（42 项）中对应 R&VH 15 项的条目**——
>   取得 42 条全文后由 AI 对号替换下方翻译初稿
> - **IUS-12**：zh 验证已确认——**张亚娟等 2017，N=1,018 大学生，α=.878**
>   （papers/scales/zhang2017-IUS12-zh-college.pdf）；两因子=预期性焦虑
>   （1,2,3,4,5,8,10）/抑制性焦虑（6,7,9,11,12）；**Likert 5 点**（该节计分
>   从 7 点改 5 点）。12 条全文待从引用该文的学位论文附录补齐；
>   EN 用 Carleton et al. 2007 原版（同为 5 点）
> - **RRS-brooding**（Treynor et al. 2003）：EN 原版下列；zh 版确认为
>   **韩秀、杨宏飞 2009**（中国临床心理学杂志 17(5):550-551，22 条，
>   "强迫思考"维度=brooding），取得 22 条全文后挑 5 条替换初稿
> - GIH-6（Leary 2017）、Dweck-3：无 zh 验证版，翻译初稿待回译核对（不变）
> - CSW-academic（Crocker 2003）：待比对王磊/郑雪 2006；暂用翻译初稿
> - ⚠ 中庸作答提醒（P21 陷阱3）：pilot 规模下量表只做定性对照
> - ⚠ zh 翻译初稿仅为占位：凡存在验证中文版的量表，**上线前必须换成验证条目**

---

## Qualtrics 搭建清单（Block 结构）

| Block | 内容 | 逻辑 |
|---|---|---|
| B1 资格 | Q1–Q8 | Q4 <3个月 或 Q7=从来没有 → End of Survey（礼貌结束语，不进 B2） |
| B2 量表 | Q9–Q54（6 个量表，每量表一页） | 全部 7 点 Likert（RRS 为 4 点，见该节）；量表内条目随机化可开 |
| B3 基线 | Q55–Q57 | 无逻辑 |
| 收尾 | 联系方式确认 + 感谢 | Embedded data: `Q_Language`, 总分自动计算可后置 |

---

## 第一部分：基本信息与资格（B1）

1. 你的年龄 / Your age: ____
2. 性别 / Gender: 男 Male / 女 Female / 其他 Other / 不愿透露 Prefer not to say
3. 你目前的身份 / Current status: 本科生 Undergraduate / 硕士生 Master's / 博士生 PhD / 已工作 Working / 其他 Other ____
4. 你使用 AI 聊天工具多久了？ / How long have you been using AI chat tools?
   （zh 例：ChatGPT、Claude、豆包、Kimi、DeepSeek；en 例：ChatGPT, Claude, Gemini, Copilot）
   - 不到1个月 <1 month / 1–3个月 1–3 months / **3个月–1年 3 months–1 year / 1年以上 >1 year**（加粗=合格）
5. 你多久使用一次？ / How often do you use them?
   - 几乎每天 Almost daily / 每周几次 Several times a week / 每周一次左右 About weekly / 更少 Less often
6. 你最常用的 AI 聊天工具（可多选） / Which do you use most? (multi-select):
   ChatGPT / Claude / Gemini / 豆包 / Kimi / DeepSeek / 文心一言 / 通义千问 / Copilot / 其他 Other ____
7. 你有没有跟 AI 聊过工作/学习决定、人际关系、情绪或其他个人话题？ /
   Have you talked with an AI about work/study decisions, relationships, emotions, or other personal topics?
   - 经常 Often / 偶尔 Sometimes / 很少 Rarely / 从来没有 Never
   （"从来没有 Never"不合格；此题同时为 RQ1 提供基线）
8. 联系方式（微信/手机/邮箱，仅用于约时间） / Contact (WeChat/phone/email, scheduling only): ____

## 第二部分：想法与态度（B2，1=完全不同意 … 7=完全同意 / 1=strongly disagree … 7=strongly agree）

### 智识谦逊 GIH-6（zh 翻译初稿待回译核对；en 用 Leary et al. 2017 原版）

9. 我承认我的想法和态度可能是错的。/ I question my own opinions, positions, and viewpoints because they could be wrong.
10. 我会根据新证据重新考虑自己的观点。/ I reconsider my opinions when presented with new evidence.
11. 我尊重跟我看法不同的人的观点。/ I recognize the value in opinions that are different from my own.
12. 我接受我的信念和态度可能有错。/ I accept that my beliefs and attitudes may be wrong.
13. 面对相反的证据，我愿意改变自己的看法。/ In the face of conflicting evidence, I am open to changing my opinions.
14. 我喜欢了解与我已有认知不同的新信息。/ I like finding out new information that differs from what I already think is true.

### 成长型思维 Dweck-3（反向计分；zh 初稿待回译核对）

15. 一个人的聪明程度是天生固定的，无法真正改变。（R）/ You have a certain amount of intelligence, and you can't really do much to change it. (R)
16. 人可以学习新东西，但改变不了自己的基本智力水平。（R）/ You can learn new things, but you can't really change your basic intelligence. (R)
17. 不管是谁，都无法显著改变自己的能力水平。（R）/ No matter who you are, you can't significantly change your ability level. (R)

### 认知闭合需求 NFCS-15（Roets & Van Hiel 2011；en 原版条目，发布前核对；zh 为翻译初稿，**取得 2024 验证版后整节替换**）

18. 我不喜欢不确定的情境。/ I don't like situations that are uncertain.
19. 我不喜欢那种可以有很多种回答的问题。/ I dislike questions which could be answered in many different ways.
20. 规律有序的生活很适合我的性格。/ I find that a well-ordered life with regular hours suits my temperament.
21. 如果不明白生活中某件事为什么发生，我会觉得不舒服。/ I feel uncomfortable when I don't understand the reason why an event occurred in my life.
22. 当一个人和群体里其他所有人意见都不一致时，我会觉得烦躁。/ I feel irritated when one person disagrees with what everyone else in a group believes.
23. 我不喜欢在不知道会发生什么的情况下进入一个情境。/ I don't like to go into a situation without knowing what I can expect from it.
24. 做出决定之后，我会感到如释重负。/ When I have made a decision, I feel relieved.
25. 面对一个问题时，我非常渴望尽快找到答案。/ When I am confronted with a problem, I'm dying to reach a solution very quickly.
26. 如果不能立刻找到解决办法，我会很快变得不耐烦和恼火。/ I would quickly become impatient and irritated if I would not find a solution to a problem immediately.
27. 我不喜欢和行事难以预料的人待在一起。/ I don't like to be with people who are capable of unexpected actions.
28. 我不喜欢一句话可以有很多种理解的情况。/ I dislike it when a person's statement could mean many different things.
29. 建立稳定的日常规律能让我更享受生活。/ I find that establishing a consistent routine enables me to enjoy life more.
30. 我喜欢清晰而有条理的生活方式。/ I enjoy having a clear and structured mode of life.
31. 在形成自己的观点之前，我通常不会去征询很多不同的意见。/ I do not usually consult many different opinions before forming my own view.
32. 我不喜欢不可预测的情境。/ I dislike unpredictable situations.

### 未决不耐受 IUS-12（**本节 Likert 5 点**：1=完全不符合 … 5=完全符合 / 1=not at all characteristic of me … 5=entirely characteristic of me。en 用 Carleton 2007 原版，发布前核对；zh 为翻译初稿，**取得张亚娟 2017 验证条目后整节替换**）

33. 预料之外的事会让我非常心烦。/ Unforeseen events upset me greatly.
34. 缺少我需要的信息会让我很受挫。/ It frustrates me not having all the information I need.
35. 不确定感让我无法充分地生活。/ Uncertainty keeps me from living a full life.
36. 人应该凡事往前看，避免意外发生。/ One should always look ahead so as to avoid surprises.
37. 即使计划做得再好，一件小小的意外也可能毁掉一切。/ A small unforeseen event can spoil everything, even with the best of planning.
38. 到了该行动的时候，不确定感会让我动弹不得。/ When it's time to act, uncertainty paralyses me.
39. 不确定的时候，我没办法好好做事。/ When I am uncertain I can't function very well.
40. 我总是想知道未来会发生什么。/ I always want to know what the future has in store for me.
41. 我受不了被事情打个措手不及。/ I can't stand being taken by surprise.
42. 一点点疑虑就能让我停下行动。/ The smallest doubt can stop me from acting.
43. 我应该能把一切都提前安排好。/ I should be able to organize everything in advance.
44. 我必须远离所有不确定的情境。/ I must get away from all uncertain situations.

### 反刍-brooding RRS 5 项（Treynor et al. 2003；**4 点频率量表**：1=几乎从不 … 4=几乎总是 / 1=almost never … 4=almost always；引导语："当你感到低落、难过或沮丧时，你多常……" / "When you feel down, sad, or depressed, how often do you..."）

45. 想"我做了什么，要承受这些？" / Think "What am I doing to deserve this?"
46. 想"我为什么总是这样反应？" / Think "Why do I always react this way?"
47. 回想最近的某个情境，希望它当时能更好。/ Think about a recent situation, wishing it had gone better.
48. 想"为什么别人没有的问题，我有？" / Think "Why do I have problems other people don't have?"
49. 想"为什么我就不能把事情处理得更好？" / Think "Why can't I handle things better?"

### 学业权变自我价值 CSW-academic（5 项，zh 初稿待与王磊/郑雪 2006 比对；回到 7 点同意度）

50. 学习/工作上表现好的时候，我感觉自己更有价值。/ I feel better about myself when I do well academically/professionally.
51. 每当考试或考核表现差，我的自尊心就受打击。/ My self-esteem suffers whenever I do poorly on an exam or evaluation.
52. 我对自己的评价，很大程度上取决于我在学业/工作上的表现。/ How I feel about myself depends largely on my academic/work performance.
53. 知道自己在学业/工作上比别人强，会让我自我感觉良好。/ Knowing I do better than others academically/professionally makes me feel good about myself.
54. 学业/工作上的挫折会让我怀疑自己的价值。/ Academic/professional setbacks make me doubt my worth.

## 第三部分：RQ1 基线（B3，非筛选项）

55. 遇到烦心事时，你更可能先跟谁说？ / When something is bothering you, who are you most likely to talk to first?
    - 家人或朋友 Family or friends / AI 聊天工具 An AI chat tool / 都会，看情况 Either, depends / 都不说，自己消化 Neither, I keep it to myself
56. （若上题含 AI / if AI included）有一件事你只跟 AI 说过、没跟任何人说过吗？ / Is there something you've told only an AI and no person?
    - 有 Yes / 没有 No / 不确定 Not sure
57. 用一两句话说说：你一般在什么情况下会想跟 AI 聊个人话题？ / In a sentence or two: when do you tend to bring personal topics to an AI? ____

---

## 计分与使用备注（研究者用，不进问卷）
- GIH-6：均分，高=更谦逊。Dweck-3：反向计分后均分，高=成长型。
- **闭合需求 15 项**：均分，高=闭合需求强（seizing/freezing 倾向）。
- **IUS-12**：**5 点计分**，总分 12–60；两因子按张亚娟 2017——预期性焦虑
  （条目 1,2,3,4,5,8,10）/抑制性焦虑（条目 6,7,9,11,12）。**与访谈 Q11 追问
  （表述萎缩自我报告）交叉验证**——P27 signature 3。
- **RRS-brooding**：总分（5–20），高=brooding 强。**Moderator 用途**（P27）：
  高 brooding 者截断孵化可能是治疗性的，低 brooding 者才是 foreclosure 风险
  人群——pilot 只做定性分组参考，不检验。
- CSW-academic：均分，高=学业权变性强（优绩主义倾向 proxy）。
- 合格线：Q4 ≥ 3个月 且 Q7 ≠ 从来没有（Qualtrics B1 逻辑自动执行）。
- 第55题=「默认求助路径」访谈探针的问卷版；session 访谈里还会追问。
- `Q_Language` 字段 → session 语言分配参考（最终以"平时和 AI 聊个人话题
  用什么语言"访谈确认为准，SESSION_PROTOCOL 阶段 0）。
