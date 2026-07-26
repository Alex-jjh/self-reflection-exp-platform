# 1.1 通读伴随表（2026-07-25，advisor memo B4/A3/B3）

> 用途：任务 1.1（通读 zh 11 + en 9 份 frozen-pilot 转录 → v1-freeze）
> 反正要逐份读，顺手带三张便宜的表。**B4 是 freeze 前最后一个可能
> 触发改 prompt 的检查**——先做它。

## 表 1（B4）：AI 提问的认识论姿态比例 —— manipulation check 盲区

> 依据：Koshik RPQs + Heritage epistemic gradient。决定叙事走向的
> 不是语气，是 AI 的提问姿态。若三条件姿态比例无差 → 操纵只动了
> 语气没动认识论，**freeze 前要改 prompt**。

每份转录数 AI 的提问（append 到下表）：
- **INFO**：真信息寻求（"当时具体发生了什么？"——答案未知）
- **CONF**：确认寻求/评价性（"这对你很重要，对吧？"——答案已含）
- **CHAL**：挑战性开放（"有没有另一种解释？"——邀请反例）

| 转录 | 条件 | INFO | CONF | CHAL | 备注 |
|---|---|---|---|---|---|
| S1×supportive (zh) | A | | | | |
| S1×challenging (zh) | B | | | | |
| S1×neutral (zh) | C | | | | |
| …（全 20 份） | | | | | |

**判读**：预期 challenging 的 CHAL 占比 ≫ supportive；supportive 的
CONF 占比最高；neutral 以 INFO 为主。若 supportive 与 neutral 的
分布无法区分，或 challenging 的 CHAL 不足半数——改 prompt 再 freeze。

## 表 2（A3）：AI 支持的 person-centeredness 等级 —— Burleson 预测

> 依据：Burleson comforting 层级。报告预测：LLM 默认落在**中 PC**、
> 很少高 PC。编码本 B1 只测框架接受，AI 侧"支持的质量维度"是空的。

对 supportive 条件的每个 AI turn 标一级：
- **LPC** 低：否认/最小化感受（"别想太多""这没什么"）
- **MPC** 中：转移注意/给建议/安慰但不展开感受（"可以试试X"）
- **HPC** 高：帮助表述和探索感受本身（"听起来那种失落里还有点
  不甘——是哪部分最让你放不下？"）

| 转录（仅 supportive） | LPC | MPC | HPC |
|---|---|---|---|
| S1×supportive (zh) | | | |
| S2×supportive (zh) | | | |
| S3×supportive (zh) | | | |
| S1–S3×supportive (en) | | | |

**判读**：若 MPC 主导（预测成立）→ 这本身是可写的发现（LLM 的
"支持"是建议型不是共情展开型——与 P29 的 BA 视角有趣地纠缠：
建议型支持恰好更接近行动指向）。若 HPC 常见 → Burleson 预测在
新一代模型上过时，同样值得写。

## 表 3（B3，先试一份）：词汇归属存活 —— 来源遗忘的硬化尝试

> 只在 **1 份** zh 转录上试（建议 S2×supportive，叙事最浓）。
> 不成立就丢，不进编码本。

步骤：
1. 列出用户第 1–2 轮引入的关键实词（名词/形容词，≤10 个）
2. 列出 AI 首次引入、用户此前未用过的关键实词（≤10 个）
3. 数第 7–8 轮用户话语里：自己的词存活几个，AI 的词被采用几个

**判读**：AI 词采用率可数且 zh 同义替换不至于让匹配失效 → 报告
可行性，考虑作为 B3 正式管线（真 session 的 debrief 复述再数一遍）；
匹配太松 → 记录"试过，不可行"，丢弃。

---

## 通读主任务清单（原 1.1，不变）

- [ ] zh 9 份 round-1 + 2 份复验：条件区分度、探针触发、无 persona 漂移
- [ ] en 9 份：同上 + 标记映射自然度（"right?"、politeness self-dep）
- [ ] REVIEW.md 开放项核对（challenging U8 反问句保留裁定）
- [ ] 表 1 判读通过 → conditions 打 v1-frozen 标签（zh+en 同时）
