# Qualtrics 逐题录入稿 — 给 computer-use agent 的施工文档

> **唯一事实来源：`screening/QUESTIONNAIRE.md`（v1 定稿）。** 本稿是它的
> 无歧义施工版：题干已剥掉所有科研标注、逐题给出类型/刻度/双语文本/逻辑。
> 若本稿与 QUESTIONNAIRE.md 冲突，以 QUESTIONNAIRE.md 为准并回报。
> 生成日期 2026-07-30。共 **66 题**（B1 资格 8 + B2 量表 55 + B3 基线 3）。

---

## 0. 给 agent 的三条铁律（先读，违反=数据作废）

1. **每个量表的作答刻度不同，不要统一。** GIH/Dweck/ECR/CSW = 7 点；
   NFCS = **6 点**；IUS = **5 点**；RRS = **4 点频率**。每个量表单独一页、
   单独设刻度（见各 §）。
2. **绝不录入任何科研标注。** 源文件题干里出现的这些一律**删掉、不进问卷**：
   `✅刘#3` `⚠` `（R）` `（R，回避；ECR-27）` `（焦虑；…）` `（加粗=合格）`
   `（近邻：刘#36…未采用）` `（"从来没有 Never"不合格；…）` 等。本稿给出的
   题干**已经是干净版**——照本稿录，不要回源文件抄带标注的版本。
3. **题号 `44a–44i`(ECR) 是遗留 item-ID，不是位置。** 它们物理上排在
   RRS(Q45–49)**之后**、CSW(Q50–54)**之前**（见 §B2 顺序表）。**不要**把
   它们插到 Q44 和 Q45 中间。Qualtrics 内部命名建议直接用 `ECR_1…ECR_9`，
   忽略 44x 编号。

**不需要做的事（省力+防错）**：① 不在 Qualtrics 里建任何计分/总分逻辑
（源文件明确"总分自动计算可后置"，反向计分是分析阶段做的，agent 只录题）；
② 不建量表内 attention-check；③ 反向题(R)照常录成普通 Likert 题，R 只影响
后期计分，不影响录入。

---

## 1. 问卷级设置（Survey Options）

- **单份问卷，双语**：Survey Options → Languages/Translations 加 English 翻译层。
  每题的 zh 为主语言文本、en 为翻译层文本（本稿每题都给了两条）。
- 被试自选语言；记录 **Embedded Data 字段 `Q_Language`**（zh / en）。
- 进度条：开。允许返回上一页：开（筛选问卷，无计时）。
- 匿名链接；单次作答（防重复可选开 ballot-box stuffing 防护）。
- 量表内**条目随机化**：可开（源文件"可开"）。跨量表顺序**不随机**（按下表固定）。

---

## 2. Block 结构与跳转逻辑

| Block | 题 | 类型概览 | 逻辑 |
|---|---|---|---|
| **B1 资格** | Q1–Q8 | 混合 | Q4=`<1个月` 或 `1–3个月`  **或**  Q7=`从来没有` → **End of Survey**（礼貌结束语，不进 B2） |
| **B2 量表** | 7 个量表，每量表**一页**、各自刻度 | Matrix/Likert | 无跳转；量表内条目随机化可开 |
| **B3 基线** | Q55–Q57 | 混合 | Q56 仅当 Q55 选了含 AI 的项时显示（见 Q56 逻辑） |
| **收尾** | 联系确认 + 感谢 | — | Embedded `Q_Language` 收尾确认 |

**B2 内 7 个量表的固定显示顺序（照此顺序建页，注意 ECR 的位置）：**

| 顺序 | 量表 | 题号 | 题数 | 刻度 |
|---|---|---|---|---|
| 1 | 智识谦逊 GIH-6 | Q9–Q14 | 6 | 7 点同意 |
| 2 | 成长型思维 Dweck-3 | Q15–Q17 | 3 | 7 点同意（含反向题） |
| 3 | 认知闭合需求 NFCS-15 | Q18–Q32 | 15 | **6 点同意** |
| 4 | 未决不耐受 IUS-12 | Q33–Q44 | 12 | **5 点符合度** |
| 5 | 反刍-brooding RRS-5 | Q45–Q49 | 5 | **4 点频率** |
| 6 | 依恋 ECR-RS-9 | **ECR_1–ECR_9**（源文件旧标 44a–44i） | 9 | 7 点同意（含反向题） |
| 7 | 学业权变自我价值 CSW-5 | Q50–Q54 | 5 | 7 点同意 |

---

## 3. B1 资格（Q1–Q8）

**Q1** 文本输入
- zh：你的年龄
- en：Your age

