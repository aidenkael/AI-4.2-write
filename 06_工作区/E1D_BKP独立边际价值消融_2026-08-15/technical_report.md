# E1-D｜技术报告

状态：`TECHNICAL_EVIDENCE_ONLY / E1_PASS_NOT_DECLARED`

## 1. HEAD / git status

- 工作区：`E:\AI-Write-e1-storydesign`
- 分支：`feat/e1-storydesign-foundation`
- HEAD：`aeb9f3057146f2e516348d0f41e3f8b101ddea48`
- tracked/staged 修改：当前只看到 E1-B、E1-C、E1-D sandbox 为 untracked；本报告未修改正式代码。最终交付前仍应由主执行者复核一次 `git status`。

## 2. 是否修改正式代码

否。只在 `06_工作区/E1D_BKP独立边际价值消融_2026-08-15/` 写入 disposable、`proposal_noncanonical` 实验工件；未修改 StoryDesign、KnowledgeRetrieve、长期开发手册、正式 Story State，未进入 StoryPlan / Writer。

## 3. 输入 SHA 校验

算法：SHA-256。冻结快照当前实算值与 `input_hashes.json` 一致：

- Seed：`530da5b675f892eeb93cd4611a303c308eaf84ac787edbdffab9979482e490f9`
- Brief：`a5cacde1b7aae5a4a05e772cbf00bfca87431eaff4ac87b0c3f41ea52d60bf1d`
- free_design：`74d717c71ef464ebb4e5b83aab3bdbf0fdb8b440925d50530162ff413f9bd307`
- weakness_diagnosis：`acb4accc595ad2e144ebbd8866ea135df898785e879bdbc48d1165e681e64077`
- C1 唯一额外输入 K016：`f9b7ec3fbd8e0312112ee85fb9469e3804f9f1230194a70e1840f96afe006d97`

C0/C1 的 `run_meta.json` 对四项共同输入记录完全相同；未重新生成第一轮设计，未重新诊断 W1/W2。

## 4. 模型 / 思考等级

- C0：`gpt-5.6-sol / xhigh`
- C1：`gpt-5.6-sol / xhigh`
- 盲评 01：`gpt-5.6-sol / xhigh`
- 盲评 02：`gpt-5.6-sol / xhigh`
- temperature / sampling：当前 Agent runtime 不提供控制或读取能力，已记录为 `UNAVAILABLE`。

## 5. C0 实际运行方式

独立新会话；输入仅为固定 Seed、Brief、free_design、W1/W2 诊断与共同修订合同；不查看任何 BKP/K016，不调用 KnowledgeRetrieve，不查看 C1。模型用自身创作能力完成 1 次定点二次修订。输出 2295 个汉字，SHA-256 为 `b523bb71b52fb1b5384f7736ed9b939ed5898ba845a7e5db94a71ab419284835`。

## 6. C1 实际运行方式

另一独立新会话；共同输入与 C0 完全相同，唯一额外输入为冻结 K016；W2 保持 `NO_USEFUL_BKP`，不重新检索、不加其他卡、不查看 C0。模型判断为 `PARTIAL_USE`，完成 1 次定点二次修订。输出 2424 个汉字，SHA-256 为 `9c59bcc71c68bff0a7a87a389f389b1b6d9fb0819d42872c64e984d3abd47a90`。两版篇幅相差 129 汉字，约 5.6%，信息密度大致可比。

## 7. C1 使用的 K016 完整 provenance

