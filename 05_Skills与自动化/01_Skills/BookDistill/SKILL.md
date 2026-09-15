# BookDistill —— 原著蒸馏纪律工作台（runtime 0.5.0）

## 定位

C19（原著蒸馏 / 能力发现）的最小可运行实现，当前属于能力地图方法论层（M4）。
runtime 0.5.0 在既有结构语义门上增加**可恢复的全书真实遍历**（reading manifest +
ledger + batch 循环）与**确定性 completion receipt**；whole-book 阅读完成度的权威
是当前 source-bound manifest/ledger + ordered continuity state + 确定性 acceptance，不再是 Agent 自报的
`scan_refs`。BKP 包协议版本仍按其独立合同管理。
目标是：对 SourcePrepare PASS 的真实作品，产出**可追溯、分类清晰、边界明示、全维度覆盖**的蒸馏证据，
供作者审阅并沉淀可迁移写作机制。不是剧情复述，不是风格模仿器，不是批量蒸馏流水线。

## 长篇执行合同（根不变量）

- 作者仍只点一次“原著学习”，仍只在同一个 Qoder Agent 窗口发送一次 `/gowrite`；
  BookDistill 内部把完整来源拆成有界批次，长期状态只依赖磁盘工件，聊天上下文可自然压缩。
- **并行 Reader 执行架构（当前合同）**：`book_distill_propose` 的 `/gowrite` 由 parent/main
  Agent **亲自执行** canonical 编排（不再把整本书包给单个 general-purpose 子 Agent 串行读完）。
  Main = coordinator/editor；通过 Qoder `subagent_type=gowrite-bookdistill-reader`（项目级
  Custom Agent，定义在仓库 `.qoder/agents/gowrite-bookdistill-reader.md`）分派**单批次 Reader**。
  该 Custom Agent 的 frontmatter **故意省略 `model` 字段**：Qoder CN CLI 1.1.52 在真实
  spawn 时继承 parent/main 当前会话模型；不得写 `model: inherit`（运行时可能把它当成真实
  model id 并报 40506），也不得硬编码 Qwen/DeepSeek model id。
  每个 Reader 严格只读一个 batch、六域 checked、写唯一 temp note 后经确定性 `note-publish`
  校验并**原子发布** canonical note；Reader 绝不 `reading-commit`/收敛/生成卡/再分派子 Agent。
- **Ordered continuity spine**：Main 同时启动恰好一个
  `subagent_type=gowrite-bookdistill-continuity` worker。它使用同一 Qoder runtime，
  占用同一共享 Reader Pool 的 1 个 lease，严格按 manifest 顺序读原著，每批原子
  持久化自然语言 `experience_update + rolling_state`。它不读 BookProfile、并行
  batch notes、convergence 或未来 batch，不重复六域局部分析，不自动产生
  Mechanism/BKP。这条 spine 与 local Readers **同时**运行，不是后置串行二次蒸馏。
- **共享 Reader 池（全局上限 16）**：所有并发 BookDistill 共用一个 file-based + atomic +
  Windows-safe + Local Only 的租约池（`06_工作区/BookDistill/.reader_pool`），应用级全局上限
  `BOOKDISTILL_GLOBAL_READER_LIMIT=16`；同一时间所有书合计 active Reader ≤16。调度是**动态补位**
  （acquire lease → 1 Reader/1 batch → 验证/发布 note → Main 串行 commit → release → 立即补位），
  不做固定 wave barrier。池**不建** DB/daemon/service/event bus/第二 Agent runtime/SDK/worktree。
  本机 Qoder CN 1.1.52 默认 concurrent subagent limit=20 是 runtime evidence，不是永久产品 invariant。
- 不要求 Agent 自动开新窗口/新会话，不增加作者步骤。
- Observer 是**独立分析视角**，不因此要求每个视角各自全文扫描；
  continuity spine 是为保留首读时序而必须直读原著的有界顺序 pass，需要反证/边界/疑难判断时再定向回读原文。
- Agent 自报 `scan_refs`/coverage/`identity PASS` 不能单独证明完成；whole-book completion
  的权威是当前 source-bound reading manifest/ledger + ordered continuity state + 确定性 acceptance。
