# 筛选问卷（v1 草案）— Qualtrics 双语搭建规格

> 用途：session 前数天发放。筛资格 + 个体差异变量。约 12–14 分钟。
> 平台：**Qualtrics 单份问卷，内置 zh/en 语言切换**（Survey Options →
> Translations；被试自选语言，`Q_Language` 字段自动记录，作为 session
> 语言分配的参考——见 SESSION_PROTOCOL 阶段 0）。
> 数据管理：平台只存量表分与联系方式（低敏），与对话转录（高敏）分离，
> 用参与者编号关联。
>
> **量表包（2026-07-23 裁决 + 2026-07-25 增补 ECR-RS）：**
> GIH-6 + Dweck-3 + NFCS-15 + CIUSC-12 + RRS-brooding-5 + ECR-RS-9 +
> CSW-academic-5。全部量表同时存在中英文验证版/原版——EN 轨道零额外
> 翻译负担。
>
> 条目来源状态（2026-07-23 文献核实后更新）：
> - **闭合需求 15 项**：EN 用 Roets & Van Hiel 2011 原版条目（下列，发布前核对）。
>   **刘 2007 已取件（07-27）但只印验证保留的 21 条**（42 条 EFA 删减后，
>   未印全文）→ zh 为混合来源：6 条刘版验证措辞已替换（✅ 标注），9 条
>   保留翻译初稿走回译（⚠ 标注）；该节 **6 点计分**。岔路 A/B 待裁决
>   （详见 ITEM_RETRIEVAL_GUIDE ①）
> - **IUS-12**：✅ **条目已到位（2026-07-27）**——zh 用**吴莉娟等 2016**
>   附录全文 12 条（与 Carleton 原版同序；papers/scales/
>   wu-IUS12-zh-middleschool.pdf），大学生适用性锚定**张亚娟等 2017**
>   （N=1,018，α=.878）；**Likert 5 点**；两因子按 Carleton 原版编号
>   （见计分备注）。EN 用 Carleton et al. 2007 原版（同为 5 点）
> - **RRS-brooding**：✅ **条目已到位（2026-07-27，网络转载+库内 PDF
>   交叉核验）**——韩秀/杨宏飞 2009 版 brooding 5 条（原量表 5,10,13,15,16）
>   已替换 Q45–49（存证 items/rrs22-zh.md）；CNKI 学位论文附录逐字核对
>   降级为核对项。EN 用 Treynor et al. 2003 原版
> - GIH-6（Leary 2017）、Dweck-3：无 zh 验证版，翻译初稿待回译核对（不变）
> - CSW-academic（Crocker 2003）：待比对王磊/郑雪 2006；暂用翻译初稿
> - ⚠ 中庸作答提醒（P21 陷阱3）：pilot 规模下量表只做定性对照
> - ⚠ zh 翻译初稿仅为占位：凡存在验证中文版的量表，**上线前必须换成验证条目**

---

## Qualtrics 搭建清单（Block 结构）

| Block | 内容 | 逻辑 |
|---|---|---|
| B1 资格 | Q1–Q8 | Q4 <3个月 或 Q7=从来没有 → End of Survey（礼貌结束语，不进 B2） |
| B2 量表 | Q9–Q54 + 44a–i（7 个量表，每量表一页） | 7 点 Likert 为主（IUS 5 点、RRS 4 点，见各节）；量表内条目随机化可开 |
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

### 认知闭合需求 NFCS-15（Roets & Van Hiel 2011；en 原版条目，发布前核对；**6 点计分**：1=强烈不同意 … 6=强烈同意——刘 2007 与 W&K 原版均为 6 点，与本问卷默认 7 点不同，Qualtrics 搭建时该节单独设置）