**Q2** 单选
- zh：性别 — 男 / 女 / 其他 / 不愿透露
- en：Gender — Male / Female / Other / Prefer not to say

**Q3** 单选（"其他"带文本框）
- zh：你目前的身份 — 本科生 / 硕士生 / 博士生 / 已工作 / 其他____
- en：Current status — Undergraduate / Master's / PhD / Working / Other____

**Q4** 单选 —（**资格题**）
- zh：你使用 AI 聊天工具多久了？（例：ChatGPT、Claude、豆包、Kimi、DeepSeek）
- en：How long have you been using AI chat tools? (e.g., ChatGPT, Claude, Gemini, Copilot)
- 选项：`不到1个月 <1 month` / `1–3个月 1–3 months` / `3个月–1年 3 months–1 year` / `1年以上 >1 year`
- **合格 = 后两项**（`3个月–1年` 或 `1年以上`）。前两项触发淘汰逻辑。

**Q5** 单选
- zh：你多久使用一次？ — 几乎每天 / 每周几次 / 每周一次左右 / 更少
- en：How often do you use them? — Almost daily / Several times a week / About weekly / Less often

**Q6** **多选**
- zh：你最常用的 AI 聊天工具（可多选）
- en：Which do you use most? (multi-select)
- 选项：ChatGPT / Claude / Gemini / 豆包 / Kimi / DeepSeek / 文心一言 / 通义千问 / Copilot / 其他 Other____

**Q7** 单选 —（**资格题 + RQ1 基线**）
- zh：你有没有跟 AI 聊过工作/学习决定、人际关系、情绪或其他个人话题？
- en：Have you talked with an AI about work/study decisions, relationships, emotions, or other personal topics?
- 选项：`经常 Often` / `偶尔 Sometimes` / `很少 Rarely` / `从来没有 Never`
- **`从来没有 Never` = 淘汰。**

**Q8** 文本输入
- zh：联系方式（微信/手机/邮箱，仅用于约时间）
- en：Contact (WeChat/phone/email, scheduling only)

**B1 淘汰逻辑（Survey Flow 或 Q7 后加 Branch / End-of-Survey）**：
`IF Q4 == (不到1个月|1–3个月) OR Q7 == 从来没有 → End of Survey`，
显示礼貌结束语（zh：感谢参与，你暂不符合本次研究的招募条件 / en：Thank you,
you don't meet this study's criteria this time）。合格者继续 B2。

---

## 4. B2 量表（干净题干，照录）

> 每个量表 = 一个 Matrix Table（行=条目，列=刻度点）最省事、且天然强制"整个
> 量表共用一个刻度"。以下每条给 zh / en 两版；R 标记仅供你识别，不进问卷。

### 量表 1 — 智识谦逊 GIH-6（7 点同意）
刻度：`1 完全不同意 … 7 完全同意` / `1 strongly disagree … 7 strongly agree`

| # | zh | en |
|---|---|---|
| Q9 | 我承认我的想法和态度可能是错的。 | I question my own opinions, positions, and viewpoints because they could be wrong. |
| Q10 | 我会根据新证据重新考虑自己的观点。 | I reconsider my opinions when presented with new evidence. |
| Q11 | 我尊重跟我看法不同的人的观点。 | I recognize the value in opinions that are different from my own. |
| Q12 | 我接受我的信念和态度可能有错。 | I accept that my beliefs and attitudes may be wrong. |
| Q13 | 面对相反的证据，我愿意改变自己的看法。 | In the face of conflicting evidence, I am open to changing my opinions. |
| Q14 | 我喜欢了解与我已有认知不同的新信息。 | I like finding out new information that differs from what I already think is true. |

### 量表 2 — 成长型思维 Dweck-3（7 点同意；全部反向题，R 不显示）
刻度同 7 点同意。

| # | zh | en |
|---|---|---|
| Q15 | 一个人的聪明程度是天生固定的，无法真正改变。 | You have a certain amount of intelligence, and you can't really do much to change it. |
| Q16 | 人可以学习新东西，但改变不了自己的基本智力水平。 | You can learn new things, but you can't really change your basic intelligence. |
| Q17 | 不管是谁，都无法显著改变自己的能力水平。 | No matter who you are, you can't significantly change your ability level. |

### 量表 3 — 认知闭合需求 NFCS-15（**6 点同意**，单独设刻度！）
刻度：`1 强烈不同意 … 6 强烈同意` / `1 strongly disagree … 6 strongly agree`
（**注意：6 点，不是 7 点；zh 用"强烈"非"完全"**）

