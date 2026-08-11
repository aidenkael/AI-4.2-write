# BookDistill —— 原著蒸馏纪律工作台（vNext Base Scan 升级）

## 定位

C19（原著蒸馏 / 能力发现）的最小可运行实现，当前属于能力地图方法论层（M4）。
v0.2 在 v0.1.1 确定性 Core 基础上，增加 Base Scan 升级、BookProfile、专项深挖支持。
目标是：对 SourcePrepare PASS 的真实作品，产出**可追溯、分类清晰、边界明示、全维度覆盖**的蒸馏证据，
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
| `book_profile.md` | **v0.2 新增**：BookProfile（维度覆盖、深挖建议，脚本生成骨架，Agent 填写判断） |
| `deepdive/dd_<维度>.md` | **v0.2 新增**：专项深挖底稿（复用 assemble 校验逻辑） |
| `bd_report.md` | 蒸馏报告（来源身份 / 覆盖 / 边界 / 状态） |
| `chapters_index.md` | 章节索引（章节/标题/字符数/行数）与引用规范 |
| `evidence/ch_NNNN.md` | 每章证据底稿（FACT / INFERENCE / OBSERVATION / MECHANISM / BOUNDARY）+ MAP |
| `distill_manifest.json` | assemble 校验清单 + source snapshot + dimension_stats |
| `bkp/` | **v0.2 新增**：BKP Finalize 正式知识包（`identity.json` / `README.md` / `work_map.md` / `profile.md` / `knowledge/` / `deep_dive/`，依据 `BKP_v0.1_protocol.md`） |

### source snapshot（固化在 distill_manifest.json / bd_report.md）

`metadata.json` 属于 Local Only 不上传，因此 tracked 产物必须自行携带不可篡改的输入指纹：

- `source_sha256`：选定来源文件 SHA256（来自 SourcePrepare metadata）
- `sp_version` / `book_id` / `chapter_count`
- `chapter_content_fingerprint`：按稳定章节顺序（`NNNN.md` 升序）对
  `文件名 + "\0" + 文件字节` 聚合后的 SHA256；任何转换结果变化都会被检测到

产物中**不得保存原始素材真实文件路径**。

## 证据纪律（C19 已验证原则，v0.2 扩展）

1. **evidence-first**：每条条目必须带原文引用 `chapters/NNNN.md#L<起始行>-L<结束行>`。
2. **分层**：FACT（原文可直接支持）/ INFERENCE（推断，不直接出现在字面）/ **OBSERVATION**（v0.2：作品内观察，按维度标记，不强制收口为 MECHANISM）/ MECHANISM（可迁移机制）/ BOUNDARY（本条边界与不确定性）。
3. **MAP 独立**：MAP 是结构性作品地图，不属于 Evidence kind；填写场景/人物/时间线/信息状态/冲突等结构信息。
4. **维度标记**：OBSERVATION 条目须携带 `dimension:维度名` 标签（如人物、关系、信息控制、POV、情绪、Scene Turn 等）。维度框架为可扩展 v0.1 观察列表，不是永久冻结的封闭枚举。
5. **coverage 明示**：报告必须写明哪些章节覆盖充分、哪些局部、哪些未覆盖；空证据模板 = 未分析章节，在 manifest 记警告。assemble 新增 `dimension_stats` 字段统计各维度覆盖。
6. **confidence 标记**：每条条目标记置信度 高/中/低。
7. **counterevidence / boundary**：BOUNDARY 不省略；反证、译本影响、样本局限必须记录。
8. **不大量复制原文**：条目为一句话结论 + 行号引用，不摘抄大段原文。
9. **可迁移机制，不做剧情换皮**：MECHANISM 必须说明“为何可迁移”（从具体文本抽象技法），禁止“某角色做了某事所以这样写”式的剧情复述。
10. **不随意外推**：局部样本只标记为局部证据，不宣称覆盖整书或整个类型。
11. **coverage 不是价值判断**：维度覆盖统计只是 BookProfile 的辅助信号，禁止“Observation 数量多 = 更重要”这类机械判断。
12. **不做原作者风格模仿器**：产出是分析性证据，不是模仿奥威尔文风的仿写样本。

## 工作流（v0.2 vNext 流程）