> 【zh 条目状态（2026-07-27 取件后更新）：刘雪峰/梁钧平 2007 原文到手
> （`papers/scales/liu2007-NFCC-zh.pdf`），但**其表 1 只印验证后保留的
> 21 条**（42 条经 EFA 两轮删除，未印全文）——原"42 选 15"方案不可行。
> 逐条比对结果（存证 `items/nfcc21-liu2007-zh.md`）：R&VH-15 中 **6 条
> 有刘版验证措辞（已替换：Q18,19,20,27,29,30，下标 ✅）**；其余 9 条的
> 原条目被刘的 EFA 删除、无验证中文措辞（保留翻译初稿，走回译流程，
> 下标 ⚠）。Q28 与刘版 #36 语义相近但非同一原条目，保守处理为 ⚠。
> **方法学岔路待裁决（ITEM_RETRIEVAL_GUIDE ①）**：A=现状（混合来源，
> zh/en 结构镜像保持）；B=zh 整节改用刘版 21 条（全验证但 zh/en 结构
> 分叉 + 加长）。方法节如实写："zh 条目 6/15 采用刘雪峰梁钧平(2007)
> 验证措辞，其余 9 条为回译核对的研究者翻译（对应原条目在该中文验证
> 中未保留）"。】

18. 我不喜欢不确定的情境。✅刘#3 / I don't like situations that are uncertain.
19. 我不喜欢那些可以有许多不同答案的问题。✅刘#4 / I dislike questions which could be answered in many different ways.
20. 我发现我的性格适合井井有条、循规蹈矩的生活方式。✅刘#6 / I find that a well-ordered life with regular hours suits my temperament.
21. 如果不明白生活中某件事为什么发生，我会觉得不舒服。⚠ / I feel uncomfortable when I don't understand the reason why an event occurred in my life.
22. 当一个人和群体里其他所有人意见都不一致时，我会觉得烦躁。⚠ / I feel irritated when one person disagrees with what everyone else in a group believes.
23. 我不喜欢在不知道会发生什么的情况下进入一个情境。⚠ / I don't like to go into a situation without knowing what I can expect from it.
24. 做出决定之后，我会感到如释重负。⚠ / When I have made a decision, I feel relieved.
25. 面对一个问题时，我非常渴望尽快找到答案。⚠ / When I am confronted with a problem, I'm dying to reach a solution very quickly.
26. 如果不能立刻找到解决办法，我会很快变得不耐烦和恼火。⚠ / I would quickly become impatient and irritated if I would not find a solution to a problem immediately.
27. 我不愿意与可能作出意想不到的行为的人在一起。✅刘#25 / I don't like to be with people who are capable of unexpected actions.
28. 我不喜欢一句话可以有很多种理解的情况。⚠（近邻：刘#36"当我不清楚某人的意思和意图时，会感到不舒服"，非同一原条目，未采用）/ I dislike it when a person's statement could mean many different things.
29. 我发现建立始终如一的规律能使我更好地享受生活。✅刘#32 / I find that establishing a consistent routine enables me to enjoy life more.
30. 我喜欢有条不紊的生活方式。✅刘#33 / I enjoy having a clear and structured mode of life.
31. 在形成自己的观点之前，我通常不会去征询很多不同的意见。⚠ / I do not usually consult many different opinions before forming my own view.
32. 我不喜欢不可预测的情境。⚠ / I dislike unpredictable situations.

### 未决不耐受 IUS-12（**本节 Likert 5 点**：1=完全不符合 2=有点符合 3=基本符合 4=非常符合 5=完全符合 / 1=not at all characteristic of me … 5=entirely characteristic of me。en 用 Carleton 2007 原版，发布前核对）

