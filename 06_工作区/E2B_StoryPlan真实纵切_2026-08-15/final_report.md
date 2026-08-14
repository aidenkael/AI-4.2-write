# E2-B｜StoryPlan 真实长篇规划纵切最终报告

> 状态：`E2B_VERTICAL_SLICE_PASS`
> 审查者：ChatGPT / GPT-5.6 Sol
> 证据基线：冻结种子、P0_FREE_PLAN、P0 诊断、正式 KnowledgeRetrieve、Retrieval 使用决定、Local Relationship Scope、Deliberate Ambiguity 审计、simulated Decision/Writeback 机械验证。
> 本实验未修改 StoryPlan / StoryDesign runtime，未 merge main，未开始 E2-C。

## 总结

E2-B 证明了 StoryPlan v0 在一个真实长篇规划纵切中可以完成以下工作：

- 强模型在 0 BKP 条件下，从 Author Intent + Story State + 已确认 StoryDesign direction 形成可继续写作的前半程规划；
- 规划可以保留作者故意未决定的过去真相与最终关系，不因结构完整性而偷写成 Canon；
- 规划问题可以缩小到 relationship scope，而不需要重算整本书；
- 正式 Retrieval 即使 status=OK，也允许因无独立增益而采用 0 张 BKP；
- noncanonical Candidate → simulated Decision → Planning Diff → apply_diff 的权限链在真实规划内容下保持 Canon 零污染。

E2-B 不证明 StoryPlan 已经解决所有长篇规划问题。P0 暴露了轻度“策划委员会感”（W1），并暴露父亲旧债在第一版中仍可从商业主线拆除（W2）。Local relationship scope 表明 W2 可以通过更聚焦的规划任务转化为“当前责任分配与关系判断”的持续变量，但这不是严格 C0/C1，因此不能据此宣称基础模型优于 BKP。

## 八项判断

### A. CONTRACT_RUNTIME = PASS

Plan Brief / Context 在 `intent_rev=1`、`state_rev=1` 下建立；0 knowledge need 时正式走 `SKIPPED_NO_KNOWLEDGE_NEED`，0 BKP 合法。真实 P0 后建立 noncanonical Candidate，Decision/Brief/revision/id 等确定性边界继续成立，未发现 runtime blocker。

### B. FREE_PLAN_QUALITY = PASS_WITH_RESERVATIONS

P0 已具备真实可用的前半程长篇规划质量：地方物流生态变化持续进入人物选择；姐妹合作越成功，利益冲突越具体；前半程终点由宋宁主动签“共同保量”承诺造成真实、难撤销的利益伤害，而非事故、误会或阴谋。

保留两项真实弱点：

- W1：推进过于整齐，存在轻度 committee/template feel；
- W2：父亲旧债在 P0 中仍偏附加压力，尚未完全成为关系发动机。

这两项不足以要求推倒 StoryPlan Foundation，但应继续作为后续真实规划的观察项。

### C. DELIBERATE_AMBIGUITY = PASS

五项 deliberate open space 在 P0 与 local scope 中均保持 `PRESERVED_OPEN`：债务用途、姐姐离开完整原因、姐姐私人目的、姐妹最终关系、物流站最终去留均未被确定。允许存在 `HYPOTHESIS_ONLY` 机制，但没有 `ILLEGALLY_FIXED`。

### D. LONG_FORM_ENGINE = PASS

长篇发动机不是“不断来更大的事故”，而是两套生存体系同时具有合理性、互相需要又逐渐排斥。旧路关闭、客户货量、末端关系、标准化运力、融资与竞标共同制造持续选择压力。第一次不可逆利益伤害后仍存在后续动力，因此前半程不是一次性冲突。

### E. BKP_POSTHOC_POLICY = PASS

执行顺序符合冻结策略：先 0 BKP 得到 P0 → 诊断真实 W1/W2 → 选择 W2 → 正式 Retrieval → 判断候选是否有独立增益。

正式 Retrieval 返回 15 个候选、status=OK，但没有因“召回成功”强制选卡，最终采用 0 张。该结果直接支持 `BKP_POSTHOC_SPARSE_PROBLEM_DRIVEN`。

### F. BKP_INDEPENDENT_VALUE = NO_USEFUL_BKP_AVAILABLE

本案例没有进行 C0/C1 与盲评，因为正式候选没有一张真正改变 W2 的修订方法。最接近的 P18/D6“选择—代价循环”只强化 P0 已有的选择/后果机制，不能解决“未解过去如何持续改变今天的责任分配与关系判断”。

因此不能得出 `SUPPORTED` 或 `NOT_SUPPORTED`；正确结果是 `NO_USEFUL_BKP_AVAILABLE`。这不是 E2-B 失败，也不应伪造对照实验。

### G. LOCAL_SCOPE = PASS

只给出“姐妹关系从被迫合作，到第一次公开承认双方利益不能同时满足”的 relationship target，就形成了独立、具体的关系 progression。该版本沿用 P0 主线背景，但没有新增主商业线、没有重排全书、没有决定最终关系或谜底。

因此 arbitrary/local planning scope 在真实内容下成立。

### H. DECISION_WRITEBACK = PASS

正式 P0 Candidate 保持 `proposal_noncanonical / ai_candidate:noncanonical`；测试 Decision 为 `simulated_confirmed_for_test`，不是作者真实决定。Diff 以 state_rev=1 为 base，apply 后 state_rev=2，approved_plan 只新增 1 条、occurred=false。

`canon_facts / character_state / relationship_state / occurred_events / open_threads` 全部 deep-equal 不变，`CANON_POLLUTION = ZERO`。

## 关于没有 C0/C1 / Blind Review

本轮未做 C0/C1，不是实验缺失，而是冻结策略的预期合法路径：只有存在真正 useful BKP 时才进行严格 ablation。当前正式 Retrieval 没有提供这样的候选，因此强行构造 C1 会把第二次修订收益或泛化提示误计为 BKP 独立价值。

因此也不存在需要执行的 C0/C1 blind review。

## 当前真实缺口

1. `COMMITTEE_TEMPLATE_RISK`：强模型第一版长篇规划仍可能把现实事件排列得过于整齐；后续真实案例继续观察，不据单案例升级为固定规则。
2. Retrieval 对“责任 / 选择 / 后果”表面语义召回正常，但对“未解过去如何通过当前行为持续改变关系判断”的细粒度创作机制匹配不足。当前只记录，不重开 BookDistill / KnowledgeRetrieve。
3. E2-B 证明了 local scope 可以单独规划，但尚未验证“作者修改一个已确认局部规划后，如何 supersede / stale / replacement 且不影响无关 planning”的完整局部重规划写回语义；这属于 E2-C。
4. E1 `apply_diff` 最终公共 State Writeback 层的 Decision action / planning-id 唯一性防御，以及 StoryPlan 对恶意 non-dict plans 的统一 ContractError，仍为既有非 blocker 技术债。

## 阶段结论

`E2B_VERTICAL_SLICE_PASS`

StoryPlan v0 已经证明：技术合同不是空壳，它可以承载真实长篇规划；强模型第一版具有可用的长篇发动机；deliberate ambiguity 能保留；局部 scope 能独立工作；知识可以在无增益时被拒绝；planning writeback 不污染 Canon。

下一阶段建议：

`E2-C_STORYPLAN_LOCAL_REPLAN_AND_STALE`

只验证作者修改/否定一个局部已确认 planning 后的 supersede、stale、replacement 与无关 sibling/ancestor 隔离；不要重新做全书规划，也不要扩大 StoryPlan Schema。E2-C 通过后再进入 Context Compiler。
