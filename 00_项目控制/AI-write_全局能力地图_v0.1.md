# AI-write 全局能力地图 v0.1

> 日期：2026-08-09
> 状态：下一阶段研究基线
> 目的：把“找项目”改成“补能力”。以后先判断 AI-write 缺什么，再找最合适的上游、Baseline 与 Benchmark；不按项目选总冠军。

## 一、总原则

AI-write 的终点不是堆叠多个外部 Agent，而是形成统一的作者工作台：

`作者提出创作问题 → Controller 判断所需能力 → 加载本地 Skill / 上下文 → 生成/诊断/修订 → 必要状态确认后写回`

作者主要判断真实创作效果；内部机制、证据、许可证、上下文成本和能力归类由 Controller / Benchmark 处理。

当前不批量蒸馏全部原著，不继续整体推进 B09 Round 02B，不为尚未发生的商业化过度限制当前私人研究。

## 二、成熟度标记

- `M0 未研究`：只有问题意识，尚无稳定候选。
- `M1 候选已知`：已有上游或初步机制，但未正式 Benchmark。
- `M2 协议可测`：已有明确测试题/评价方法。
- `M3 初步验证`：完成至少一轮对照/盲测，有方向性证据。
- `M4 跨样本验证`：多任务/多样本验证，边界和副作用较清楚。
- `M5 生产固化`：已成为 AI-write 本地 Skill / 工作流，并有回归检查。

注意：成熟度评的是“AI-write 对该能力的掌握程度”，不是上游项目本身的质量。

## 三、核心能力地图

| ID | 能力 | 作者能感知的问题 | 当前成熟度 | 主要候选/来源 | 下一步 |
|---|---|---|---|---|---|
| C01 | 故事发动机 / 宏观结构 | 故事有没有持续可写的矛盾、目标、代价和阶段变化 | M1 | oh-story、Apodictic、AI-Novel-Writing-Assistant、autonovel | 暂不优先；人物/情绪稳定后再测 |
| C02 | 人物声音与知识边界 | 不同人物说话是否可互换；是否知道不该知道的事 | M2 | creative-writing-skills Character Sim、oh-story dialogue | 保留 B01，放在 B02 后衔接 |
| C03 | 人物心理与自主性 | 人物是否像活人，会误解、回避、撒谎、做错误选择，而非作者工具人 | M1 | Apodictic character architecture、creative-writing-skills Character Sim | 与 B02 联动，列为当前最高优先级之一 |
| C04 | 情绪传递 | 不说“她吃醋了”，读者是否仍自然感受到；情绪是否通过注意、解释、选择和关系变化传递 | M3 初步验证 | Apodictic emotional craft、creative-writing-skills、oh-story | B02 Round2A 完成：M2 人物特异性反应为强正向方向性候选；M1 解释抑制为轻量修订检查候选。仍需真实创作观察，不进入 M4/M5 |
| C05 | 关系状态与互动变化 | 一场戏后关系是否真的发生可识别变化，而非只有台词/情绪表演 | M1 | Apodictic、creative-writing-skills、oh-story | 嵌入 B02/B05，而非先单独开大赛道 |
| C06 | 气氛 / POV 过滤 / 叙述距离 | 不同 POV 是否看到同一个“环境描写模板”；环境是否参与判断和压力 | M2 | Apodictic、后续文学蒸馏、AI-write Candidate | B03，排在 B02/B04/B05 后 |
| C07 | 人物化微动作 | 是否仍是“握拳/咬唇/手指收紧”动作字典；动作是否来自人物常态偏移 | M2 | Apodictic + AI-write 原则 | B04；核心模型为“人物常态×控制习惯×关系×场合×压力→行为偏移” |
| C08 | 对话与潜台词 | 台词是否像真人；表面话题能否承载真正冲突；沉默/误读是否有作用 | M2 | creative-writing-skills、oh-story dialogue、Apodictic；B09-K2 | B05；把 K2“约束改变表达+误读纠错确认”带回参赛 |
| C09 | Scene Turn / 场景因果 | 场景结束后信息、关系、资源、风险、目标是否改变 | M2 | Apodictic scene/sequel、oh-story、B09-K1 | B06；K1 作为风险类专项机制，不默认所有场景启用 |
| C10 | 信息控制 / 悬念 / 伏笔 | 是否公平给线索、阶段结算、旧线索改义，而非无限加谜团 | M3（局部） | oh-story、B09-K4、B09-K3（轻规则） | 暂缓主赛道；以后悬念/智斗专项继续验证 |
| C11 | 节奏 / 网文追读 / 连载留存 | 为什么读者还想点下一章；期待债与兑现是否失衡 | M1 | oh-story 为主，中文网文原著蒸馏 | 人物/情绪之后再开专项 |
| C12 | Reader Sim | 能否预测真人读者哪里投入、走神、困惑、期待，而不是只会写漂亮书评 | M2 | creative-writing-skills Reader Sim、autonovel reader_panel | B07；必须与真人反馈做预测对照 |
| C13 | Character Sim | 角色面对同一刺激时是否按自身知识、欲望、防御和误解反应 | M1 | creative-writing-skills Character Sim、Apodictic character architecture | B02/B01 后单独验证其“预测/模拟价值” |
| C14 | 中文自然度 / 作者声音 / 去 AI 味 | 是否像中文作者在写，而非模板化、翻译腔、AI 腔；是否保留作者原有风格 | M1 | oh-story deslop/voice、creative-writing-skills style、多个中文 Skill | 后续 B10；不能只靠禁词表 |
| C15 | 文学功能 / 意象 / 深层叙事 | 文学技法是否承担结构、情绪、主题功能，而非装饰性炫技 | M1 | Apodictic、世界文学蒸馏 | 人物/场景基础稳定后再测 |
| C16 | 世界质感 / 生活纹理 | 世界是否像有人真实生活，而非设定条目堆砌 | M0-M1 | 世界文学/网文蒸馏、Apodictic worldbuilding integration | 暂不单开；后续从场景与人物行为切入 |
| C17 | Canon / Memory / 长篇状态 | 写到几十/几百章后是否遗忘设定、人物位置、伤势、关系、伏笔；上下文是否失控 | M2 | NovelClaw、NovelForge、InkOS、AI-Novel-Writing-Assistant、novel-creator-skill、AuthorAgent、Long-Novel-GPT | B08；人物赛道初步稳定后启动 |
| C18 | 修订 / 诊断 / 编辑 | 能否指出真正结构问题并给作者可执行修法，而非直接重写或打空分 | M1 | Apodictic、creative-writing-skills Critic/Editor、oh-story review | 与每个专项共用；最终可能比“自动代写”更重要 |
| C19 | 原著蒸馏 / 能力发现 | 能否从具体作品提炼有证据、可迁移、知道边界的方法 | M3-M4 | ani-book、oh-story、AI-write Candidate、D0 | **B09 当前阶段收尾**；不扩 Round 02B，不批量蒸馏 |
| C20 | 工作流 / Controller / Context Orchestration | 作者是否只需说创作问题，系统自动取正确 Skill、必要上下文并安全写回 | M1 | AI-write 自身、NovelForge、InkOS、NovelClaw、AI-Novel-Writing-Assistant、AuthorAgent | 后期组合层；现在先验证底层能力 |

