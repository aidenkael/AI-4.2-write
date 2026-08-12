# AI-write 全局能力地图 v0.2

> 首建：2026-08-10  
> 最近校准：2026-08-12（G3 closeout 后）  
> 状态：**长期技术能力路由图**。C01–C20 继续保留，但不再作为串行 Benchmark 排期或“20 个作者 Skill”。  
> 成熟作者战略地图：六个大区，见根目录 `AI-write_长期开发手册.md` 第 6 节。  
> 上游路由：`00_项目控制/GitHub候选池_能力路由_v0.2.md`。  
> G3 收口前旧版已原样归档：`99_归档/AI-write_全局能力地图_v0.2_G3收口前_2026-08-12.md`。

---

# 一、地图用途

遇到真实蒸馏 / 创作问题时：

```text
问题
→ 先定位成熟作者六区中的大类
→ 再定位 C01–C20 技术能力
→ 查看已有上游 / 已吸收能力 / 当前边界
→ 最小真实测试
→ 直接借 / 适配 / 保留 / 放弃
→ 只有真实剩余缺口才自研
```

这张地图不再用于：

- B02 → B01 → B04 → B05……逐项排 Benchmark；
- 把 C01–C20 一一开发成 Skill；
- 用一个 M 分数假装文学能力已经“客观完成”；
- 因为某个格子没跑独立 Benchmark，就阻止真实创作链建设。

---

# 二、六区战略地图与 C01–C20 的关系

| 成熟作者能力大区 | 对应技术能力 |
|---|---|
| 1. 作品方向与判断 | C01 故事发动机、C11 连载/读者承诺的一部分、C15 文学功能、C20 Controller/作者控制的一部分 |
| 2. 故事运行能力 | C01、C03、C05、C09、C10、C11、C16、C17、C20 |
| 3. 读者与文本效果 | C04、C09、C10、C11、C12、C15 |
| 4. 页面写作能力 | C02、C04、C06、C07、C08、C14、C15、C16 |
| 5. 判断与修订能力 | C09、C12、C13、C18、C20 |
| 6. 长期知识与创作运行能力 | C17、C19、C20，以及 Retrieval / Context Compiler / State Writeback |

永久开放：**重要，但目前无法命名。**

如果一个真实问题无法自然塞进 C01–C20，不要为了维护表格完整性丢掉它；先记录问题，再决定是否需要扩展技术路由。

---

# 三、当前状态词怎么理解

以后不再强求所有能力都用同一套 M0–M5 数字描述。

本表主要使用四种状态：

- **可用地基**：已经有可运行资产/协议，足以被下一阶段消费；
- **方法已确认**：成熟上游方法已经明确，但尚未组合进 AI-write 正式运行时；
- **Phase E 待组合**：不是“没研究”，而是下一阶段需要从成熟上游组合成创作闭环；
- **真实问题触发**：当前没有必要单独开发，等真实创作暴露瓶颈再复查。

“项目方法被审查 / 局部机制被实测”不能扩大成“整个上游整体运行验证”。

---

# 四、C01–C20 当前能力主表