| # | zh | en |
|---|---|---|
| Q18 | 我不喜欢不确定的情境。 | I don't like situations that are uncertain. |
| Q19 | 我不喜欢那些可以有许多不同答案的问题。 | I dislike questions which could be answered in many different ways. |
| Q20 | 我发现我的性格适合井井有条、循规蹈矩的生活方式。 | I find that a well-ordered life with regular hours suits my temperament. |
| Q21 | 如果不明白生活中某件事为什么发生，我会觉得不舒服。 | I feel uncomfortable when I don't understand the reason why an event occurred in my life. |
| Q22 | 当一个人和群体里其他所有人意见都不一致时，我会觉得烦躁。 | I feel irritated when one person disagrees with what everyone else in a group believes. |
| Q23 | 我不喜欢在不知道会发生什么的情况下进入一个情境。 | I don't like to go into a situation without knowing what I can expect from it. |
| Q24 | 做出决定之后，我会感到如释重负。 | When I have made a decision, I feel relieved. |
| Q25 | 面对一个问题时，我非常渴望尽快找到答案。 | When I am confronted with a problem, I'm dying to reach a solution very quickly. |
| Q26 | 如果不能立刻找到解决办法，我会很快变得不耐烦和恼火。 | I would quickly become impatient and irritated if I would not find a solution to a problem immediately. |
| Q27 | 我不愿意与可能作出意想不到的行为的人在一起。 | I don't like to be with people who are capable of unexpected actions. |
| Q28 | 我不喜欢一句话可以有很多种理解的情况。 | I dislike it when a person's statement could mean many different things. |
| Q29 | 我发现建立始终如一的规律能使我更好地享受生活。 | I find that establishing a consistent routine enables me to enjoy life more. |
| Q30 | 我喜欢有条不紊的生活方式。 | I enjoy having a clear and structured mode of life. |
| Q31 | 在形成自己的观点之前，我通常不会去征询很多不同的意见。 | I do not usually consult many different opinions before forming my own view. |
| Q32 | 我不喜欢不可预测的情境。 | I dislike unpredictable situations. |

### 量表 4 — 未决不耐受 IUS-12（**5 点符合度**，单独设刻度！）
刻度：`1 完全不符合 / 2 有点符合 / 3 基本符合 / 4 非常符合 / 5 完全符合`
/ `1 not at all characteristic of me … 5 entirely characteristic of me`
（en 原版只标两端，中间点不加标签，照 Carleton 原版）

| # | zh | en |
|---|---|---|
| Q33 | 无法预料的事情会让我心烦意乱。 | Unforeseen events upset me greatly. |
| Q34 | 如果不能拥有我所需要的全部信息，我会很沮丧。 | It frustrates me not having all the information I need. |
| Q35 | 不确定性使我很难拥有一个完美的生活。 | Uncertainty keeps me from living a full life. |
| Q36 | 我做事总会未雨绸缪，以避免措手不及。 | One should always look ahead so as to avoid surprises. |
| Q37 | 即使有最好的计划，一个小意外也能搞砸我的全盘计划。 | A small unforeseen event can spoil everything, even with the best of planning. |
| Q38 | 当到了采取行动的时候，不确定性会让我停滞不前。 | When it's time to act, uncertainty paralyses me. |
| Q39 | 当我感到不确定时，我就不能很好的表现自己。 | When I am uncertain I can't function very well. |
| Q40 | 我总是想知道我的未来是什么样子的。 | I always want to know what the future has in store for me. |
| Q41 | 我无法忍受突发状况。 | I can't stand being taken by surprise. |
| Q42 | 一点点的疑虑都会阻止我行动。 | The smallest doubt can stop me from acting. |
| Q43 | 在做事之前，我应该能够规划好一切。 | I should be able to organize everything in advance. |
| Q44 | 我必须摆脱所有不确定的情形。 | I must get away from all uncertain situations. |

### 量表 5 — 反刍-brooding RRS-5（**4 点频率**，单独设刻度！）
刻度：`1 从不 / 2 有时 / 3 经常 / 4 总是` / `1 almost never … 4 almost always`
**引导语（重要，zh/en 结构不同，照录）**：
- zh 引导语：请回想你感到郁闷、情绪低落的时候，以下情况符合你的程度：
- en 引导语：When you feel down, sad, or depressed, how often do you...

| # | zh（注意自带"我常常"） | en（原版不带 often） |
|---|---|---|
| Q45 | 我常常想我究竟做了什么会导致这样。 | Think "What am I doing to deserve this?" |
| Q46 | 我常常想我为什么总是这样。 | Think "Why do I always react this way?" |
| Q47 | 我常常思考现状，希望它有所好转。 | Think about a recent situation, wishing it had gone better. |
| Q48 | 我常常想为什么我有这些问题，而别人却没有。 | Think "Why do I have problems other people don't have?" |
| Q49 | 我常常想我为什么不能把事情处理得更好。 | Think "Why can't I handle things better?" |