- book_id：`book_0035`
- book_title：`长安十二时辰`
- card_id：`K016`
- title：`行为证据累积人物心智`
- canonical source：`02_原著蒸馏/book_0035_长安十二时辰/bkp/knowledge/cards.md`
- source：`knowledge/cards.md`
- knowledge level：`Work-specific Pattern`
- dimension：`人物心智`
- use stages：`character_design, scene_write, review, revise`
- problem types：`characterization, interiority, social_simulation`
- scale：`cross_scale`
- statement：人物的能力、伦理和欲望通过反复选择与专业动作累积，让读者自行建立心智模型。
- function：减少解释性人物介绍，同时维持复杂角色可理解性。
- conditions：行为在不同压力下保持可辨识逻辑，并允许出现代价或矛盾。
- mechanism：用操作习惯、资源取舍、对弱者/敌人的处理和承担后果的方式反复提供证据。
- effect：读者不是被告知人物是谁，而是逐章更新对其预测。
- scope：张小敬、姚汝能、元载及多名配角。
- boundary：单一漂亮动作不足以证明稳定心智；必须跨情境累积。
- confidence：高。
- evidence：`chapters/0001.md#L399-L429`；`chapters/0006.md#L461-L465`；`chapters/0019.md#L77-L145`。
- E1-C retrieval：rank 4；raw score `0.6093220338983052`；relevance reason 为关键词匹配 7 个、原始得分 0.609。
- E1-D 使用边界：仅作为 W1 的参考/挑战，检查梁秋屏在不同压力下的专业动作、资源取舍与后果承担；不得引入原作人物、情节、限时结构或其他卡；不得把 W2 事实归因给 K016。

## 8. 两组调用次数

- C0：正式修订调用 1 次。
- C1：正式修订调用 1 次。
- 两组均为独立新会话，互相不可见；KnowledgeRetrieve 调用均为 0。

## 9. C0 解决 W1/W2 的方式

- W1：铜铃从错拿菜篮露出并留下车号复查；梅雨改道、倒片机木座暂载、误班少补贴、药品中转与甘驰错误期待形成接力；主轴箱拒载又引出维修费、停驶、接生簿交接延期和母女存款损失。
- W2：区分资产编号、档案交接、补偿冻结、房屋影像复核；补入断电、拆皮带/护罩、链葫芦、矮车、车门宽度、载荷、怕潮、锯口等阻力，并允许追回、正式移交或放弃。

## 10. C1 解决 W1/W2 的方式

- W1：用春季门框拒载/暂存、梅雨倒片机越界失败、秋季主轴箱退回、冬季小碑本人承担，形成跨情境接力；同时部分采用 K016，让梁秋屏的可靠性经专业动作、一次越界、不撒谎、付代价和拒绝复制冒险逐步显现。
- W2：补入资产编号、拆分放油、旧棉被包裹、绳扣固定、链葫芦、滚杠、公交台阶/通道/后轴、影像复核、档案整册交接和本人随车说明。此部分来自强模型一般修订，不归因于 K016。

## 11. 两边共同改善

两版都把 W1 从抽象四变量变成跨趟后果，把 W2 从普通行李变成差异化材料/程序阻力；都保住非圣人梁秋屏、母女发动机、生活细节、偶然碰撞、不整齐关系、失败/放弃与开放终局。共同改善不得计入 BKP 独立贡献。

## 12. 只有 C0 出现或更强的改善

- 更完整保留七人年龄、班次、家庭处境与原稿散点纹理。
- “车号、木座、维修票、迟到交接日期”形成更分散的低强度余波。
- 甘驰收费、谭素珍依赖但拒绝私运等关系更尖、更不对称。
- 主轴箱结局保留更多作者开放选择。

## 13. 只有 C1 出现或更强的改善

- “肯载锯但不让锯口横逃生通道—允许倒片机上车但不谎称编号—小碑本人随车说明”的跨情境职业边界序列。
- 倒片机失败成为后续停开、收入、母女裂缝、药品失约、乘客信任与甘驰退让的共同前史。
- 郭兆云躲避、周行降低信任、甘驰拒绝拆散机器、梁秋屏承认越界等反应更分化。
- 后续场景入口更确定，W1 的因果方向更清楚。

## 14. K016 可明确归因的增益

窄幅增益是：把人物可靠性从解释性标签变成跨压力的专业动作、资源取舍与后果承担，让读者更新对梁秋屏职业伦理的预测。三个直接锚点为：“肯载锯、不肯让新鲜锯口横过逃生通道”“没有把编号说成公交零件”“本人随车、坐在旁边，检查时自己说明来处”。

两位盲评不知道 K016，却都把 Y 在人物、W1、下一场戏和较少模板感上的优势定位到同一组行为前史，构成独立支持。W2 与两版共同因果改善不计入此项。