| ID | 技术能力 | 当前状态 | 核心上游 / 已有地基 | 当前真正边界 | 下一触发点 |
|---|---|---|---|---|---|
| C01 | 故事发动机 / 作品方向 | **Phase E 待组合** | AI-Novel、oh-story、creative-writing-skills、Apodictic | 尚未形成 AI-write 自己的“作者意图→故事发动机”运行链 | Phase E Planner / Author Decision Loop |
| C02 | 人物声音 | **方法已确认** | creative-writing-skills Character Sim / Writer、oh-story 对话 | 未形成统一 Character Sim→Writer 消费接口 | Phase E Character Sim / Writer |
| C03 | 人物心理与决策 | **方法已确认** | Apodictic Character Architecture / Decision Pressure、creative-writing-skills | 真实原创人物长期演化尚未验证 | Phase E 人物状态 + Character Sim；Phase F 场景验证 |
| C04 | 情绪传递 | **有方向性实测 + 方法已确认** | B02 M2 信号、creative-writing-skills、Apodictic、oh-story | 小样本不能升级成普遍规则 | Phase F 真实场景 / 小故事弧 |
| C05 | 关系状态 | **Phase E 待组合** | InkOS、creative-writing-skills、Apodictic、oh-story | 关系状态如何进入 Canon、Planner、Writer、writeback 尚未统一 | Phase E Story State / Character Sim |
| C06 | POV / 叙述距离 | **方法已确认** | creative-writing-skills Page Craft、Apodictic POV/Voice | 未作为 AI-write 正式 Writer/Editor 合同 | Phase E Writer / Editor；真实问题触发 |
| C07 | 人物化微动作 / 身体性 | **方法已确认** | creative-writing-skills、Apodictic Interiority / somatic 方向 | 不应固化成“多写动作”的机械规则 | Phase F 人物场景暴露问题时 |
| C08 | 对话 / 潜台词 | **有方向性实测 + 方法已确认** | oh-story、creative-writing-skills、Apodictic | 过密规则会让对白设计感过强 | Phase E Writer / Critic；Phase F 对话场景 |
| C09 | Scene / Scene Turn | **有方向性实测 + 方法已确认** | Apodictic Scene Turn、creative-writing-skills scene craft、B09 K1 | 不是每个场景都套固定 turn 模板 | Phase E Scene Planner / Editor |
| C10 | 信息控制 / 悬念 | **有方向性实测 + BKP 已有知识** | B09 K3/K4、Apodictic Reveal Economy、oh-story、AI-Novel | 单书技巧和 Smoke Test 不能变普遍规则 | Phase E Planner；Phase F 悬念场景 |
| C11 | 长篇读者动力 / 连载留存 | **方法已确认，Phase E 重点** | oh-story、AI-Novel Reader Experience Contract | 不能机械化成“每 N 章一个爽点” | Phase E Planner / Reader Experience |
| C12 | Reader Sim | **方法已确认，Phase E 重点** | creative-writing-skills Reader Sim、Apodictic Reader Experience、AI-Novel | 模拟读者不是“普遍读者真相”；需要 persona/knowledge boundary | Phase E Reader 层；Phase F 真人作者读感对照 |
| C13 | Character Sim | **方法已确认，Phase E 重点** | creative-writing-skills Character Sim | 需要与 Canon / 当前关系状态连接，避免只做角色聊天玩具 | Phase E Character Sim / Planner |
| C14 | 中文自然度 / 去 AI 味 | **方法已确认，真实问题触发** | oh-story deslop / 文风、creative-writing-skills llm-writing / style | 不能只靠禁词表和 AI 痕迹打分 | Phase E Writer / Editor 后，Phase F 正文暴露问题时 |
| C15 | 文学功能 / 审美效果 | **方法已确认，真实问题触发** | creative-writing-skills reward channels、Apodictic Literary Craft | 审美不能压成单一总分 | Phase F 真实文本判断 |
| C16 | 世界质感 / 世界进入叙事 | **方法已确认，Phase E 待组合** | Apodictic SFF Worldbuilding、InkOS / AI-Novel 世界状态 | 世界设定很多 ≠ 世界在正文中有叙事作用 | Phase E Story Bible / Planner / Writer |
| C17 | Canon / Memory / Story State | **Phase E 核心待组合** | InkOS、graphify-novel、NovelForge、ani-book、AI-Novel | 候选丰富，但 AI-write 的最小权威状态协议尚未正式建立 | Phase E 第一批架构决策 |
| C18 | 修订 / 诊断 | **Phase E 核心待组合** | Apodictic、creative-writing-skills Critic/Editor、AI-Novel repair、oh-story review | Reader 感受、Critic 分析、Editor 优先级不能重复成三个相同报告 | Phase E Review / Revision loop |
| C19 | 原著蒸馏 / 能力发现 | **可用地基 + Discovery 方法已升级** | SourcePrepare、BookDistill v0.2、BKP v0.1、ani-book、oh-story、creative-writing-skills、Apodictic、AI-Novel | 旧版“BookDistill 尚未实现”已废止；当前未验证的是多视角 Discovery 在新书上的长期实际收益，不是工具不存在 | 新参考书真实蒸馏时验证；不重开 G3 |
| C20 | 工作流 / Controller / 作者控制 | **Phase E 核心待组合** | InkOS、creative-writing-skills Muse、AI-Novel、NovelForge | 目标不是自动化最大化，而是后台自动路由 + 重大决定作者确认 | Phase E Gate 的核心之一 |