## 四、B09 已产生但需要分流的能力

B09 不再作为主线继续扩张。四项原创迁移能力保留如下：

- `K1 可计算风险系统` → C09 场景因果 / 风险专项：多个独立暴露通道，角色无法一次清零风险。
- `K2 外部约束改变表达形式` → C08 对话 / 潜台词：公开环境改变信息量、媒介、节奏，并引入误读—纠错—确认成本；需加入“减法约束”。
- `K3 主动诱发式信息获取` → C10 调查 / 智斗轻规则：保留“预期反应→实际反应只更新排序；反应不是证据”，不做庞大流程 Skill。
- `K4 可逆证据与竞争性解释` → C10 悬念 / 伏笔：旧线索在新证据下改变意义，并阶段性真实结算旧问题。

以上仍不是正式 `04_写作知识库` 条目；以后在对应专项与新的 GitHub 候选共同验证。

## 五、当前优先级

### P0：现在执行

1. 冻结这份全局能力地图作为研究导航。
2. 清洗 GitHub 候选池：只保留有独特能力或工程价值的上游。
3. 为 B02 情绪传递准备候选，不立即混成超级 Prompt。

### P1：下一主线

真实蒸馏 / 真实创作暴露问题 → 定位能力地图 → 优先调用已有候选 → 最小测试 → 必要时才升级严格 Benchmark。

不再按 `B02 → B01 → B04 → B05 → ...` 串行做完整重型 Benchmark。

### P2：人物链之后

- B07 Reader Sim / Character Sim；
- B08 Canon / Memory；
- B10 中文自然度；
- B11 连载留存；
- 悬念/智斗/风险专项；
- 文学性/意象/叙述距离专项。

## 六、下一次 Benchmark 的防偏规则

1. 始终保留 D0 strong baseline。
2. 上游项目直接参赛，不先假定 AI-write 组合版更强。
3. 一个能力首轮尽量包含 2–3 个性质不同的任务，避免单题过拟合。
4. 作者只看匿名实际方案：更自然、人物更像活人、是否更愿继续写、哪个具体设计值得保留。
5. 对模型本来就会的能力不重复包装成“大 Skill”。
6. 发现“设计过密、流程说明书、AI 炫技、廉价钩子”等副作用时，与收益同等记录。
7. 通过专项验证后，才决定整套保留、局部吸收、改造或放弃。
8. 最终固化为 AI-write 本地能力，不要求写作时联网调用上游项目。

## 七、当前明确不做

- 不批量蒸馏现有全部原著。
- 不整体启动 B09 Round 02B。
- 不为了项目星数做排名赛。
- 不把所有上游都下载后机械拼接成多 Agent 系统。
- 不把情绪映射成“情绪→动作词典”。
- 不把许可证允许当前私人用途的高价值项目仅因 AGPL / CC BY-NC-SA 自动排除。
- 不在工作流未稳定前投入本地模型部署工程。
