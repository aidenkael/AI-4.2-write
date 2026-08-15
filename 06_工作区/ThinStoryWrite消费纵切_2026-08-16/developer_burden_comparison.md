# Developer Burden Comparison｜第三轮测量（薄层引入前 vs 引入后）

> 状态：FROZEN（2026-08-16）。
> 判定：**薄层消除了第二轮记录的全部四项重复机械摇柄；剩余手工动作全部是语义判断（本来就该由模型/人做）。作者侧零新增负担。**

## 1. 逐环节对比（第二轮手工 vs 第三轮薄层）

| 环节 | 第二轮（LONGFORM，纯手工） | 第三轮（本轮，薄层） | 变化 |
| --- | --- | --- | --- |
| State settlement 落盘 | 手工构造 shadow_story_state.json 全文（145 行）：逐条写条目、保 authority 合规、算 state_rev、查重 id，最易错 | 模型只给 settlement candidates（语义）；`apply_settlement` 自动生成 rev4 JSON + report，authority 由 runtime 铸造，rev/id/分类门机器保证 | **机械摇柄消除** |
| Brief 编译 | 手写 creation_brief.json 全字段（source_versions 手工对齐） | `prepare_creation_brief` 一行调用，source_versions 由 E1 合同自动铸造 | **机械摇柄消除** |
| Context 编译 | 手写一次性脚本 ~108 行（携带合同知识：校验、size_summary、gate） | run 脚本只写语义输入（SETTLEMENT + SELECTIONS）；合同全部在 `prepare_context` 内，脚本零合同逻辑 | **机械摇柄消除** |
| recent prose 窗口 | 手工截取 W1 末段 ~1400 字 + 手写权威定位元数据 MD | `prepare_recent_prose_window` 自动尾部截取 + 非权威元数据 + writing_hint | **机械摇柄消除** |
| settlement 分类判断 | 模型语义 | 模型语义（不变） | 语义，保留 |
| selection 理由 | 模型语义 | 模型语义（不变） | 语义，保留 |
| W0 / 五立场 / W1 | 创作与诊断核心 | 不变 | 创作，保留 |
| 归档 | postmortem / report | 不变 | 归档，保留 |

## 2. 量化

- 合同级机械拼装显著消除：State JSON / authority / rev / id guard / Brief source_versions / recent prose metadata 均由薄层承担。第二轮的 4 件手工机械工件（shadow state JSON / brief JSON / 一次性编译脚本 / recent prose MD）在第三轮均通过一次 `run_scene3_thin_chain.py` 运行生成，合同逻辑全部在薄层内。
- 易错点结构性消失：authority 拼写、state_rev 计算、id 查重、source_versions 对齐、窗口元数据——全部由有测试的 runtime 承担（10 新测试锁定，含 F0-1 no-op rev 测试）。
- Reservation：第三场仍使用一次性 `run_scene3_thin_chain.py`，其中 settlement candidates / semantic brief interpretation / Context selections 均由模型生成。当前证明的是 **THIN_STORYWRITE_PRIMITIVES = USEFUL、MECHANICAL_SETTLEMENT_ASSIST = USEFUL；AUTHOR_FACING_ONE_SENTENCE_ENTRY = NOT_YET_PROVEN**。不得因此继续开发作者入口；形态等真实写作 consumer 再暴露。

## 3. 作者侧

作者动作仍为三件：说想写什么 → 读正文 / 给反馈 → 明确接受正文。薄层没有引入任何需要作者理解的新概念（state id / authority / selection 仍全部在后台）。

## 4. 对开发决策的输入

- `MECHANICAL_SETTLEMENT_ASSIST`：consumer test 通过，消除最重最易错环节，建议保留；
- `THIN_STORYWRITE_ENTRY` 整体：consumer test 通过（P0/P1/P2 三个摇柄全部真实使用），建议保留；
- 没有暴露新的重复机械缺口：本轮剩余手工全部是语义/创作动作，不构成下一个 BUILD 证据；
- 新观察（非负担）：窗口盲区导致一次账期数字冲突，解法是结算纪律（数字进 State）而非新开发。