- **恢复以磁盘为 authority**：reload manifest/ledger/continuity state；pending batch 若已有合法 canonical note
  直接串行 commit 不重读；incomplete temp note 丢弃后只重读该 batch；completed batch 永不重派；
  派发前安全 reconcile 本 request 的 Reader leases。bridge claim 保持 fail-closed（24h running
  hard-stale），正式恢复 = 恢复同一 Qoder main session 后从磁盘继续，绝不制造双 runner。
- Qoder response 丢失时可由合法 deterministic completion receipt 恢复结算，但绝不从
  Agent 自报 PASS 推断成功；backend finalize 仍独立重跑全部确定性门。

## 输入契约（SourcePrepare PASS 包）

目录：`06_工作区/SourcePrepare/<book_id>_<书名>/`

必须存在且校验通过：

- `metadata.json`：`status == "PASS"`、当前 `skill_version == 0.4.0`、`book_id`、`selected_source.sha256`、`unit_semantics`、`unit_boundary_source`
- `full.md`、`conversion_report.md`
- `chapters/NNNN.md`：正文章节（`0000_*.md` 视为卷首前置，不参与正文蒸馏）
- 磁盘正文章节数（仅 `NNNN.md`）与 `metadata.chapter_files` **精确相等**；
  `0000_前置内容.md` 不计入正文计数，任何 ±1 一律 FAIL（防止实际缺章被静默放过）
- 输入目录名必须形如 `<book_id>_<书名>`，前缀与 `metadata.book_id` 精确一致
- 旧版或缺少结构语义的 Prepare 一律 fail closed，不得以 warning 继续。`chapter` 按真实章扫描；`reading_unit` 可处理，但索引/报告/任务必须明示其语义。

BookDistill 不读取 `01_原始素材` 作为正文输入；不修改 SourcePrepare 输出。

## 输出契约

目录：`02_素材知识库/<book_id>_<书名>/`

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
| `bkp/` | BKP v0.2 正式知识包：`knowledge/cards.md` 为 canonical 知识层，`author_view.md` 为非权威八区投影；`knowledge/supporting.md`（v0.5）为非默认检索层的来源绑定 supporting findings；旧 v0.1 split files 仍可读取，依据 `BKP_protocol.md`。 |

### 过程工件（仅 06_工作区，绝不进入 02）

蒸馏过程在 `06_工作区/BookDistill/<request_id>_<书名>/` staging 内进行，以下过程工件
**绝不进入正式 02**（发布时由显式 allowlist projection 排除）：

- `_work/reading_manifest.json`：run-bound 阅读计划（绑定 request/run/source snapshot/
  章节内容指纹；全部 span 无遗漏/无重叠/顺序稳定）；
- `_work/reading_ledger.json`：逐批 pending/completed 状态（原子/幂等；可 resume）；
- `_work/batch_notes/B####.md`：每批直接阅读笔记（六域 checked + 来源绑定 findings）；
- `_work/reader_continuity/state.json`：严格按 batch 前缀推进的连续首读状态（身份/位置/hash +
  自然语言阅读体验变化与 rolling state）；
- `_work/completion_receipt.json`：确定性完成回执（仅 local ledger 与 continuity 完整 + acceptance PASS 后写）；
- `discovery/`、`evidence/ch_*.md`、`bkp_prototype/`、临时脚本：raw/调试产物。

正式发布只把 allowlist 正式产物投影到 `02_素材知识库/<book_id>_<书名>/`。

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
5. **coverage 明示（权威 = local ledger + continuity state）**：whole-book 阅读完成度的权威是当前
   source-bound reading manifest/ledger 与 ordered continuity state：每个 manifest batch 必须有 completed 记录与有效
   batch note（六域 checked）。`scan_refs` 仅保留为调试信号，**绝不再作为 whole-book
   reading completion 的权威证据**；仅填写全范围 `scan_refs`（如 `L1-LN`）、仅有完整行号
   范围、仅有 Agent 自报“已读”都必须失败。允许“已检查但无高价值发现”，coverage 不要求固定 evidence/知识数。
