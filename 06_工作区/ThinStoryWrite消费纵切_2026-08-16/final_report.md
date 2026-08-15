# THIN_STORYWRITE_CONSUMER_SLICE Final Report｜24 问

> 状态：FROZEN（2026-08-16）。三阶段：A 安全收口 LONGFORM → B 最薄 StoryWrite 操作层 → C 第三场 consumer test。
> 总原则：CAPABILITY_FIRST_CONSUMER_DRIVEN（最终工作台能力第一，降低开发者/作者长期负担第二，子系统工程完整性第三）。
> 所有结论基于本分支原始材料、测试输出与 Git 事实；不为已开发的薄层辩护——若证据不支持，结论允许是删除。

## 1. main 最终 SHA

`51ea1ac1bd48eac0fcf717aad7e8389ee6d9b3ad`（docs: close LONGFORM_CONTINUITY_REAL_SLICE）。薄层分支**未合入 main**（按合同由项目负责人裁定）。

## 2. 新实验 branch / SHA

- 分支：`exp/thin-storywrite-consumer-slice`
- commit 1：`3f9c266` feat: add thin StoryWrite operation layer（薄层 + 测试，4 文件）
- commit 2：`4c29dba` experiment: thin StoryWrite entry consumer test with scene 3（14 个实验文件）
- 报告本身随 commit 3 提交（见分支 HEAD）。

## 3. LONGFORM_CONTINUITY_REAL_SLICE 是否安全 ff-only 合入

是。fetch 后核验：origin/main = `516ece8`、分支 = `41fe87e`、ahead 1 / behind 0、merge-base = `516ece8`、正式 source diff = 0；独立 worktree `E:\AI-Write-longform-merge` 中 `git merge --ff-only`（516ece8→41fe87e），无 merge commit；closeout 仅含两份长期文档，push 后验证 `7a18ed3`/`41fe87e` 均为 main ancestor。

## 4. 正式新增/修改了哪些 source 文件

仅新增 4 个文件，全部在 `05_Skills与自动化/01_Skills/StoryWrite/`：
- `storywrite_entry.py`（薄层：apply_settlement / prepare_creation_brief / prepare_context / prepare_recent_prose_window / reject_simulation_impersonation）
- `test_storywrite_entry.py`（9 测试）
- `SKILL.md`、`__init__.py`

main 上另有关闭文档两文件（当前工作索引.md、AI-write_长期开发手册.md）。**冻结子系统文件零改动。**

## 5. 是否新增 Schema

否。Story State 结构、authority 规则、Creation Brief、Context Package、recent prose window 全部复用 E1/E2/E3-A 既有结构与 validator；settlement report 是薄层派生工件，不是 State Schema。

## 6. 是否修改冻结子系统

否。ContextCompiler / StoryPlan / StoryDesign / BookDistill / KnowledgeRetrieve 文件零修改；回归测试 111 全绿（ContextCompiler 34 + StoryPlan 50 + StoryDesign 27）。

## 7. 新薄层到底自动化了哪些机械步骤

- P0：settlement 落盘——mechanical 条目写入、authority 铸造、state_rev 递增、id 查重、三分类门、最终 validate_story_state；
- P1：creation_brief 编译（source_versions 自动对齐）与 Context 编译入口（显式 selection、空 selection 不 fallback、BKP 冻结门）；
- P2：recent prose 尾部窗口截取 + 非权威元数据 + 写作提示。
第二轮的 4 件手工机械工件（shadow state JSON / brief JSON / 一次性编译脚本 / recent prose MD）→ 第三轮 0 件手工。

## 8. 哪些判断仍由模型负责

结算三分类判断、每条 mechanical 的事实与证据、selection 与逐条理由、五立场诊断、正文写作与修订、BKP 需求判断。runtime 不做任何语义判断。

## 9. settlement 的 mechanical / ambiguous / creative gate 是否成立

成立。真实链条：10 mechanical 写入 shadow rev4，5 ambiguous + 2 creative 全部拒收（`settlement_report.json` 可审计）；第三场正文核对：被拒收项无一被偷用。单元测试独立证明 ambiguous/creative 在任何 mode、任何 flag 下都不写入。

## 10. 未 author-accepted 时 production writeback 是否可靠拒绝

可靠。测试 4：`author_accepted=False` → ContractError；空 scene_ref → ContractError；shadow mode 声称 acceptance → ContractError。实验全程只走 shadow（`manual_import:experiment_shadow_from_W2`），三场 W1 均未升级为 accepted_text。

## 11. simulation authority 是否可靠隔离

可靠。测试 5：`author_decision:storydesign-simulated` 类新输入被拒；shadow 不得使用 accepted_text:/author_decision: 前缀；accepted_scene_ref 携带 simulation 标记被拒。历史 `author_decision:storydesign-simulated` 仅作历史证据保留，未回改。

## 12. Context 第三场选中数 / 总数 / 比例

**14 / 30 = 46.7%**（第二轮 13/22 = 59.1%）。State 增长 8 条后，selection 缩减幅度反而更大；编译零错误，status=CURRENT。

## 13. CONTEXT_MISSING 是否仍为 0

是（带限定）。16 条未选条目事后逐条核对，无一应选；第三场事实依赖全部由 14 条选中项覆盖。限定：CONTEXT_MISSING 仅指“已进入 Story State 的条目中，没有应选而漏选的条目”。不得用它推导“整个前文事实没有遗漏”——本场暴露的“两个月账期”数字冲突即属 STATE_SETTLEMENT_OMISSION（该事实根本未进入 State，因此不在 CONTEXT_MISSING 的管辖范围内）。

