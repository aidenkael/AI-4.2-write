# BookDistill —— 最小原著蒸馏 / 能力发现

## 定位

C19（原著蒸馏 / 能力发现）的最小可运行实现，当前属于能力地图方法论层（M4）。
目标是：对 1 部 SourcePrepare PASS 的真实作品，产出**可追溯、分类清晰、边界明示**的蒸馏证据，
供作者审阅并沉淀可迁移写作机制。不是剧情复述，不是风格模仿器，不是批量蒸馏流水线。

## 输入契约（SourcePrepare PASS 包）

目录：`06_工作区/SourcePrepare/<book_id>_<书名>/`

必须存在且校验通过：

- `metadata.json`：`status == "PASS"`、`book_id`、`selected_source.sha256`（源指纹）
- `full.md`、`conversion_report.md`
- `chapters/NNNN.md`：正文章节（`0000_*.md` 视为卷首前置，不参与正文蒸馏）
- 磁盘章节数与 `metadata.chapter_files` 一致（允许且仅允许差 1：0000 前置）

BookDistill 不读取 `01_原始素材` 作为正文输入；不修改 SourcePrepare 输出。

## 输出契约

目录：`02_原著蒸馏/<book_id>_<书名>/`

| 文件 | 内容 |
|---|---|
| `chapters_index.md` | 章节索引（章节/标题/字符数/行数）与引用规范 |
| `evidence/ch_NNNN.md` | 每章证据底稿（FACT / INFERENCE / MECHANISM / BOUNDARY） |
| `distill_manifest.json` | assemble 校验清单（分类统计、错误、警告、覆盖） |
| `bd_report.md` | 蒸馏报告（方法 / 覆盖范围与置信度 / 边界与不确定性） |

## 证据纪律（C19 已验证原则，逐条落地）

1. **evidence-first**：每条条目必须带原文引用 `chapters/NNNN.md#L<起始行>-L<结束行>`。
2. **分层**：FACT（原文可直接支持）/ INFERENCE（推断，不直接出现在字面）/ MECHANISM（可迁移机制）/ BOUNDARY（本条边界与不确定性）。
3. **coverage 明示**：报告必须写明哪些章节覆盖充分、哪些局部、哪些未覆盖；空证据模板 = 未分析章节，在 manifest 记警告。
4. **confidence 标记**：每条条目标记置信度 高/中/低。
5. **counterevidence / boundary**：BOUNDARY 不省略；反证、译本影响、样本局限必须记录。
6. **不大量复制原文**：条目为一句话结论 + 行号引用，不摘抄大段原文。
7. **可迁移机制，不做剧情换皮**：MECHANISM 必须说明"为何可迁移"（从具体文本抽象技法），禁止"某角色做了某事所以这样写"式的剧情复述。
8. **不随意外推**：局部样本只标记为局部证据，不宣称覆盖整书或整个类型。
9. **不做原作者风格模仿器**：产出是分析性证据，不是模仿奥威尔文风的仿写样本。

## 工作流

1. `validate`：校验 SourcePrepare PASS 包（状态、版本、book_id、文件、章节一致性、SHA256、空章节）。
2. 阅读 `chapters/` 原文（逐章阅读，不做抽样猜整书）。
3. `prepare`：生成章节索引 + 每章证据模板 + 报告骨架。
4. 在 `evidence/ch_NNNN.md` 按模板填写条目。
5. `assemble`：校验条目分类合法性与引用可追溯，生成 `distill_manifest.json`。
6. 完成 `bd_report.md` 三节：方法 / 覆盖范围与置信度 / 边界与不确定性。
7. 作者审阅产物。

## 运行方式

```powershell
python scripts/book_distill.py validate --input "06_工作区/SourcePrepare/<book_id>_<书名>"
python scripts/book_distill.py prepare  --input "06_工作区/SourcePrepare/<book_id>_<书名>" --output "02_原著蒸馏/<book_id>_<书名>"
python scripts/book_distill.py assemble --output "02_原著蒸馏/<book_id>_<书名>"
```

测试：

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

## 范围边界

- 本技能只做 1 部作品的真实蒸馏；批量蒸馏、RAG、知识图谱、多 Agent、复杂长期状态不属于 v0.1。
- 脚本不调用大模型；分析内容由运行本 Skill 的 Agent / 作者填写。
- 方法来源与许可证记录见 `PROVENANCE.md`。
