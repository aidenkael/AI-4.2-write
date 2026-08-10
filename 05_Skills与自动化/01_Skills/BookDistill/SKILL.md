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
- 磁盘正文章节数（仅 `NNNN.md`）与 `metadata.chapter_files` **精确相等**；
  `0000_前置内容.md` 不计入正文计数，任何 ±1 一律 FAIL（防止实际缺章被静默放过）
- 输入目录名必须形如 `<book_id>_<书名>`，前缀与 `metadata.book_id` 精确一致

BookDistill 不读取 `01_原始素材` 作为正文输入；不修改 SourcePrepare 输出。

## 输出契约

目录：`02_原著蒸馏/<book_id>_<书名>/`

| 文件 | 内容 |
|---|---|
| `model.md` | **作者核心产物**：整体写作模型（第一阅读入口） |
| `evidence.md` | **作者核心产物**：支撑 model/mechanisms 的精选证据索引 |
| `mechanisms.md` | **作者核心产物**：跨章收敛后的可迁移机制集（含反证/失败模式） |
| `bd_report.md` | 蒸馏报告（来源身份 / 覆盖 / 边界 / 状态） |
| `chapters_index.md` | 章节索引（章节/标题/字符数/行数）与引用规范 |
| `evidence/ch_NNNN.md` | 每章证据底稿（FACT / INFERENCE / MECHANISM / BOUNDARY） |
| `distill_manifest.json` | assemble 校验清单 + source snapshot（见下） |

### source snapshot（固化在 distill_manifest.json / bd_report.md）

`metadata.json` 属于 Local Only 不上传，因此 tracked 产物必须自行携带不可篡改的输入指纹：

- `source_sha256`：选定来源文件 SHA256（来自 SourcePrepare metadata）
- `sp_version` / `book_id` / `chapter_count`
- `chapter_content_fingerprint`：按稳定章节顺序（`NNNN.md` 升序）对
  `文件名 + "\0" + 文件字节` 聚合后的 SHA256；任何转换结果变化都会被检测到

产物中**不得保存原始素材真实文件路径**。

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
3. `prepare`：生成章节索引 + 每章证据模板 + 报告骨架 + 初始 manifest（固化 source snapshot）。
4. 在 `evidence/ch_NNNN.md` 按模板填写条目。
5. `assemble --input <SourcePrepare PASS> --output <BookDistill 输出>`：
   校验条目分类合法性、引用可追溯与**行号不越界**（`end <= 章节实际总行数`），
   重算输入 snapshot 并与 prepare 时记录比对，生成 `distill_manifest.json`。
6. 跨章收敛机制：从逐章 MECHANISM 中合并同质、降级单章小技巧、补充反证，
   产出 `mechanisms.md`（10–20 条高价值机制，不设数量指标）。
7. 生成 `evidence.md`（精选支撑最终结论的证据）与 `model.md`（作者第一阅读入口）。
8. 完成 `bd_report.md`：来源身份（source SHA256 / fingerprint / 版本）+
   覆盖范围与置信度 + 边界与不确定性 + 状态。
9. 作者审阅产物。

## 运行方式

```powershell
python scripts/book_distill.py validate --input "06_工作区/SourcePrepare/<book_id>_<书名>"
python scripts/book_distill.py prepare  --input "06_工作区/SourcePrepare/<book_id>_<书名>" --output "02_原著蒸馏/<book_id>_<书名>"
python scripts/book_distill.py assemble --input "06_工作区/SourcePrepare/<book_id>_<书名>" --output "02_原著蒸馏/<book_id>_<书名>"
```

测试：

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

## 范围边界

- 本技能只做 1 部作品的真实蒸馏；批量蒸馏、RAG、知识图谱、多 Agent、复杂长期状态不属于 v0.1。
- 脚本不调用大模型；分析内容由运行本 Skill 的 Agent / 作者填写。
- **v0.1 不提供自动 resume**：中断时依赖已有文件人工继续，不实现断点/状态恢复；
  若未来真实第二本书证明需要，再从 C17/C20 候选中选择最小机制。
- 逐章 evidence 与 manifest 是 audit appendix / 工作附件；作者核心产物是
  `model.md` / `evidence.md` / `mechanisms.md` / `bd_report.md`。
- 详细的逐章工作底稿优先放 `06_工作区/BookDistill/<book>/`（Local Only），
  不把 `02_原著蒸馏` 默认膨胀成逐章分析数据库。
- 方法来源与许可证记录见 `PROVENANCE.md`。