## 14. recent prose 的收益和副作用

收益：句式回声变奏（“接，站能活”）、路灯意象的主动拒绝（“她没有再去数”）、器物节奏延续、称呼/对话节奏延续。副作用：belief beat 前半句逐字重复 scene2（连续第三次证明强吸收需自觉变奏）。注意：“两个月”账期的重量递进感实际来自 recent prose 的语气吸收，但该数字本身不在窗口内；W0 产生数字冲突的根因是 STATE_SETTLEMENT_OMISSION，不是 recent prose 窗口缺陷。

## 15. 第三场连续性结果

7 项连续性专项全部通过（见 scene3_review.md）：事实继承、戏剧动作不同构、人物声音延续、三天期限兑现、五项 open space 均未偷关、State 无遗漏、recent prose 价值成立。W0 的 4 个问题中 1 项为 STATE_SETTLEMENT_OMISSION（已在 SKILL.md 补 hard-anchor 检查纪律），3 项执行层，一轮 W1 修订全部解决。

## 16. W0 问题分类

CONTEXT_MISSING 0（限定口径：仅指已进入 State 的条目中无应选而漏选）｜STATE_SETTLEMENT_OMISSION 1（“两个月账期”hard-anchor 未进入 mechanical；非 runtime gate 失败）｜WRITING_JUDGMENT 2（主题双说、长桌句歧义）｜OTHER 1（recent-prose 逐字回声）。

## 17. BKP 是否真正需要

不需要。连续第五次 `NO_USEFUL_BKP`（0 调用、0 增益）；检索状态 SKIPPED_NO_KNOWLEDGE_NEED。不为凑验证发起检索。

## 18. 开发者逐场机械负担相比第二轮下降了哪些

合同级机械拼装显著消除（详见 developer_burden_comparison.md）：State JSON / authority / rev / id guard / Brief source_versions / recent prose metadata 均由薄层承担，易错点由有测试的 runtime 保证。Reservation：第三场仍使用一次性 `run_scene3_thin_chain.py`，其中 settlement candidates / semantic brief interpretation / Context selections 均由模型生成。当前证明的是 THIN_STORYWRITE_PRIMITIVES = USEFUL、MECHANICAL_SETTLEMENT_ASSIST = USEFUL；AUTHOR_FACING_ONE_SENTENCE_ENTRY = NOT_YET_PROVEN。

## 19. 有没有出现新的作者操作负担

没有。作者动作仍为三件（说想写什么 / 读正文给反馈 / 明确接受）；薄层未引入任何作者需要理解的新概念。

## 20. THIN_STORYWRITE_ENTRY 是否值得保留

值得。consumer test 即其证明：P0/P1/P2 三个摇柄在第三场全部真实使用，合同级机械拼装显著消除，且未制造新 Schema、新 authority 漏洞或隐藏状态。当前证明 THIN_STORYWRITE_PRIMITIVES = KEEP_AND_FREEZE，不是最终作者 UI/入口。

## 21. MECHANICAL_SETTLEMENT_ASSIST 是否值得保留

值得，且是薄层中价值最高的一项：它消除了两轮证据中增速最高、最易错的场次线性环节（第 N 场需 N-1 次结算），并把三分类纪律从"自觉"升级为"机器门"。

## 22. 是否出现必须回改 Context Compiler / StoryPlan 的真实 blocker

没有。compile_context 对增长后的 shadow State（30 条、含 replace 后的 thread）照常工作；resolve_plan_activity 照常；零回改需求。两个冻结维持：CONTEXT_COMPILER_CONSUMER_DRIVEN_FREEZE、StoryPlan 冻结。

## 23. 当前下一步应该选哪个

**建议：冻结薄封装并转向更多真实写作。**
- 继续薄封装：没有新的重复机械证据（本轮剩余手工全是语义/创作动作），继续封装违反消费者驱动原则；
- 回改现有子系统：无 blocker，无依据；
- DO_NOT_BUILD（删除薄层）：证据明确反对——负担测量显示机械摇柄真实消除；
- 冻结薄封装 + 更多真实写作：薄层已达"最薄"目标，其价值只会在更多真实场次中被验证或证伪；下一批真实写作同时是生产闭环（真实 author acceptance → accepted_text → production State）的候选验证场景。
裁定权在项目负责人；若批准冻结，薄层分支可 ff-only 合入 main。

## 24. 哪个选择最符合三级优先级

第 23 问的建议（冻结薄封装 + 转向更多真实写作）同时满足：最终工作台能力第一（作者三动作 + 后台薄层已经是当前可达的最简工作台形态，继续加代码不增加作者可感知能力）；开发者/作者长期负担第二（机械摇柄已消除，继续开发反而增加维护面）；子系统工程完整性第三（冻结子系统全部保持原样，回归全绿）。

---

## Reservations（必须保留）

- 三场 W1 均为 FROZEN EXPERIMENT DRAFT，没有真实 author acceptance；
- `accepted_text → production Story State` 的真实闭环仍未验证（production writeback 路径只有测试覆盖，没有真实消费）；
- 当前结果证明的是：跨场景 shadow continuity + 薄操作层可行性，不得写成生产闭环已完成；
- belief 条目连续三次需要约束才触碰、recent-prose 逐字回声连续三次出现——均为 WRITING_JUDGMENT 层稳定倾向，薄层不解决、也不必解决。
