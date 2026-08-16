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
| `bkp/` | BKP v0.2 正式知识包：`knowledge/cards.md` 为 canonical 知识层，`author_view.md` 为非权威八区投影；旧 v0.1 split files 仍可读取，依据 `BKP_protocol.md`。 |

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
13. **重要发现可跨尺度、跨位置聚合**：一条高价值 Observation / Pattern 可以由多个不相邻句子、场景或章节共同支撑；不得为了“一条结论只配一个局部证据”而拆散真实效果链。
14. **保留未命名价值**：发现“重要但暂时难以命名”的创作智慧时，允许先以 Observation / Inference 保存，不得因为暂时不属于现有 taxonomy 而丢弃。

## 原著 Discovery：多视角直接阅读（G3 closeout 方法修正）

BookDistill 不再被要求单枪匹马发现一本书的全部精华。它的核心职责是**总编辑式收敛**：让互补观察镜头直接阅读同一原著，随后回源核证、合并重复、识别组合效果、补边界/反例/置信度，并封装为 BKP。

### 原则

1. **原著始终是最高事实源。** 重要观察镜头应直接读取原文，不经过“Profile 摘要 → 二手摘要 → 再总结”的逐层压缩链。
2. **BookProfile 是导航，不是过滤器。** 它用于分配后续深挖预算，不能提前宣布其他维度“没有价值”。
3. **默认使用两个互补 Discovery 镜头；不是两个固定 Skill。** 可以由同一个 Agent 分 Pass、多个 Agent、成熟上游 Skill 或其他简单实现完成，不冻结实现形式。
4. **专项 Developmental Deep Dive 按问题触发，不默认全跑。** 只有 Base / Discovery 暴露明显高价值或不确定问题时才进入。
5. **作品 contract / reader promise / controlling idea 属于合法观察对象。** 既要看“作者做了什么”，也要看“作品向读者承诺了什么、实际怎样兑现或偏离”。
6. **发现阶段可以宽，BKP 必须克制。** 多镜头可产生很多候选；最终只有长期有调用价值、证据充分且边界清楚的知识进入 BKP。

### 默认镜头 A：长篇运行 / 读者动力

优先借鉴 oh-story 与 AI-Novel-Writing-Assistant 已成熟的方法，重点观察但不限于：

- story engine、长篇推进与阶段变化；
- 作品承诺、题材/类型读者预期、核心 reader promise；
- 章节/场景功能、主角即时欲望与阻力；
- 期待建立、延迟、部分兑现、重大兑现与旧钩子责任；
- 情绪生态、压力/释放、张弛、换气；
- 信息债、悬念、认知变化与 reveal timing；
- 关系推进、人物欲望变化以及读者为什么愿意继续读；
- 跨章、跨卷累积后才出现的效果。

### 默认镜头 B：Reader / Page Craft

优先借鉴 creative-writing-skills 的 Writing Principles / Reader Sim / Craft 观察方法，重点观察但不限于：

- 读者逐时刻的投入、漂移、疑问、预测与认知变化；
- transportation / aesthetic / social simulation / curiosity-prediction / flow 等读者回报通道；
- 人物作为“心智”的可信度：行为、内心、欲望、选择、反应是否让读者能建模；
- POV、叙事距离、声音、语言节奏、句法与意象；
- 对话、潜台词、动作、微动作、感官、心理距离；
- 留白、幽默、暧昧、欲望、尴尬、惊奇等微观体验；
- 多个普通细节组合后产生、单独拆句时看不出的整体效果；
- 一句话、一个动作、一个称呼、一个省略等微观机巧。

### 触发型 Developmental Deep Dive

Base / Discovery 暴露明显高价值问题时，可借鉴 Apodictic 的发展编辑镜头进行专项深挖，例如：

- contract / reader promise；
- Reader Experience；
- Decision Pressure；
- Scene Turn / Scene Function；
- Emotional Craft / Rhythm；
- Reveal Economy；
- Character Architecture；
- POV / Voice / Interiority；
- Theme / controlling idea；
- genre-specific audit。

Apodictic 式镜头用于诊断和发现，不自动覆盖为普遍写作规则；最终仍须回到本作品证据、scope、boundary、counterevidence 与 confidence。

## 工作流（v0.2 vNext 流程）

1. `validate`：校验 SourcePrepare PASS 包（状态、版本、book_id、文件、章节一致性、SHA256、空章节）。
2. 阅读 `chapters/` 原文（逐章阅读，不做抽样猜整书）。
3. `prepare`：生成章节索引 + 每章证据模板（含 MAP 和 OBSERVATION 节）+ 报告骨架 + 初始 manifest。
4. **Base Scan + 多视角 Discovery**：所有关键观察都以原文为一手来源。
   - Base Scan 在 `evidence/ch_NNNN.md` 填写 MAP、FACT / INFERENCE / OBSERVATION / 少量 MECHANISM / BOUNDARY；
   - 至少完成“长篇运行 / 读者动力”与“Reader / Page Craft”两个互补观察 Pass；
   - 同一高价值效果允许跨多个句子、场景和章节聚合证据；
   - 允许记录“重要但暂时难以命名”的 Observation / Inference；
   - 不要求每个 Pass 机械覆盖所有分类，也不把维度数量当成质量指标。