> 【zh 条目来源（2026-07-27 替换完成，✅ 不再阻塞）：**吴莉娟、王佳宁、齐晓栋
> 2016**《简版无法忍受不确定性量表在中学生中应用的效度和信度》，中国心理
> 卫生杂志 30(9)，**文末附录印有全部 12 条**（`papers/scales/
> wu-IUS12-zh-middleschool.pdf`），条目顺序=Carleton 2007 原版顺序，逐条
> 照录。**大学生适用性锚定张亚娟等 2017**（N=1,018，α=.878，
> `papers/scales/zhang2017-IUS12-zh-college.pdf`）——注意张版为独立翻译、
> 条目顺序与 Carleton 不同（其正文透露的"第8条"实为 Carleton 第3条内容），
> 故**不与吴版拼接措辞、不用张版因子编号**；方法节表述："zh 条目采用
> 吴莉娟等(2016)公开发表的 IUS-12 中文版，该量表在大学生群体的适用性
> 见张亚娟等(2017)"。可选升级：取得张版 12 条全文后（取件指南②b）
> 整节换为大学生样本验证条目。】

33. 无法预料的事情会让我心烦意乱。/ Unforeseen events upset me greatly.
34. 如果不能拥有我所需要的全部信息，我会很沮丧。/ It frustrates me not having all the information I need.
35. 不确定性使我很难拥有一个完美的生活。/ Uncertainty keeps me from living a full life.
36. 我做事总会未雨绸缪，以避免措手不及。/ One should always look ahead so as to avoid surprises.
37. 即使有最好的计划，一个小意外也能搞砸我的全盘计划。/ A small unforeseen event can spoil everything, even with the best of planning.
38. 当到了采取行动的时候，不确定性会让我停滞不前。/ When it's time to act, uncertainty paralyses me.
39. 当我感到不确定时，我就不能很好的表现自己。/ When I am uncertain I can't function very well.
40. 我总是想知道我的未来是什么样子的。/ I always want to know what the future has in store for me.
41. 我无法忍受突发状况。/ I can't stand being taken by surprise.
42. 一点点的疑虑都会阻止我行动。/ The smallest doubt can stop me from acting.
43. 在做事之前，我应该能够规划好一切。/ I should be able to organize everything in advance.
44. 我必须摆脱所有不确定的情形。/ I must get away from all uncertain situations.

### 反刍-brooding RRS 5 项（Treynor et al. 2003 brooding 因子；**4 点频率量表**：1=从不 2=有时 3=经常 4=总是 / 1=almost never … 4=almost always）

> 【zh 条目来源（2026-07-27 替换）：**韩秀、杨宏飞 2009** RRS 中文版
> （中国临床心理学杂志 17(5)，α=.90，`papers/scales/han2009-RRS-zh.pdf`）
> 强迫思考（brooding）因子 = 原量表条目 5,10,13,15,16，与 Treynor 编号
> 一致。条目文本取自网络转载（xinlixue.cn），已用韩 2009 原文的样本
> 细节+因子表+计分交叉核验（存证 `screening/items/rrs22-zh.md`）；
> **CNKI 学位论文附录逐字核对仍要做（降级为核对项，非缺件）**。
> 措辞注意：韩版条目自带"我常常想"（频率内嵌），故 zh 引导语不再用
> "你多常……"句式，避免叠加；en 保留 Treynor 原版引导语
> "When you feel down, sad, or depressed, how often do you..."，
> en 条目不带 often（原版如此），zh/en 结构差异在方法节注明。
> zh 引导语："请回想你感到郁闷、情绪低落的时候，以下情况符合你的
> 程度："】

45. 我常常想我究竟做了什么会导致这样。/ Think "What am I doing to deserve this?"
46. 我常常想我为什么总是这样。/ Think "Why do I always react this way?"
47. 我常常思考现状，希望它有所好转。/ Think about a recent situation, wishing it had gone better.
48. 我常常想为什么我有这些问题，而别人却没有。/ Think "Why do I have problems other people don't have?"
49. 我常常想我为什么不能把事情处理得更好。/ Think "Why can't I handle things better?"

### 依恋 ECR-RS 9 项（Fraley et al. 2011，Relationship Structures 通用版；**7 点同意度**；引导语："以下句子描述人们在亲近关系中的感受。请针对你生活中普遍的亲近关系（如亲密朋友、家人）作答" / "The following concern how you feel in close relationships in general"）