## 15. K016 的副作用

没有出现明显行为清单化或自然度崩塌；但 C1 的倒片机事件过度高效，可能让群像过度中心化；部分原稿人物刻度被压缩；若继续增加同类卡，专业动作可能滑向显式边界清单。另需在正文中补足梁秋屏为何以十九年经验仍允许高风险机头上车，否则职业可信度会反向下降。

## 16. 两份独立盲评结果

两位评审结论完全同向：人物更活 Y 略胜；W1 Y 更有效；下一场戏 Y；较少策划模板感 Y 略胜；保留原稿优点 X 略胜；只能留一个均选 Y，且均称窄幅选择。共同判断最重要差异为：X 是高密度分散余波网络，Y 是少数已发生且不可撤销的失败选择所形成的行为前史。

## 17. sealed mapping 解盲

- Version X = C0（无 BKP）。
- Version Y = C1（只含 K016）。
- mapping 在盲评前完成；两份 meta 均记录 `mapping_read=false`、`technical_inputs_read=false`。

## 18. 最终证据结论

`BKP_INDEPENDENT_VALUE_SUPPORTED`

限定语：这是单 Seed、每臂一次、同模型盲评的窄证据，只支持 K016 在 W1 人物心智/职业动作累积上的小幅独立价值，不支持“BKP 普遍必需”，不宣布整个 E1 PASS。

## 19. 对 StoryDesign 默认策略的建议

继续保留“BKP 后置、稀疏、问题驱动”，但默认调用门槛应提高：先自由设计、锁诊断，并让强模型判断自身定点修订是否足够；只有卡片能提供可检验、可追溯且非一般性的方法差异时才注入 0–1 张。0 张合法；检索命中不等于使用；不得为展示卡片而增加行为清单或牺牲原稿离心细节。

## 20. sandbox 路径

`E:\AI-Write-e1-storydesign\06_工作区\E1D_BKP独立边际价值消融_2026-08-15\`

## 21. 测试结果

- 主执行者已运行 StoryDesign 既有测试：16/16 通过，`Ran 16 tests ... OK`。
- 主执行者已运行 KnowledgeRetrieve 既有测试：4/4 通过，`Ran 4 tests ... OK`。
- 15 个 E1-D JSON 全部可解析；四项共享输入的实际 SHA、manifest、C0 `run_meta`、C1 `run_meta` 四方一致，K016 的实际 SHA 与 manifest/C1 记录一致。
- C0/C1 各 1 次正式修订、各 0 次 Retrieval；C0 内容无 K016/BKP 痕迹，C1 只使用 K016；盲包技术标签命中 0；sealed mapping 记录 `completed_before_blind_review=true`。

## 22. 是否 commit

否。

## 23. 是否 push

否。

## 24. 是否 merge

否。

## 25. 下一步最小建议

不要进入 StoryPlan / Writer，也不要升级长期手册。先由 ChatGPT 审查本次窄结论；若要提高证据强度，下一步最小实验不是再加卡，而是用另一个 Seed 复现“相同诊断、同一张高度贴合卡、C0/C1 各一次”的严格消融，或在可控 sampling 下做小规模重复，检验 K016 型增益是否跨样本稳定。若不做复现，产品策略应保守维持“需要才用、默认 0–1 张”。

## 成本、耗时与可获得性

- C0/C1、两份盲评各 1 次模型调用，共 4 次正式模型调用；另有本次解盲归因会话。
- token usage、货币成本、模型 latency 均为 `UNAVAILABLE`。
- C1 元数据记录 01:20:09–01:22:18，约 129 秒；C0 无可比时间戳，不能据此声称 C1 更慢或更贵。
- 独立会话虽隔离输出，却带来不可控 sampling 噪声；单样本不能估计方差，这是本结论最主要的实验限制。

## Bug 与边界

- 实验运行记录未报告明确 runtime Bug；没有为实验修改 runtime。
- 所有工件均为 `proposal_noncanonical` / technical evidence；未生成 Decision、Diff、Canon、`approved_plan`、StoryPlan 或 Writer 工件。