5. `assemble --input <SourcePrepare PASS> --output <BookDistill 输出>`：
   校验条目分类合法性、引用可追溯与**行号不越界**，
   重算输入 snapshot 并比对，计算**维度覆盖统计**，生成 `distill_manifest.json`。
6. `profile --output <BookDistill 输出>`：生成 `book_profile.md`（维度覆盖、强项/潜在强项、不确定项、深挖建议骨架）。
   脚本只做确定性统计；文学价值判断由运行本 Skill 的 Agent 完成。Profile 只能分配深挖预算，不能否定未选维度的潜在价值。
7. `deepdive --output <BookDistill 输出> --dimension <维度名> [--input <SourcePrepare PASS>]`：生成专项深挖模板。
   专项文学分析优先参考 Apodictic / ani-book / creative-writing-skills / oh-story 的分析框架。
   传入 `--input` 时复用 assemble 校验逻辑（引用格式、章节存在性、行号越界）校验已填写的深挖内容；不传 `--input` 时仅生成模板。文件已存在时不覆盖。
8. **BookDistill 总编辑式收敛**：汇总 Base Scan、多视角 Discovery 与 Deep Dive，回原文核证；合并同质观察，识别多个普通细节形成的组合效果；区分 Observation / Inference；降级过度抽象；补充反证、scope、boundary 和 confidence。
9. 跨章收敛机制：从充分支撑的 Observation / MECHANISM 中合并同质、降级单章小技巧，
   产出 `mechanisms.md`（10–20 条高价值机制，不设数量指标）。无法可靠抽象但很有价值的内容继续保留为 Observation / Inference，不强行机制化。
10. 生成 `evidence.md`（精选支撑最终结论的证据）与 `model.md`（作者第一阅读入口）。
11. 完成 `bd_report.md`：来源身份 + 覆盖范围与置信度 + 边界与不确定性 + Discovery / Deep Dive 覆盖状态。
12. `bkp --output <BookDistill 输出> [--prototype <原型目录>]`：BKP Finalize——
    读取 `bkp_prototype/`（人工验证的知识层），校验身份/源指纹、v0.2 cards 的调用字段、
    类型边界、引用可追溯与条目计数后，封装正式 BKP 到 `bkp/`；
    重跑不覆盖被人工修改的 curated 文件（仅告警保留）。
13. 作者审阅产物。

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

## Finalized Settlement（Phase 2B2）

**只在 BKP FINALIZED 且全部验证通过后，对当前作品执行一次 settlement**（收尾动作，不重复执行）：

1. **Mandatory Preflight**（不满足则 STOP，保留现场）：
   - `bkp/identity.json` 的 `schema_status == "FINALIZED"`，且 `bkp/knowledge/cards.md` 存在；
   - 本作品全部验证通过（validate / assemble / bkp 校验无未处理告警）；
   - git `precheck`：`fetch` 成功、`branch == main`、`HEAD == origin/main`、porcelain 空（MaterialIntake `post_action.precheck`）。
2. 执行 settlement：
   - **catalog refresh**：`refresh_and_render()`（`素材资产.json` 的 `knowledge` 自动变为可用，`CSV / MD` 刷新）；
   - **Post-Action git sync**：`post_action.safe_commit_push`，allowlist 见 `scripts/settlement_contract.py`：
     `02_原著蒸馏/<book_id>_<书名>/` 整棵 subtree + `01_原始素材` 三份 material state files；
     commit message 使用 `chore: settle book_<XXXX> <书名>`。
3. **绝不包含**：`01_原始素材` 原著全文（Local Only）、`06_工作区/**`（Local Only）、其他作品目录。
4. settlement 不修改 `book_distill.py` runtime；具体动作由 Agent 按本 SKILL 执行（`settlement_contract.py` 只提供 contract 常量与校验）。

## 范围边界

- 本技能只做 1 部作品的真实蒸馏；批量蒸馏、RAG、知识图谱、多 Agent、复杂长期状态不属于当前版本。
- 脚本不调用大模型；分析内容由运行本 Skill 的 Agent / 作者填写。
- **v0.1 不提供自动 resume**：中断时依赖已有文件人工继续，不实现断点/状态恢复。
- BKP v0.2 只冻结知识卡职责/调用字段/证据边界；`bkp` 子命令只做最小 Finalize
  封装（校验 + 复制白名单知识文件 + 生成 identity.json），不新增 RAG/KG，
  不自动升级知识等级（单书 BKP 最高为 Work-specific Pattern）。
- 逐章 evidence 与 manifest 是 audit appendix / 工作附件；作者核心产物是
  `model.md` / `evidence.md` / `mechanisms.md` / `book_profile.md` / `bd_report.md`。
- 详细的逐章工作底稿优先放 `06_工作区/BookDistill/<book>/`（Local Only），
  不把 `02_原著蒸馏` 默认膨胀成逐章分析数据库。
- 专项深挖的文学分析方法优先参考已有来源（Apodictic / ani-book / creative-writing-skills / oh-story），
  当前只吸收分析框架/方法纪律，不整体复制外部代码或 Prompt。
- 多视角 Discovery 是**方法要求**而不是固定 Skill 数量；不要为了满足本节而制造新的平级 Skill、复杂编排或永久 taxonomy。
- v0.2 不要求重跑或迁移已完成的《一九八四》《三体》：适配器在 cards 缺失时继续加载其 v0.1 split files。
- 方法来源与许可证记录见 `PROVENANCE.md`。