> 【条目来源（2026-07-25 对号完成）：zh 条目取自**李同归、加藤和生 2006
> ECR 中文版**（心理学报 38(3):399-406，α=.82/.77，重测 .71/.72，
> `papers/scales/litonggui2006-ECR-zh.pdf`）中对应 ECR-RS 的条目，
> 指称从"恋人"改为"他们"（通用关系）——**此指称适配需在方法节注明**。
> 44g 无 ECR 原版对应条目（ECR-RS 该题源自 ECR-R），保留我们的翻译并标注。
> 若 CNKI 检得 ECR-RS 专门中文验证（取件指南③b），则整节替换为该版。】

44a. 我经常与他们讨论我所遇到的问题以及我关心的事情。（R，回避；ECR-27）/ I usually discuss my problems and concerns with them. (R)
44b. 我跟他们什么事情都讲。（R，回避；ECR-25）/ I talk things over with them. (R)
44c. 我觉得依赖他们是很自在的事情。（R，回避；ECR-29）/ I find it easy to depend on them. (R)
44d. 我觉得对他们开诚布公不是一件很舒服的事情。（回避；ECR-9）/ I don't feel comfortable opening up to them.
44e. 总的来说，我不喜欢让他们知道自己内心深处的感觉。（回避；ECR-1）/ I prefer not to show them how I feel deep down.
44f. 在需要的时候，我向他们求助是很有用的。（R，回避；ECR-33）/ It helps to turn to them in times of need. (R)
44g. 我常担心他们并不真正在乎我。（焦虑；⚠ 翻译稿，无 ECR 对应）/ I often worry that they don't really care for me.
44h. 我担心我会被抛弃。（焦虑；ECR-2）/ I'm afraid that they may abandon me.
44i. 我担心他们不会像我关心他们那样地关心我。（焦虑；ECR-6）/ I worry that they won't care about me as much as I care about them.

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
- **IUS-12**：**5 点计分**，总分 12–60；两因子按 **Carleton 2007 原版编号**
  （zh 条目=吴版，与原版同序）——Prospective Anxiety（条目 1,2,4,5,8,9,11
  = Q33,34,36,37,40,41,43）/ Inhibitory Anxiety（条目 3,6,7,10,12 =
  Q35,38,39,42,44）。⚠ 勿用张亚娟 2017 的因子编号（其条目为独立翻译、
  顺序与原版不同）；吴 2016 在中学生中报告三因子，pilot 规模下以总分+
  Carleton 两因子做定性参考即可。**与访谈 Q11 追问（表述萎缩自我报告）
  交叉验证**——P27 signature 3。
- **RRS-brooding**：总分（5–20），高=brooding 强。**Moderator 用途**（P27）：
  高 brooding 者截断孵化可能是治疗性的，低 brooding 者才是 foreclosure 风险
  人群——pilot 只做定性分组参考，不检验。
- CSW-academic：均分，高=学业权变性强（优绩主义倾向 proxy）。
- **ECR-RS**：回避分（6 题，R 题反向）+ 焦虑分（3 题）分开计。用途（P30/ch26）：
  焦虑高 = reassurance 回路高危（与访谈"AI 鼓励了我"听觉指引交叉）；
  回避高 = "仅向 AI 外化"预期人群（与 Q6 人际模板探针交叉；预期
  bypass——回避者照样向 AI 暴露）。pilot 规模只做定性分组。
- 合格线：Q4 ≥ 3个月 且 Q7 ≠ 从来没有（Qualtrics B1 逻辑自动执行）。
- 第55题=「默认求助路径」访谈探针的问卷版；session 访谈里还会追问。
- `Q_Language` 字段 → session 语言分配参考（最终以"平时和 AI 聊个人话题
  用什么语言"访谈确认为准，SESSION_PROTOCOL 阶段 0）。