---

# 五、G0–G3 已形成的可复用地基

## SourcePrepare

状态：稳定输入地基。

原则：没有真实阻塞时不继续优化。

## BookDistill / BKP

状态：Phase C 技术验证完成，两本正式样本已经跑通。

已验证：

- evidence-first；
- BookProfile；
- 1～N Deep Dive；
- BKP Finalize；
- 两种差异明显作品可以共用底座而不完全压平；
- 单书知识成熟度边界。

2026-08-12 方法级升级：

- 默认长篇运行 / 读者动力 Discovery 镜头；
- 默认 Reader / Page Craft Discovery 镜头；
- 按问题触发 Developmental Deep Dive；
- BookDistill 总编辑式回源核证 / 整合 / 压缩；
- 允许跨句、跨场景、跨章节组合证据；
- 永久允许“重要但难以命名”。

不因此重跑《一九八四》《三体》。未来新书真实使用时验证。

## KnowledgeRetrieve

状态：`G3_RETRIEVAL_VALIDATED / CLOSED`。

已证明：

- 多 BKP 统一入口；
- 小量跨书召回；
- Evidence / Scope / Boundary / Counterevidence / Confidence 保留；
- 无可靠答案时可返回不足；
- 当前无需升级大型 RAG / KG。

结论：`NO_RAG_UPGRADE`。

Retrieval 不是 Cross-book Synthesis；后者归 Phase E Context Compiler / Muse / Planner。

---

# 六、Phase E 当前真正需要解决的能力组合

下一阶段不是“补完 C01–C20 的所有空格”，而是拼出最小可工作的创作后台：

```text
作者意图
+ Story / Project Bible
+ Canon / Story State
        ↓
Context Compiler
+ 少量 BKP Retrieval
+ Cross-book Synthesis
        ↓
Planner / Outliner
        ↓
Writer / Character Sim
        ↓
Reader Sim / Critic / Editor / Continuity
        ↓
作者确认重大取舍
        ↓
State Writeback
        ↓
下一轮
```

Phase E 优先需要 C17、C20 作为状态与控制地基，并同时接通 C01/C03/C05/C11/C12/C13/C18 等创作能力；不是先把每一项独立“升到 M5”。

---

# 七、历史 Benchmark 资产怎么处理

## B02

Round1 + Round2A 完成并暂停。

- “人物特异性反应”等是方向性候选；
- 不自动升级 Production Rule；
- 不启动 B02-R / Round2B。

## B09

Round01 + Round02A 完成并暂停。

- K1–K4 作为能力方向和历史证据；
- 不启动 Round02B。

历史 Runner / 盲测文件继续保留用于追溯，但不再决定主线排期。

---

# 八、什么时候才升级严格 Benchmark

同时满足以下条件才考虑：

1. 某机制准备成为长期核心规则；
2. 现有证据互相冲突或极易误判；
3. 固化错误会造成高代价；
4. 少量真实任务不能给出可靠判断。

其他情况：最小真实测试 + 作者快速判断即可。

---

# 九、当前明确不做

- 不批量蒸馏现有全部原著；
- 不重跑《一九八四》《三体》只为“更新方法版本”；
- 不启动 B02/B09 新轮次；
- 不把单书 Pattern 升级为 Production Rule；
- 不为了技术完整度升级 Retrieval；
- 不无真实瓶颈建设大型 RAG/KG；
- 不把 C01–C20 变成作者必须操作的 20 个 Skill；
- 不先把每格做完再开始创作后台；
- 不从零重造成熟上游已有 Writer / Reader / Editor / Canon / Continuity；
- 不直接把正式长篇作为工具试验品；
- 不因为 taxonomy 没位置就丢掉“重要但难以命名”的发现。

---

# 十、一句话地图

> **六个成熟作者能力大区负责“不漏掉作者真正需要什么”，C01–C20 负责把真实问题路由到技术能力和成熟上游；它们都服务真实创作，不再服务一场无休止的 Benchmark 清单竞赛。**
