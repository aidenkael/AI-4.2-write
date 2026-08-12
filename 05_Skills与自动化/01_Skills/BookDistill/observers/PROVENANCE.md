# Observer Layer PROVENANCE v0.1

本文件只记录 BookDistill `observers/` 与 `observer_bridge.py` 的来源性质。

## 分类

- `COPY`：基本按上游文件复制，仅做必要路径/命名调整。
- `ADAPT`：明确基于上游方法/结构重新编写，适配 AI-write 的目标和合同。
- `WRAPPER`：AI-write 为连接既有模块新增的确定性接口。
- `ORIGINAL`：AI-write 自己的知识协议、边界或实现。

本版**没有整文件 COPY**。原因不是许可证阻塞，而是上游任务边界不同：oh-story 面向网文拆文/写作资产，AI-Novel 面向完整产品拆书，creative-writing-skills 面向自己稿件的写作与读者模拟。直接整文件复制会把无关产品流程一起带入 BookDistill。当前选择的是源码/Skill 级读取后做窄适配。

## 来源映射

| AI-write 组件 | 性质 | 上游来源 | 实际吸收 |
|---|---|---|---|
| `longform_reader_dynamics.md` | ADAPT | `worldwonderer/oh-story-claudecode`：`skills/story-long-analyze/SKILL.md`、`references/material-decomposition.md`、`pipeline-ops.md` | 逐章原子提取、情节点、关键信息与扩写技法、剧情单元、情绪/节奏/信息推进、跨章聚合、稳定章节边界与恢复思想 |
| `longform_reader_dynamics.md` | ADAPT | `ExplosiveCoderflome/AI-Novel-Writing-Assistant`：`shared/types/bookAnalysis.ts`、`bookAnalysis.prompts.ts`、拆书 workflow | overview 导航、section 化分析、evidence 绑定原文、source range、token/失败恢复/只补缺口等工程思想 |
| `reader_page_craft.md` | ADAPT | `haowjy/creative-writing-skills`：`reader-sim`、`writing-principles`、`creative-writing-craft/resources/prose-writing.md`、`scene-construction.md` | first-time reader 顺序体验、reward channels、信任读者、psychic distance、POV、interiority、节奏、感官、对话/潜台词、scene pacing |
| Developmental Deep Dive 路由 | ADAPT / existing | `anotherpanacea-eng/apodictic` | contract、Reader Experience、Decision Pressure、Scene Function/Turn、Emotional Craft、Reveal Economy、Character Architecture、POV/Voice 等按问题触发镜头；本版未复制完整审稿流程 |
| `observer_bridge.py` | WRAPPER + ORIGINAL | AI-write | SourcePrepare snapshot 校验、observer staging、引用/行号/标签校验、幂等合并到 canonical evidence；不调用模型 |
| `README.md` | ORIGINAL + integration | AI-write | 规定观察者只产生 Observation/Inference/Boundary，BookDistill 才能提升为 Mechanism/BKP；保证多上游最终进入统一知识协议 |
| Evidence / BKP / BookDistill Finalize | ORIGINAL / existing | AI-write（早期证据纪律受 ani-book 等启发） | 原著最高事实源、Evidence→Observation/Inference→Work-specific Pattern、scope/boundary/counterevidence/confidence、参考知识与原创 Canon 隔离 |

## 关键上游版本锚点（2026-08-13 集成时）

- oh-story `story-long-analyze/SKILL.md` blob: `5718af52be65f4d4c16cf7b9449b102f1d0052bb`
- oh-story `material-decomposition.md` blob: `386658797d28086b740cfeccd3bb62b24268e952`
- oh-story `pipeline-ops.md` blob: `a211d41f8911b5686ffff4abd6f55bbf2a7dcf71`
- AI-Novel `shared/types/bookAnalysis.ts` blob: `64658336511411f77a993358d5c1ca9e25c2732b`
- creative-writing-skills `reader-sim/SKILL.md` blob: `ebfc96a18f7d8c0509c421d06f0725975bb8fd1a`
- creative-writing-skills `writing-principles/SKILL.md` blob: `ee3645368997c2a1e42ca1615ae2679e4bbd90e7`
- creative-writing-skills `prose-writing.md` blob: `ef514cd0d8bf2233c8fd2efb2e00ae47d35048f0`
- creative-writing-skills `scene-construction.md` blob: `32a2ea1d207d7c1d7c230706168189ebfdc0ef21`

## 为什么不是五套报告堆叠

上游名称、taxonomy 和产品目标不成为 AI-write 的长期权威。

统一流程是：

`上游成熟观察方法`
→ `observer staging`
→ `AI-write Evidence / Observation / Inference / Boundary`
→ `BookDistill 回原著核证、去重、组合`
→ `Work-specific Pattern`
→ `BKP`

因此“多个项目都这么说”本身不能升级知识等级；证据和适用边界仍然优先。

## 许可证

当前私人项目许可证不作为技术路线阻塞。保留来源和版本锚点，方便未来公开/商业分发时统一处理 provenance / attribution / copyleft 边界。