6. **confidence 标记**：每条条目标记置信度 高/中/低。
7. **counterevidence / boundary**：BOUNDARY 不省略；反证、译本影响、样本局限必须记录。
8. **不大量复制原文**：条目为一句话结论 + 行号引用，不摘抄大段原文。
9. **可迁移机制，不做剧情换皮**：MECHANISM 必须说明“为何可迁移”（从具体文本抽象技法），禁止“某角色做了某事所以这样写”式的剧情复述。
10. **不随意外推**：局部样本只标记为局部证据，不宣称覆盖整书或整个类型。
11. **coverage 不是价值判断**：维度覆盖统计只是 BookProfile 的辅助信号，禁止“Observation 数量多 = 更重要”这类机械判断。
12. **不做原作者风格模仿器**：产出是分析性证据，不是模仿奥威尔文风的仿写样本。
13. **重要发现可跨尺度、跨位置聚合**：一条高价值 Observation / Pattern 可以由多个不相邻句子、场景或章节共同支撑；不得为了“一条结论只配一个局部证据”而拆散真实效果链。
14. **保留未命名价值**：发现“重要但暂时难以命名”的创作智慧时，允许先以 Observation / Inference 保存，不得因为暂时不属于现有 taxonomy 而丢弃。
15. **报告统计单一真源**：`bd_report.md` 的条目/分类/单元语义/覆盖门统计由最终 `distill_manifest.json` 重建，acceptance 前必须一致。

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

## 工作流（v0.5 可恢复全书真实遍历）

1. `validate`：校验 SourcePrepare PASS 包（状态、版本、book_id、文件、章节一致性、SHA256、空章节）。
2. `prepare --input <SP> --output <staging> [--request-id <id>] [--run-id <id>]`：生成章节索引 +
   每章证据模板 + 报告骨架 + 初始 manifest，并生成确定性 **reading manifest + ledger**
   （`_work/`）：把冻结来源拆成无遗漏/无重叠/顺序稳定的 span，按保守内部上限聚合为有界 batch。
3. **并行局部阅读 + ordered continuity spine**（动态补位，不做固定 wave barrier）。
   Main 保持两条路径同时前进，直到 local ledger 全部 completed 且 continuity state complete：
   - 恢复准备：`reading-status` reload 进度；`reader-reconcile --output <staging>` 安全释放本 request
     遗留的 Reader 租约；completed batch 永不重派；已发布未 commit 的 canonical note 直接串行 commit。
   - `continuity-start --output <staging> --input <SP>`：先占用同一全局池的 1 个槽，
     Main 以 `subagent_type=gowrite-bookdistill-continuity` 启动唯一 worker。worker 循环调用
     `continuity-next`，每次只收到旧 rolling state 与下一个原著 batch，写 candidate 后调用
     `continuity-commit` 原子推进。该 worker 与下面 local Readers 并行；完成后 Main 用
     `reader-release` 释放其 lease。若一次 invocation 因 turn/context 上限只读完了严格前缀，
     必须在已 commit 边界退出；Main 确认它结束后只释放该 lease，再启动下一个 invocation
     从磁盘 source position 续读。任何时刻只有一个 continuity worker，正常更换时不得用
     request-wide reconcile 误释放正在工作的 local Reader leases。
   - `reader-dispatch --output <staging> --input <SP>`：原子占用一个全局 Reader 租约并返回下一个待读
     batch（含 span/原文行范围/`temp_note_path`/`note_template`/`note_publish_command`/`lease_token`）；
     `pool_full=true` 表示池已满（16），先处理已完成 Reader 再补位；`commit_ready` 列出已有合法
     canonical note 的 pending batch（直接串行 commit，不重读）。
   - Main 用 Agent 工具以 `subagent_type=gowrite-bookdistill-reader` 启动**一个** Reader；该项目级
     Custom Agent 省略 `model` frontmatter，真实 spawn 会继承 Main 当前模型。只交给它这一个
     batch 的分派载荷。Reader **直接阅读该 batch 全部 span 的完整原文**（不抽样、不只读首部、不伪造
     scan_refs），做本批能够自洽支撑的局部叙事、reader dynamics 与 page craft 深读；
     它不得声称已维护跨批 question/prediction/人物与关系心智模型，这些属于 continuity spine。
     Reader 写唯一 temp note（**六域 checked**：故事与大纲 /
     人物与关系 / 章节与场景 / 冲突与节奏 / 世界与题材 / 语言与读者体验，每域 `0 findings` 合法、
     “未检查”不合法；来源绑定 findings 证据必须落在本批 span），再运行 `note-publish --output <staging>
     --batch <id> --temp <temp_note> --lease <token>`：确定性校验（六域/绑定字段/finding_count/span refs）
     后**原子发布** `_work/batch_notes/B####.md`。
   - Main 复核 canonical note，**按 manifest 顺序串行** `reading-commit --output <staging> --batch <id>`
     （原子/幂等标记 completed，绑定 batch id/manifest hash/source fingerprint/note sha256）；只有 Main
     可 commit。commit 后 `reader-release --lease <token>` 释放租约，立即 `reader-dispatch` 补下一个。
   - 期间持续维护 `_work/convergence_state.md`（滚动收敛状态，过程工件，绝不进入 02）：processed batch
     ids / mechanism clusters / accumulated evidence / conflicts / scope-boundary / unresolved questions /
     canonical+supporting candidates。**优先保持 Reader 满载，绝不让收敛把并行阅读重新串行化。**
