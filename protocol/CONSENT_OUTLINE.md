# 签署包清单（v1 — 2026-08-04 对齐 Brennan 官方伦理文件后重写）

> **官方文件已到位**（`../consent/`）：Participant Information Sheet +
> Informed Consent Form（均 V1, 2026-06-09，伞形项目 "Context-Aware
> AI-Assisted Personal Reflection"，XJTLU 伦理已批，Alex 为列名
> co-investigator）。本研究是伞下的一个 study activity；信息单
> "researcher will explain the study activity before you consent" 一句
> 是我们 incomplete-disclosure 口径的挂载点。
> 本文件从"自拟同意书草稿"改为**签署包清单**：参与者签什么、每项
> 对应哪个文件、我们的 study-specific 补充项是什么。
> 旧版 v0 的自拟条款凡与官方文件重叠的，一律以官方文件为准。

---

## 参与者要签的东西（按顺序）

### 1. Participant Information Sheet（官方，提前发）

- 筛选通过后、session 前发给参与者阅读（链接或 PDF）
- Session 开场确认已读、答疑

### 2. Informed Consent Form（官方，session 开场签）

官方表内已含五项确认 + 两个选择题：
- 已读信息单 / 自愿参与 / 匿名化前可获取或销毁数据
- **视频（仅屏幕共享）+ 音频录制**用于研究
- 主选择：Agree 参与
- **可选档：腾讯会议第三方云端 AI 转写**（单独 Agree/Disagree）

【主持人注意：录制方式=腾讯会议屏幕共享+音频。这覆盖了旧 v0 的
"可选档 A 录音录屏"——不再需要自拟录音同意，但见下方"未决问题 2"
关于 scroll-back 段的处理。】

### 3. Study-specific 补充确认（我们的，口头+勾选，session 开场）

官方表未覆盖、本研究特有的两项：

- [ ] **聊天记录捐赠意向**（阶段 4 才实际发生）："session 结束时
      我们会问你是否愿意分享部分你自己的 AI 聊天记录——流程是你
      自己导出→自己浏览删减→确认后才传输，完全可选，现在只是
      提前告知。"附加风险口径照旧：即使删除姓名，内容本身可能
      含可推断信息；与转录同级安全标准存储。
      【in-situ pattern prompt（INSITU_PATTERN_PROMPT.md，校准
      通过后启用）作为捐赠的中间档，同属此项意向确认覆盖范围】
- [ ] **报酬确认**：¥60/小时（官方标准）× 本 session 时长 ≈
      **¥90–120**，按实际时长结算，现金/转账/红包按参与者方便。

### 4. Debrief 补充确认（session 末尾，揭示后）

（官方文件无此项，是我们 incomplete-disclosure 设计的收尾件，保留 v0 原样：）

- 我已了解研究的完整目的（包括三段对话为同一模型的不同回应风格）
- 了解完整目的后，我：
  - [ ] 同意继续使用我的全部数据
  - [ ] 要求排除以下部分：____

---

## 口径对齐（旧 v0 → 官方）

| 项 | 旧 v0 | 现行（官方为准） |
|---|---|---|
| 撤回窗口 | "session 后 30 天内" | **匿名化之前**随时可撤回（官方条款3/13）；操作上我们把匿名化时点定为 session 后 30 天，效果等价但措辞必须用官方的 |
| 报酬 | 空白待填 | ¥60/小时（官方 §9） |
| 数据存储 | "研究组加密存储" | XJTLU Box，3 年后销毁（官方数据表） |
| 录音/录屏 | 自拟可选档 A | 官方表主条款（腾讯会议）+ 可选 AI 转写档 |
| 第三方 AI 服务 | 未提 | 官方 §8 已含跨境传输披露；我们用 AWS Bedrock（Anthropic 模型，美国区）——落在 "or similar services" 内，**待与 Brennan 口头确认**（未决问题 4） |
| 投诉渠道 | 未提 | 官方 §14（ethics@xjtlu.edu.cn）——debrief 材料里附上 |

## ⚠ 未决问题（进 2.1 给 Brennan 的信 / 下次 meeting）

1. **时长**：信息单写 "typically 45–90 minutes"，我们的 session 是
   90–120 分钟。"typically" 是否容纳 120？还是我们压缩流程/信息单
   出 V2？
2. ~~Scroll-back 录屏 vs "原文不留存"~~ → **已化解（08-04 Alex
   裁决）**：参与者一般在**自己手机上**和 AI 聊天，scroll-back 在
   参与者手机上进行，手机屏幕**不入会议录制**（录的是主持人侧
   屏幕共享+双方音频）。参与者拿着手机口述，主持人用结构化提问
   提取（见 SESSION_PROTOCOL 2b 更新），原文自然不落任何记录——
   与"take notes rather than raw text"的设计承诺一致，无需二选一。
   残余确认项：给 Brennan 提一句"scroll-back 发生在参与者自己
   设备上、不入录制"即可，预计无争议。
3. **捐赠档的伦理覆盖**：官方信息单覆盖"原型交互日志"+媒体历史
   导出类比（YouTube 条款），参与者**自己账号聊天记录**的捐赠
   是否需要伦理侧补一档，请 Brennan 判断。in-situ prompt 同问。
4. **供应商清单**：官方列 OpenAI/Qwen/DeepSeek "or similar
   services"；我们实际用 **AWS Bedrock（Anthropic 模型，美国区
   endpoint）**。跨境传输规则依据 AWS 的数据隐私与跨区传输框架，
   给参与者/伦理侧可附的链接：
   - AWS 数据隐私常见问题：https://aws.amazon.com/compliance/data-privacy-faq/
   - AWS Bedrock 数据保护（输入输出不用于训练、不出所选区域）：
     https://docs.aws.amazon.com/bedrock/latest/userguide/data-protection.html
   大概率被"similar services"覆盖，口头确认留痕；若信息单出 V2，
   建议供应商例举里加 "AWS Bedrock (Anthropic)" 一项。

## 伦理基础（不变）

Incomplete disclosure（如实描述主题、暂不披露风格操纵与具体假设，
debrief 完整揭示）——非 deception。官方信息单的伞形描述（"研究
人们如何使用 AI 反思工具"）如实覆盖本研究而不暴露假设，结构兼容。
阶段 1 的口头口径见 SESSION_PROTOCOL 阶段 1。
