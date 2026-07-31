# 问卷平台导入 — 现状、踩坑记录与决策

> 状态截至 2026-07-31。**结论:Qualtrics 免费账号无法自动化建问卷;转向学校 LimeSurvey（待确认版本+导入权限）。**

## TL;DR

- 内容早已定稿：题目/刻度/逻辑的**唯一真值源 = `QUALTRICS_BUILD_SHEET.md`**（逐条核对过，与 `QUESTIONNAIRE.md` 一致）。平台无关的结构化中间表示 = `survey_structure_ir.json`。
- **Qualtrics 死路**：此账号是免费版，**QSF 导入和 API 都被许可挡死**——实测连未改动的官方 sample QSF 都导不进，API 面板显示 "organization has not purchased the API"。所以在 Qualtrics 上只能**网页手动逐题建**。
- **LimeSurvey 是更优路径**（若学校实例可用）：社区版原生支持 `.lss` 导入 + flexible Array（每量表独立刻度）+ 跳转 + 双语，能**一次导入建好**。**待你确认两件事**：① 版本号（3.x/5.x/6.x，决定 .lss schema）；② 新建问卷时有无 "Import survey" 选项（导入权限）。

## 为什么 QSF 折腾了三次都没用（重要教训）

前三版 `survey_build.qsf` 反复改字段（Language 格式、补 QC/RS/PL、Trash block、Autoscale…），全部导入失败。**真相是：失败从来不在文件**——做对照实验（导未改动的官方真实 sample）也失败，才定位到是**账号许可层面禁用了 QSF 导入**。教训：验证一条路径（导入）本身可用，应该在造文件**之前**做，而不是造完拿人当验证器盲试。

## 文件清单

| 文件 | 性质 | 说明 |
|---|---|---|
| `QUALTRICS_BUILD_SHEET.md` | ⭐真值源 | 逐题录入稿，跨平台通用（手动建 / computer-use agent 都照它） |
| `survey_structure_ir.json` | 中间表示 | 平台无关的题→类型→选项/行/刻度 结构，造 .lss / 任何格式的原料 |
| `survey_build.qsf` | 过程记录 | 基于真实 Qualtrics 模板重建的 QSF；**此账号导不进**，留作若将来拿到企业版/机构账号可直接用 |
| `survey_build.qsf.bak` | 过程记录 | 更早一版（含内嵌翻译），仅留档 |
| `survey_translations_import.tsv` / `survey_en_translations_reference.tsv` | Qualtrics 专用 | 双语翻译表，仅在走 Qualtrics 翻译层时用 |
| `survey_import_zh.txt` / `survey_import_en.txt` | Qualtrics 专用 | Advanced TXT 导入格式（同样受账号导入权限限制，未验证） |
| `REF_qualtrics-encoding.md` | 参考存档 | 真实 Qualtrics 导出验证过的 QSF 编码规范（来自 mannyficient/qsf-generator），诊断 QSF 的依据 |

> 参考源码克隆在 `refsrc/`（.gitignore 已排除，因是第三方 repo）：`qsf-generator/`（编码规范）、`qsf/`（sumtxt R 包，能基于真实 QSF 编辑）、`qualtrics-utils/`（Python，API 客户端）。

## 下一步

1. 【你】登录学校 LimeSurvey → 反馈版本号 + 是否有导入权限。
2. 【AI】据版本生成对版 `.lss`（含 7 个 flexible Array 各自刻度 + 资格跳转 + Q17 显示逻辑 + 双语），从 `survey_structure_ir.json` 造。
3. 先导一份官方 sample .lss 验证通路（吸取 Qualtrics 教训），再导我们的。
4. 若学校 LimeSurvey 也锁导入 → 回到"哪个平台手工建更省事"重估（那种情况 Qualtrics 拖拽可能更快）。

## 内容本身没问题

题目/刻度/条目数/淘汰逻辑/显示逻辑/题干干净度此前都逐条核对过。以上全部是"用哪个平台、怎么把内容搬进去"的问题，从未改动任何题目内容。