4. `reading-validate --input <SP> --output <staging>`：机械证明 manifest 覆盖完整来源范围、ledger 与当前
   request/run/manifest hash/source fingerprint 一致、每 batch 有 completed 记录与有效 note，
   且 continuity state 以同一身份完整推进到 manifest 末尾。
5. `assemble --input <SourcePrepare PASS> --output <BookDistill 输出>`：
   校验条目分类合法性、引用可追溯与**行号不越界**，
   重算输入 snapshot 并比对，计算**维度覆盖统计**，生成 `distill_manifest.json`。
6. `profile --output <BookDistill 输出>`：生成 `book_profile.md`（维度覆盖、强项/潜在强项、不确定项、深挖建议骨架）。
   脚本只做确定性统计；文学价值判断由运行本 Skill 的 Agent 完成。Profile 只能分配深挖预算，不能否定未选维度的潜在价值。
7. `deepdive --output <BookDistill 输出> --dimension <维度名> [--input <SourcePrepare PASS>]`：生成专项深挖模板。
   专项文学分析优先参考 Apodictic / ani-book / creative-writing-skills / oh-story 的分析框架。
   传入 `--input` 时复用 assemble 校验逻辑（引用格式、章节存在性、行号越界）校验已填写的深挖内容；不传 `--input` 时仅生成模板。文件已存在时不覆盖。
8. **BookDistill 总编辑式收敛**：汇总逐批 local batch note、continuity history/rolling state 与 Deep Dive，回原文核证；合并同质观察，识别多个普通细节形成的组合效果；区分 Observation / Inference；降级过度抽象；补充反证、scope、boundary 和 confidence。continuity 是 discovery/observer input，不自动成为 Mechanism/BKP。
9. 跨章收敛机制：从充分支撑的 Observation / MECHANISM 中合并同质、降级单章小技巧，
   产出 `mechanisms.md`。**最终知识数量由来源决定，不设 10–20、20–40 等任何配额。**
   归并只在 conditions / mechanism / scale / effect 四者语义实质等价时进行，绝不按文字相似去重；
   归并后保留全部来源 evidence 与 `merged_from` 关系，不丢失 scope/boundary/counterevidence；无法确认等价时宁可分开。
   全面阅读产生、但尚不足以晋升 canonical card 的来源绑定 finding 存入 `bkp/knowledge/supporting.md`
   （非默认检索层），保留来源证据，绝不删除。无法可靠抽象但很有价值的内容继续保留为 Observation / Inference。
10. 生成 `evidence.md`（精选支撑最终结论的证据）与 `model.md`（作者第一阅读入口）。
11. 完成 `bd_report.md`：来源身份 + 覆盖范围与置信度 + 边界与不确定性 + Discovery / Deep Dive 覆盖状态。
12. `bkp --output <BookDistill 输出> [--prototype <原型目录>]`：BKP Finalize——
    读取 `bkp_prototype/`（人工验证的知识层），校验身份/源指纹、v0.2 cards 的调用字段、
    类型边界、引用可追溯与条目计数后，封装正式 BKP 到 `bkp/`；
    重跑不覆盖被人工修改的 curated 文件（仅告警保留）。
