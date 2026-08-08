# BookDistill（BD）Skill — 接口约定（仅文档）

版本：0.1.0（接口草案）

> 本文件仅定义 BookDistill 与上游 SourcePrepare、下游作品工程的**接口契约**。
> 本轮不实现 BookDistill 的转换/蒸馏逻辑，只固化接口，避免后续实现时破坏已稳定的目录与索引。

## 定位

BookDistill 消费 SourcePrepare 产出的标准化 Markdown，生成“单书完整写作模型”，
落到 `02_原著蒸馏`。它**只读** `06_工作区` 的中间产物，不接触 `01_原始素材` 原始文件。

## 上游接口：输入来自 SourcePrepare

输入位置（由 SourcePrepare 产出，Local Only）：

`06_工作区/SourcePrepare/<作品ID>_<作品>/`

- `full.md` —— **主输入**：选源后的完整正文，BookDistill 默认消费它。
- `chapters/*.md` —— 拆分后的章节文件；需要按章分析时使用。
- `metadata.json` —— 溯源（选中来源路径 / SHA256 / 字符数 / 章节数 / SP 状态）。
- `conversion_report.md` —— 人类可读质检报告。

### 读取前置条件（必须遵守）

BookDistill **只读取 SourcePrepare 状态为 `PASS` 的作品**；

- `REVIEW`：需人工在 `06_工作区` 或索引中确认后再读；
- `FAIL` / `NOT_APPLICABLE`：**禁止**进入 BookDistill；
- 索引中状态见 `00_项目控制/原始素材清单.csv` 的 `SourcePrepare状态` 列。

### 作品定位方式

BookDistill 通过 `<作品ID>_<作品>` 目录名与 `metadata.json` 中的 `book_id` 关联索引，
**不依赖**作品在 `01_原始素材` 中的物理路径。这样即使原始素材按格式/版本变动，蒸馏结果仍可回溯。

## 下游接口：输出到 02_原著蒸馏

输出位置：

`02_原著蒸馏/<作品ID>_<作品>/`

建议结构（供实现时参考，本轮不强制）：

```text
<作品ID>_<作品>/
├─ model.md            # 单书完整写作模型（人物/节奏/结构/主题/爽点等）
├─ characters.md       # 人物图谱
├─ outline.md          # 结构与节奏拆解
└─ bd_report.md        # 蒸馏说明与置信度
```

> `02_原著蒸馏` 属于可公开/可协作的知识产物，**不受 Local Only 限制**
> （它不含第三方原文全文，是分析模型）。是否上传 GitHub 由项目整体规则决定。

## 与 SourcePrepare 的契约边界

```text
01_原始素材 ──(只读)──> SourcePrepare ──> 06_工作区/SourcePrepare/<ID>_<作品>/
                                                  │  full.md / chapters/
                                                  ▼ (仅读 PASS)
                                              BookDistill
                                                  ▼
                                          02_原著蒸馏/<ID>_<作品>/
                                                  ▼
                                          03_作品工程
```

- SourcePrepare 保证 `full.md` 是“尽量完整、干净、可验证”的正文，不分析内容；
- BookDistill 不回写 `01_原始素材`，也不修改 SourcePrepare 的输出；
- 若发现 SourcePrepare 产物质量不足（如章节错位、缺章），应在索引备注或 `bd_report.md`
  中记录，并反馈给 SourcePrepare 重跑，而不是自行修补原文。

## 状态回写（供实现时参考）

BookDistill 完成后应回写索引 `00_项目控制/原始素材清单.csv` 的 `BookDistill状态` 列
（`未开始 / 进行中 / 已完成 / 不适用`），保持与 SourcePrepare 相同的索引契约。
回写工具复用 `scripts/index_builder.py` 的 `update_book()`。