### 量表 6 — 依恋 ECR-RS-9（7 点同意）— **内部命名 ECR_1…ECR_9，排在 RRS 之后 / CSW 之前**
刻度同 7 点同意。
**引导语（照录）**：
- zh：以下句子描述人们在亲近关系中的感受。请针对你生活中普遍的亲近关系（如亲密朋友、家人）作答。
- en：The following concern how you feel in close relationships in general.

| 内部名（旧标） | zh | en |
|---|---|---|
| ECR_1 (44a) | 我经常与他们讨论我所遇到的问题以及我关心的事情。 | I usually discuss my problems and concerns with them. |
| ECR_2 (44b) | 我跟他们什么事情都讲。 | I talk things over with them. |
| ECR_3 (44c) | 我觉得依赖他们是很自在的事情。 | I find it easy to depend on them. |
| ECR_4 (44d) | 我觉得对他们开诚布公不是一件很舒服的事情。 | I don't feel comfortable opening up to them. |
| ECR_5 (44e) | 总的来说，我不喜欢让他们知道自己内心深处的感觉。 | I prefer not to show them how I feel deep down. |
| ECR_6 (44f) | 在需要的时候，我向他们求助是很有用的。 | It helps to turn to them in times of need. |
| ECR_7 (44g) | 我常担心他们并不真正在乎我。 | I often worry that they don't really care for me. |
| ECR_8 (44h) | 我担心我会被抛弃。 | I'm afraid that they may abandon me. |
| ECR_9 (44i) | 我担心他们不会像我关心他们那样地关心我。 | I worry that they won't care about me as much as I care about them. |

### 量表 7 — 学业权变自我价值 CSW-5（7 点同意）
刻度同 7 点同意。

| # | zh | en |
|---|---|---|
| Q50 | 学习/工作上表现好的时候，我感觉自己更有价值。 | I feel better about myself when I do well academically/professionally. |
| Q51 | 每当考试或考核表现差，我的自尊心就受打击。 | My self-esteem suffers whenever I do poorly on an exam or evaluation. |
| Q52 | 我对自己的评价，很大程度上取决于我在学业/工作上的表现。 | How I feel about myself depends largely on my academic/work performance. |
| Q53 | 知道自己在学业/工作上比别人强，会让我自我感觉良好。 | Knowing I do better than others academically/professionally makes me feel good about myself. |
| Q54 | 学业/工作上的挫折会让我怀疑自己的价值。 | Academic/professional setbacks make me doubt my worth. |

---

## 5. B3 基线（Q55–Q57）

**Q55** 单选
- zh：遇到烦心事时，你更可能先跟谁说？
- en：When something is bothering you, who are you most likely to talk to first?
- 选项：`家人或朋友 Family or friends` / `AI 聊天工具 An AI chat tool` /
  `都会，看情况 Either, depends` / `都不说，自己消化 Neither, I keep it to myself`

**Q56** 单选 —（**显示逻辑**）
- **仅当 Q55 选了 `AI 聊天工具` 或 `都会，看情况` 时显示**（含 AI 的两项）。
- zh：有一件事你只跟 AI 说过、没跟任何人说过吗？
- en：Is there something you've told only an AI and no person?
- 选项：有 Yes / 没有 No / 不确定 Not sure

**Q57** 文本输入（长文本框）
- zh：用一两句话说说：你一般在什么情况下会想跟 AI 聊个人话题？
- en：In a sentence or two: when do you tend to bring personal topics to an AI?

---

## 6. 附录（agent 不录入，仅供 Alex 事后核对 / 分析）

- **不在 Qualtrics 建计分**。反向计分 + 各量表算分是分析阶段做：
  Dweck Q15–17(R)；ECR 回避子量表 ECR_1/2/3/6 为 R。
- IUS 因子（分析用，非录入）：Prospective = Q33,34,36,37,40,41,43；
  Inhibitory = Q35,38,39,42,44（按 Carleton 2007 原版编号；勿用张亚娟 2017 编号）。
- **上线前逐字核对项（源文件列的低优先、不阻塞上线，但录入时顺手比一眼）**：
  RRS 5 条对 CNKI 韩秀/杨宏飞 2009 学位论文附录；CSW 5 条对王磊/郑雪 2006；
  NFCS 9 条 ⚠(Q21–26,28,31,32) 与 IUS/GIH/Dweck 的 en 原版逐字。
- GIH-6 只做**一次性 pre-study 筛选**，不做 session 前后测（见 QUESTIONNAIRE.md
  计分备注的测量时机护栏）。
