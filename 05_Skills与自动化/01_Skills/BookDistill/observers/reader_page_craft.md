# Observer: Reader / Page Craft v0.1

> observer_id: `reader_page_craft`

## 作用

直接以“第一次阅读”的方式读原著，记录读者在页面上实际经历什么，再把这些体验与页面级 craft 联系起来。

它不是第二份剧情分析，也不是事后找技巧清单。

核心问题是：

> 这一刻，读者被文本带到了什么状态？作者具体用了哪些页面动作让这种状态发生？

## 上游吸收

本观察者主要是 **ADAPT**：

- `haowjy/creative-writing-skills`
  - `reader-sim`：按阅读顺序追踪投入、漂移、问题、预测和体验变化；
  - `writing-principles`：Transportation / Aesthetic / Social simulation / Curiosity-Prediction / Flow 等 reader reward channels，以及“信任读者”“经济性”；
  - `creative-writing-craft`：psychic distance、free indirect discourse、sentence rhythm、sensory grounding、interiority、POV、scene entry、dialogue/subtext、scene pacing。
- AI-write 自己保留：
  - 不把某个读者反应伪装成“所有读者都会这样”；
  - 原著证据优先；
  - 体验信号与分析解释分层；
  - 最终由 BookDistill 决定什么值得进入 BKP。

## 第一遍：只做 Reader Experience

### 知识边界

读第 N 章时，只使用读者到第 N 章此刻已经获得的信息。

不要因为 Agent 已经知道整本书结局，就把后文解释倒灌进首次阅读体验。

### 逐时追踪

只在体验发生明显变化时记录，不需要逐段点评。

重点看：

- **Lean in**：哪里突然更想知道、想继续、想确认；
- **Drift**：哪里注意力松掉、阅读变成机械推进；
- **Question stack**：此刻正在持有什么问题；
- **Prediction**：此刻读者自然会猜什么；
- **Reorientation**：什么新信息改变了前面的理解；
- **Emotional state**：压抑、松弛、尴尬、甜、危险、亲密、荒诞、惊奇等怎样转换；
- **Character model**：读者此刻怎样理解一个人物的欲望、边界、隐瞒、矛盾；
- **Trust / confusion**：模糊是有生产力的悬念，还是失去定位的困惑。

### Reader reward channels

必要时用以下通道解释体验，但不要每章机械全填：

- `Transportation`：世界/场景/POV 是否让读者进入其中；
- `Aesthetic`：语言、节奏、意象是否本身带来阅读快感；
- `Social simulation`：人物是否像可被建模的心智，而不是信息载体；
- `Curiosity / prediction`：问题、悬念、预期、推断是否持续运转；
- `Flow`：阅读是否顺畅保持吸收，难度与信息密度是否匹配。

多个通道会互相影响。不要把它们当互斥分类。

## 第二遍：Page Craft 回查

先有体验，再回头问“文本怎么做到”。

优先观察：

### POV / Psychic Distance
- 叙事距离何时拉近/拉远；
- 何时进入人物词汇、判断和感官；
- 何时用总结压缩，何时把重要瞬间放大；
- FID/内心/动作之间如何切换。

### 人物心智
- 情绪是否由行为、选择、注意力、内心联想让读者自己拼出来；
- 人物行为是否具有个体化因果；
- 角色是否只承担剧情功能；
- 非 POV 人物如何通过可观察行为被读者理解。

### 对话与潜台词
- 对话是否同时承担多重功能；
- 说出的和真正想表达的之间是否有距离；
- 回避、转移、停顿、动作 beat 怎样改变意义；
- 不同角色是否具有可辨认的语言习惯。

### 语言与节奏
- 句长、句型、段落密度如何随场景工作变化；
- 何时速度突然加快/变慢；
- 重复、停顿、破句、并列等是否制造体验，而不是纯装饰。

### 感官与注意
- 哪些具体细节让场景成立；
- 为什么是这个 POV 人物会注意到这些东西；
- 感官细节是否同时承担人物、情绪、信息或象征功能。

### 留白与经济性
- 哪些情绪没有被解释，但读者能重建；
- 哪些信息故意少说；
- 一个动作/物件/称呼是否同时完成多件事；
- 是否存在“单独看普通，但和前后细节组合后突然产生强效果”的元素。

### Scene / Transition
- 场景从哪里切入；
- 什么时候结束；
- 高低张力 beat 怎样排列；
- 场景之间跳过了什么，为什么能跳；
- 转场是否同时携带时间和情绪变化。

## 特别关注：组合效果

AI-write 需要的不只是“这里用了感官描写”。

优先寻找：

`前一段读者状态`
→ `若干普通页面动作`
→ `读者状态换挡`
→ `后续场景因此获得新的接受条件`

例如一个小动物动作、食物联想、身体距离、称呼变化各自可能都很普通；真正值得保存的可能是它们连续出现后怎样把读者从压抑带到生活感，再带到暧昧。

这种发现可以跨多个 Evidence。

不要为了现有 taxonomy 把它拆碎。

## 输出分层

### Experience Signal
先在 Observer Notes 里用自然语言写：

- “这里开始担心……”
- “这里猜到……”
- “这里突然觉得两个人距离变近……”
- “这里失去方向，不是悬念而是定位不足……”

它是体验信号，不必假装成客观事实。

### Observation
只有能回到具体文本动作时，再写 canonical-compatible 条目：

```text
- [OBSERVATION] dimension:Reader Experience | observer:reader_page_craft | 连续三个短动作都不给情绪标签，读者需要自己拼出人物的慌乱，Social simulation 因而比直接说明更强｜证据：chapters/0021.md#L30-L45｜置信度：中
```

### Inference
当你解释“为什么可能有效”，但原文不能直接证明时，用 INFERENCE，降低结论强度。

### Boundary
主动记录：

- 译本可能改变句法/词感；
- 某体验高度依赖前文；
- 某阅读反应只适用于当前假定读者；
- 同一技巧在其他场景可能产生相反效果。

## 跨章 synthesis

`synthesis.md` 重点回答：

1. 这本书主要通过哪些 reader reward channels 持续给回报？
2. 人物是怎样逐步成为“可建模的心智”的？
3. 页面语言和长篇节奏怎样协同，而不是各自独立？
4. 有哪些反复出现、但每次都因上下文变化而产生不同效果的 craft？
5. 哪些“重要但暂时难命名”的组合效果值得 Deep Dive？

不要把 synthesis 写成风格模仿指南。未来写作调用的是功能、条件、效果和边界，不是复刻作者表面句式。