13. **全书综合验收（新协议必过门；旧版 v0.1/v0.2 BKP 不追溯）**：在声明 BKP 可检索之前，
    对全部章节 discovery 证据 + `model.md` + `mechanisms.md` + `book_profile.md` + 实际做过的
    Deep Dive + `bkp/knowledge/cards.md` 执行一次显式全书综合审计，回答：
    哪些作品级/弧级/跨尺度机制实质解释了这本书？它们对 story_design / longform_plan /
    chapter_plan / scene_write / review / revise 哪些调用有用？每条重要的、有证据支持的发现是否成为
    canonical 卡？若没有，是否因过局部/过弱/冗余/未证实/不可复用而显式排除？
    不设固定卡数或固定类型维度；实际作品决定相关性。审计结果写入资产根目录的
    `BKP_ACCEPTANCE_REPORT.md`（含结构化 `acceptance_data` JSON 块，字段合同见 `BKP_protocol.md` §5），
    然后运行 `python scripts/acceptance_gate.py <asset_dir> --write-identity`：
    全部机械校验通过且状态为 PASS 时才会把 `acceptance` 块写入 `bkp/identity.json`；
    REVIEW 或校验失败的包不可被 KnowledgeRetrieve 检索。
14. 作者审阅产物。

## 运行方式

```powershell
python scripts/book_distill.py validate --input "06_工作区/SourcePrepare/<book_id>_<书名>"
python scripts/book_distill.py prepare  --input "06_工作区/SourcePrepare/<book_id>_<书名>" --output "06_工作区/BookDistill/<request_id>_<book_id>_<书名>" --request-id <request_id>
python scripts/book_distill.py reading-status  --output "<staging>"
# 并行 Reader 编排（Main 调用；reader-dispatch 会原子占用一个全局 Reader 租约）
python scripts/book_distill.py reader-reconcile --output "<staging>"            # 恢复：释放本 request 遗留租约
python scripts/book_distill.py continuity-start --output "<staging>" --input "<SP>"  # Main：占一个共享槽启动顺序 worker
python scripts/book_distill.py continuity-next --output "<staging>" --input "<SP>" --lease <token>  # worker：旧 state + 下一批原文
python scripts/book_distill.py continuity-commit --output "<staging>" --batch B0001 --candidate "<candidate>" --lease <token>  # worker：原子推进
python scripts/book_distill.py reader-dispatch  --output "<staging>" --input "<SP>"  # 取下一个待读 batch + 租约
python scripts/book_distill.py note-publish     --output "<staging>" --batch B0001 --temp "<temp_note>" --lease <token>  # Reader：校验+原子发布
python scripts/book_distill.py reading-commit   --output "<staging>" --batch B0001   # Main：按 manifest 顺序串行提交
python scripts/book_distill.py reader-release   --lease <token>                    # Main：commit 后释放租约
python scripts/book_distill.py reader-status                                        # 共享池活跃租约/计数
python scripts/book_distill.py reading-next    --output "<staging>"   # 单批次检视（不参与并行租约）
python scripts/book_distill.py reading-validate --input "06_工作区/SourcePrepare/<book_id>_<书名>" --output "<staging>"
python scripts/book_distill.py assemble --input "06_工作区/SourcePrepare/<book_id>_<书名>" --output "<staging>"
python scripts/book_distill.py profile  --output "<staging>"
python scripts/book_distill.py deepdive --output "<staging>" --dimension "人物" --input "06_工作区/SourcePrepare/<book_id>_<书名>"
python scripts/book_distill.py bkp      --output "<staging>"  # 默认读取 <staging>/bkp_prototype
python scripts/acceptance_gate.py "<staging>" --repo-root <repo> --write-identity  # 全书验收门 + 写 completion receipt
```

测试：

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

## Finalized Settlement（Phase 2B2 / 2B2.1）

