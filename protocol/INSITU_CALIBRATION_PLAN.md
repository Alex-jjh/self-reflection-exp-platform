# In-situ 自摘要仪器校准计划（KANBAN 3.14）

> 2026-08-07 定稿。前置：`INSITU_PATTERN_PROMPT.md` v0.1（含新增 4d）。
> 为什么这一步是承重墙：P42（surf-docs `research-reports/round4/`）裁决
> in-situ 自摘要法**无发表先例、可主张为方法学贡献**，但同时指出最强
> 审稿反对 = **未验证的转换层**——没有任何已发表研究验证过"AI 摘要
> 自己参与的对话"的忠实度（LLM 编码 κ=.6–.79 只是第三方编码的相邻
> 证据）。本校准就是对这条反对的直接回答。校准通过前，in-situ 档
> 不进协议、其产出只标 exploratory。

## 1. 设计

**语料**：`pilot-transcripts/` 的 18 个最新 cell（S1–S3 × zh/en ×
supportive/challenging/neutral，Sonnet 5，8 轮/份）。零参与者数据、
零招募成本；人工基准编码可公开复核。

**自指结构的复现（核心效度设计）**：真实部署里，做摘要的 AI 就是
产出对话的 AI（在同一上下文里）。校准严格复现这一点——把 prompt
作为**第 9 轮用户消息**追加进原 message history，system prompt 用
产生该对话的同一条件文件，同模型同参数调用。**不是**把 transcript
喂给一个旁观模型去总结——那测的是第三方编码，P42 说那已有相邻
文献；我们要验证的恰恰是自指摘要（模型给自己的行为计数，存在
自利折价的结构性可能）。

**基准编码（reference standard）**：对同一 18 份 transcript，按
prompt 条目逐项人工计数（AI 初编 + Alex 裁决，沿用 4.1 纪律；
每个计数必须附可 grep 的原文定位，使裁决机械可复核）。基准编码
在**看不到 AI 自摘要**的情况下完成（防锚定）。

**两层指标**：
1. **引文可核率（全自动）**：自摘要里的每条短引文是否在原
   transcript 里逐字出现。捏造引文=转换层失效的最硬信号，且
   零人工成本。runner 自动计算。
2. **per-code 计数一致率（人工对照）**：AI 自报计数 vs 基准计数，
   报精确一致与 ±1 一致两档。按条目分别裁决：
   - 通过（精确或 ±1 一致率高）→ 保留，methods 附录报告该条目一致率
   - 系统性偏移（方向一致的高估/低估）→ 保留但只作序数用，标注偏移方向
   - 失效（不相关或捏造）→ 从 prompt 删除

**预注册的预期**（v0 就写在 prompt 对照表里，先于数据）：表层形式
码 2a/2b/4a/4b/5 可用；功能码 3a/3b 部分失真；自指最重的 3c 大概率
删除。4d（新增）无预期，探索。

**自利折价的方向性检验**：如果失真存在，预期方向是模型**低报**
自己的 3a（接受用户框架）与 3c（口头转折实同意）、**高报** 3b
（提出异议）。条件间对照给了免费的杠杆——同一模型在 supportive
vs challenging 条件下的自报 3b 应该有真实差异（基准编码可证），
若自摘要抹平或夸大这个差异，即为方向性证据。

## 2. 已知限制（写进 methods 的话）

- 校准语料是 Claude（Sonnet 5）；参与者实际用 GPT/Gemini/豆包。
  校准结论严格说只覆盖"Claude 摘要 Claude"。**扩展臂（可选，
  after v1）**：把同一 prompt 喂给 Gemini/GPT 处理同一批 transcript
  （作为旁观者），self vs other 摘要的计数差即自利折价的直接估计。
- 语料是 8 轮脚本对话，短于真实捐赠对话（P03 Conv 1 = 51 轮）；
  长上下文的计数衰减未覆盖，报告时注明。
- 频次基数低（8 轮里单条目计数 0–5），一致率的分辨率有限；
  这也是为什么引文可核率是第一道闸。
- prompt-version 错位：08-04 的 challenging cells 由旧版 challenging
  prompt 产生，runner 复现上下文时加载的是当前条件文件（S1 zh
  challenging 已是 08-05 新版重跑）。计数对象是 transcript 本身，
  错位只影响摘要轮的 system prompt，非计数语料——记录，不阻塞。

## 3. 执行清单

- [x] prompt v0.1：新增 4d（修正方向——P03 捐赠观察：AI 让步 7 次，
      但让步方向未知；ToF 的隐蔽形态）
- [x] `tools/insitu_calibration.py`：追加式自摘要 runner + 引文
      自动核对，产出 `calibration/`
- [ ] 跑 18 cell，看引文可核率
- [ ] 基准编码（AI 初编 + Alex 裁决）
- [ ] per-code 对照表 + 逐条目裁决 → prompt v1
- [ ] v1 过闸 → 进 SESSION_PROTOCOL 捐赠分层；methods 附录初稿
