# Continuity Postmortem｜第三场反向检查（薄层 consumer test）

> 状态：FROZEN（2026-08-16）。在 scene3_W0 冻结诊断与 W1 修订完成后反向判断。
> 结论先行：**structured State（14/30）继续支撑事实与承诺继承；recent prose 第三次提供独立短时连续性；薄层没有引入任何隐藏状态或新权威。**

## 1. structured State 承载了什么（可指认）

| 第三场景中的效果 | 依赖的 State 条目 |
| --- | --- |
| 三天期限兑现（礼拜五→礼拜天时间轴） | event.w2.songning-three-day + thread.songning.three-day-answer |
| 宋乔框架中午前送达 | event.w2.songqiao-framework |
| 宋宁答复的直接对象（明价、三方签、缺一不行） | event.w2.three-party-condition |
| 月底时钟只推进不收口（电话给郑国栋取向） | event.w2.zheng-month-end + thread.zheng.month-end |
| 结尾合同未签、礼拜一未至 | thread.contract.three-party |
| 垫资焦虑建立在旧债信用后果上（冻授信） | canon.seed.debt |
| belief 第三次触碰（"姐姐知道得太多"beat） | char.state.songning.belief |
| 合作机器照旧运转（秀兰盘点单、联运背景） | canon.w1.thirdparties |
| "合作更必要 + 冲突更明显"同时兑现 | rel.state.sisters + plan.design.direction.island |

CONTEXT_MISSING = 0：16 条未选条目事后核对无一应选（附页忠告、盘点单、重算模型、已兑现线等确实未被正文需要）。

## 2. recent prose 承载了什么（State 无法表达）

| 第三场景中的效果 | 只能来自 recent prose |
| --- | --- |
| "接，站能活；不接……"的权衡句式延续与升级 | 是（scene2 结尾句式的回声变奏） |
| 路灯意象的主动拒绝："她没有再去数" | 是（对上一场"数灯"结尾的反向变奏，State 无此信息） |
| "这两个月"从听账落到自己账上的重量递进 | 是（scene2 周昌顺念账期的语气余波） |
| 账/纸/计算器的器物节奏与短句对话 | 主要是 |

判断与前两轮一致：recent prose 承载短时连续性（语气、意象、句式余波），不是事实；窗口（2000 字尾部）恰好覆盖。**维持形态建议：简单 recent-text window，不是全文 RAG。** 薄层已把它实现为 `prepare_recent_prose_window`（自动尾部截取 + 非权威元数据 + writing_hint）。

新观察（结算覆盖遗漏）：“压两个月”账期是 scene2 中 continuity-critical 的 hard anchor，但模型 settlement 时未将其列入 mechanical candidates。该数字不在 State、不在 recent prose 窗口（位于 scene2 前段，超出尾部 2000 字），导致本场 W0 产生数字冲突。根因是 STATE_SETTLEMENT_OMISSION，不是 Context Compiler selection failure，也不是 recent prose 窗口设计缺陷。已在 SKILL.md 补模型侧 hard-anchor 检查纪律（F0-2），防止此类遗漏复现。

## 3. 结算质量反向验证

- 本轮结算首次经薄层 `apply_settlement` 落盘：10 条 mechanical 在第三场全部被正确使用，零事实错误；
- 被薄层门拒收的 7 条（5 ambiguous + 2 creative）在第三场确实未被正文偷用——宋乔垫资条款的动机停在不安（B5/C2 未泄露），宋宁的答复是当场创作而非预写（C1 未泄露）；
- 这第三次支持：三分类纪律 + 机械门是"下一场不偷关 open space"的直接保障。

## 4. W0 问题归因

| 问题 | 归因 |
| --- | --- |
| 末梢账期“四十天”与 scene2“压两个月”冲突（Editor-1） | **STATE_SETTLEMENT_OMISSION**：该数字是 continuity-critical hard anchor（账期/价格），但模型 settlement 时未列入 mechanical candidates；它不在 State、不在 recent prose 窗口，导致 W0 无法获得该事实。这是模型结算覆盖遗漏，不是 runtime gate 失败，也不是 Context Compiler selection failure |
| belief beat 前半句逐字重复 scene2（Character-1） | **OTHER（recent-prose 副作用）**：连续第三次证明强吸收需要自觉变奏；writing_hint 存在但不足以自动消除 |
| 结尾主题双说（Reader-1） | **WRITING_JUDGMENT** |
| 长桌句字面歧义（Editor-2） | **WRITING_JUDGMENT** |

分布：CONTEXT_MISSING 0｜STATE_SETTLEMENT_OMISSION 1（hard-anchor 结算遗漏，非 runtime gate 失败）｜WRITING_JUDGMENT 2｜OTHER 1。

## 5. 薄层自身检查（consumer test 专项）

- 无新 Schema：settlement report / shadow rev4 / brief / context / recent prose window 全部复用既有结构与 validator；
- 无新 authority：shadow 全程 `manual_import:experiment_shadow_from_W2`，由 runtime 铸造，模型无法自选；production 前缀零出现；
- 无隐藏状态：所有产出均为本目录显式 JSON/MD 文件，可逐一审计；
- 冻结子系统零修改，回归 111 全绿；
- `allow_simulation_sources=True` 仅在 compile 时因继承 E2-B simulated planning 而开启，与前两轮同口径（TEST_ONLY）。