1. `validate`：校验 SourcePrepare PASS 包（状态、版本、book_id、文件、章节一致性、SHA256、空章节）。
2. 阅读 `chapters/` 原文（逐章阅读，不做抽样猜整书）。
3. `prepare`：生成章节索引 + 每章证据模板（含 MAP 和 OBSERVATION 节）+ 报告骨架 + 初始 manifest。
4. **Base Scan**：在 `evidence/ch_NNNN.md` 按模板填写：
   - MAP（章节作品地图，结构性信息）
   - FACT / INFERENCE / OBSERVATION（携带维度标签）/ MECHANISM / BOUNDARY
   - 第一次完整扫描优先支持作品地图 + Observation + Evidence + 少量 Pattern + uncertainty
5. `assemble --input <SourcePrepare PASS> --output <BookDistill 输出>`：
   校验条目分类合法性、引用可追溯与**行号不越界**，
   重算输入 snapshot 并比对，计算**维度覆盖统计**，生成 `distill_manifest.json`。
6. `profile --output <BookDistill 输出>`：生成 `book_profile.md`（维度覆盖、深挖建议骨架）。
   脚本只做确定性统计；文学价值判断由运行 Skill 的 Agent 完成。
7. `deepdive --output <BookDistill 输出> --dimension <维度名> [--input <SourcePrepare PASS>]`：生成专项深挖模板。
   专项文学分析优先参考 Apodictic / ani-book / creative-writing-skills / oh-story 的分析框架。
   传入 `--input` 时复用 assemble 校验逻辑（引用格式、章节存在性、行号越界）校验已填写的深挖内容；不传 `--input` 时仅生成模板。文件已存在时不覆盖。
8. 跨章收敛机制：从逐章 MECHANISM 中合并同质、降级单章小技巧、补充反证，
   产出 `mechanisms.md`（10–20 条高价值机制，不设数量指标）。
9. 生成 `evidence.md`（精选支撑最终结论的证据）与 `model.md`（作者第一阅读入口）。
10. 完成 `bd_report.md`：来源身份 + 覆盖范围与置信度 + 边界与不确定性 + 状态。
11. `bkp --output <BookDistill 输出> [--prototype <原型目录>]`：BKP Finalize——
    读取 `bkp_prototype/`（人工验证的知识层），校验身份/源指纹、Observation/Inference/Pattern
    类型边界、引用可追溯与条目计数后，封装正式 BKP 到 `bkp/`；
    重跑不覆盖被人工修改的 curated 文件（仅告警保留）。
12. 作者审阅产物。

## 运行方式

```powershell
python scripts/book_distill.py validate --input "06_工作区/SourcePrepare/<book_id>_<书名>"
python scripts/book_distill.py prepare  --input "06_工作区/SourcePrepare/<book_id>_<书名>" --output "02_原著蒸馏/<book_id>_<书名>"
python scripts/book_distill.py assemble --input "06_工作区/SourcePrepare/<book_id>_<书名>" --output "02_原著蒸馏/<book_id>_<书名>"
python scripts/book_distill.py profile  --output "02_原著蒸馏/<book_id>_<书名>"
python scripts/book_distill.py deepdive --output "02_原著蒸馏/<book_id>_<书名>" --dimension "人物" --input "06_工作区/SourcePrepare/<book_id>_<书名>"
python scripts/book_distill.py bkp      --output "02_原著蒸馏/<book_id>_<书名>"  # 默认读取 <output>/bkp_prototype
```

测试：

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

## 范围边界

- 本技能只做 1 部作品的真实蒸馏；批量蒸馏、RAG、知识图谱、多 Agent、复杂长期状态不属于当前版本。
- 脚本不调用大模型；分析内容由运行本 Skill 的 Agent / 作者填写。
- **v0.1 不提供自动 resume**：中断时依赖已有文件人工继续，不实现断点/状态恢复。
- BKP schema 未冻结（`BKP_v0.1_protocol.md` 第 8 节）；`bkp` 子命令只做最小 Finalize
  封装（校验 + 复制白名单知识文件 + 生成 identity.json），不新增 schema，
  不自动升级知识等级（单书 BKP 最高为 Work-specific Pattern）。
- 逐章 evidence 与 manifest 是 audit appendix / 工作附件；作者核心产物是
  `model.md` / `evidence.md` / `mechanisms.md` / `book_profile.md` / `bd_report.md`。
- 详细的逐章工作底稿优先放 `06_工作区/BookDistill/<book>/`（Local Only），
  不把 `02_原著蒸馏` 默认膨胀成逐章分析数据库。
- 专项深挖的文学分析方法优先参考已有来源（Apodictic / ani-book / creative-writing-skills / oh-story），
  当前只吸收分析框架/方法纪律，不整体复制外部代码或 Prompt。
- 方法来源与许可证记录见 `PROVENANCE.md`。
