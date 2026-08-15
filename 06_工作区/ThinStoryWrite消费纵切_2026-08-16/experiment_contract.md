# THIN_STORYWRITE_CONSUMER_SLICE 实验合同｜第三场 consumer test

> 状态：FROZEN（2026-08-16）。本实验只在本目录内产生 shadow / test-only 材料。
> 前置：阶段 A 已把 LONGFORM_CONTINUITY_REAL_SLICE ff-only 合入 main（51ea1ac）；
> 阶段 B 已在 `05_Skills与自动化/01_Skills/StoryWrite/` 建立最薄操作层
> （`storywrite_entry.py`，9 新测试 + 111 冻结回归全绿，冻结子系统零修改）。

## 任务性质

用新薄层服务第三场真实纵切，作为该薄层的 consumer test。重点不是再证明
"模型能写 3000 字"，而是验证：

1. 新薄层是否明显减少逐场人工文件拼装；
2. settlement assist 是否保持上一轮的保守分类纪律；
3. State 增长以后 Context 是否仍能发生真实缩减；
4. recent prose 是否继续提供独立价值而不过度复写；
5. 第三场事实/人物/关系/open thread 是否连续；
6. 薄层有没有制造新 Schema、新 authority 漏洞或隐藏状态；
7. 作者侧动作是否仍保持接近：说想写什么 → 读/反馈 → 接受。

## 第三场题目

"宋宁在三天期限内算完末梢账，并给出是否接受三方末梢条件的答复。"

## 作者权威边界（最硬约束）

- 前两场 W1 均为 FROZEN EXPERIMENT DRAFT，没有真实 author acceptance；
- 本场结算仍走 shadow mode：`apply_settlement(mode="shadow",
  shadow_authority="manual_import:experiment_shadow_from_W2")`；
- 禁止 production writeback；禁止 `accepted_text:`；禁止声称作者已接受；
- 本场 W1 同样是 FROZEN EXPERIMENT DRAFT。

## 必须保持开放的 open space（五项）

1. 父亲旧债真正用途；
2. 宋乔十年前离开的完整原因；
3. 宋乔隐藏私人目的；
4. 姐妹最终关系；
5. 物流站最终命运。

## 创作约束

- 宋宁的答复必须推进后续（月底期限、三方合同），但不得替五项 open space 作答；
- 不重复上一场已完成的戏剧动作（不得再来一次"第三方报账并决定"）；
- 本场戏剧动作：宋宁第一次成为"把条件摆上桌面的人"（从算账的人变成报价的人）；
- 合作机器部分运转（联运、秀兰日常单），冲突以利益结构方式加深；
- `char.state.songning.belief` 必须被本场触碰（连续两次第一稿缺席的倾向要正面处理）；
- recent prose 的母题必须变奏，不得逐字复写（上一场教训：守时句逐字重复）。

## 链条

scene2 W1（冻结）→ settlement candidate（模型语义）→ `apply_settlement`（薄层 P0）
→ shadow Story State rev4 → `prepare_creation_brief`（薄层 P1）→ semantic Context
selection → `prepare_context`（薄层 P1，复用 E3-A）→ `prepare_recent_prose_window`
（薄层 P2）→ scene3 W0 → Reader / Character / Continuity / Critic / Editor →
一次 W1 → postmortem。

## BKP

`BKP_POSTHOC_SPARSE_PROBLEM_DRIVEN`：无明确 knowledge need 不调用
KnowledgeRetrieve；不为"第五次验证"强行使用。

## 停止条件

完成 final_report 后停止。不 merge 薄层分支进 main；是否冻结薄封装、继续真实
写作或回改现有子系统，由项目负责人按"最终工作台能力第一、开发者/作者长期负担
第二、子系统工程完整性第三"裁定。