**只在 BKP FINALIZED、全部验证通过且全书验收门为 PASS 后，对当前作品执行一次 settlement**（收尾动作，不重复执行）：

1. **Mandatory Preflight**（不满足则 STOP，保留现场）：
   - `bkp/identity.json` 的 `schema_status == "FINALIZED"`，且 `bkp/knowledge/cards.md` 存在；
   - 新协议包必须已有 `acceptance.status == "PASS"`（`acceptance_gate.py` 校验通过后写入）；
   - 本作品全部验证通过（validate / assemble / bkp 校验无未处理告警）；
   - git `precheck`：`fetch` 成功、`branch == main`、`HEAD == origin/main`、porcelain 空（MaterialIntake `post_action.precheck`）。
2. 执行 settlement：
   - **catalog refresh**：`refresh_and_render()`（`素材资产.json` 的 `knowledge` 自动变为可用，`CSV / MD` 刷新）；
   - **动态 allowlist（Phase 2B2.1，BD_SETTLEMENT_CURRENT_BOOK_ONLY）**：`scripts/settlement_contract.py` 的
     `build_settlement_allowlist(book_id, work_name)` / `build_settlement_allowlist_from_dir(distill_rel)` 按当前作品构建：
     当前 book_id 的**单一** distillation subtree（`02_素材知识库/<book_id>_<书名>/`）+ 三份 material state files；
     `02_素材知识库/` 整目录授权已废止；sibling（book_0002_Beta）与伪造前缀（book_00010_Fake）一律拒绝；
     commit message 使用 `chore: settle book_<XXXX> <书名>`。
3. **绝不包含**：`01_原始素材` 原著全文（Local Only）、`06_工作区/**`（Local Only）、其他作品目录（含 sibling）。
4. settlement 不修改 `book_distill.py` runtime；具体动作由 Agent 按本 SKILL 执行（`settlement_contract.py` 只提供 contract 常量与校验）。

## 范围边界

- 本技能只做 1 部作品的真实蒸馏；批量蒸馏、RAG、知识图谱、**通用多 Agent 编排框架**、复杂长期状态不属于当前版本。本版本的并行 Reader 是受限的、单本书内的 Main + 单批次 local Readers + 一个 ordered continuity worker 编排（全部共用租约池，全局上限 16），不是通用 multi-agent 框架，也不是第二 Agent runtime。
- 脚本不调用大模型；分析内容由运行本 Skill 的 Agent / 作者填写。
- **磁盘 resume + 并行恢复**：reading manifest/ledger/canonical batch notes/continuity state/leases 落盘；中断/上下文压缩/重新继续同一请求时以磁盘为 authority 恢复（pending batch 有合法 canonical note 直接串行 commit、incomplete temp note 只重读该 batch、completed local batch 永不重派；continuity 从最后原子提交的 source position 继续；派发前 reconcile 本 request 租约）；长期状态绝不依赖聊天窗口记忆。
- BKP v0.2 只冻结知识卡职责/调用字段/证据边界；`bkp` 子命令只做最小 Finalize
  封装（校验 + 复制白名单知识文件 + 生成 identity.json），不新增 RAG/KG，
  不自动升级知识等级（单书 BKP 最高为 Work-specific Pattern）。
- 逐章 evidence 与 manifest 是 audit appendix / 工作附件；作者核心产物是
  `model.md` / `evidence.md` / `mechanisms.md` / `book_profile.md` / `bd_report.md`。
- 详细的逐章工作底稿优先放 `06_工作区/BookDistill/<book>/`（Local Only），
  不把 `02_素材知识库` 默认膨胀成逐章分析数据库。
- 专项深挖的文学分析方法优先参考已有来源（Apodictic / ani-book / creative-writing-skills / oh-story），
  当前只吸收分析框架/方法纪律，不整体复制外部代码或 Prompt。
- 多视角 Discovery 是**方法要求**而不是固定 Skill 数量；不要为了满足本节而制造新的平级 Skill、复杂编排或永久 taxonomy。
- v0.2 不要求重跑或迁移已完成的《一九八四》《三体》：适配器在 cards 缺失时继续加载其 v0.1 split files。
- 方法来源与许可证记录见 `PROVENANCE.md`。
