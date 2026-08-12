# BookProfile Scout v0.1

> 角色：深度 Discovery 之前的**导航性作品识别**。它不是完整蒸馏，也不是最终 BookProfile。

## 目标

用较低成本建立对作品的第一张地图：

- 这大概是什么作品；
- 主要阶段/结构可能怎样；
- 文本正在向读者承诺什么；
- 哪些能力显得值得后续重点观察；
- 哪些地方现在还看不懂。

输出是 `book_profile_initial.md`，状态始终是 **HYPOTHESIS / NAVIGATION ONLY**。

它不能：

- 宣布“未发现的维度没有价值”；
- 直接生成 MECHANISM / Pattern / Production Rule；
- 替代后续观察者直接阅读原著；
- 把少量锚点样本冒充全书覆盖。

## 上游吸收

### ADAPT｜AI-Novel-Writing-Assistant

吸收其拆书 `overview → 后续 section` 的思想：先建立作品定位/题材/卖点/目标读者等口径锚点，再进入其他分析；但 AI-write 不让 overview 成为后续事实权威。

### ADAPT｜oh-story

吸收其 thin first-pass / 故事框架识别思想：先利用章节结构、开头、阶段锚点和结尾形成低成本全书导航，再进入逐章与聚合分析。

### ORIGINAL｜AI-write

- BookProfile 是导航，不是过滤器；
- 初步识别必须允许后续被推翻；
- 原著始终高于 Profile；
- 后续两个观察者仍直接读原著；
- 最终 BookProfile 必须说明哪些初步判断被确认、修正或推翻。

## 输入

SourcePrepare PASS 包：

`06_工作区/SourcePrepare/<book_id>_<书名>/`

由 `profile_scout.py init` 生成 `book_profile_initial.md`，其中列出一组**分层锚点章节**：

- 短书：章节很少时直接覆盖全部；
- 长书：开头 3 章 + 约 25% / 50% / 75% 位置 + 结尾 3 章，自动去重。

这些锚点只是导航样本。Agent 发现结构断点、卷边界或显著变化时，可以额外读取任何原文章节，不受锚点限制。

## 阅读顺序

1. 读 SourcePrepare metadata、章节索引/标题，确认身份与体量；
2. 直接读取 Scout 列出的原著锚点章节；
3. 必要时扩展到邻章或明显卷/阶段边界；
4. 填写初步 Profile；
5. 明确写出“不确定项”，不要为了完整强行下结论；
6. 进入两个完整 Discovery 观察者。

## 必填内容

### 作品初步定位

题材/叙事形态/主要阅读回报的**假设**。不做市场人口学伪精确画像。

### Contract / Reader Promise 假设

读者大概被承诺了什么体验、问题、关系或长期回报。

### 粗略阶段地图

只标记目前可见的阶段/变化，不要求第一轮准确切出全部剧情单元。

### 显著强项

只有在锚点中已经有较强信号时填写，并说明仍待全书 Discovery 验证。

### 潜在强项

“值得继续看”的候选，不等于已经确认。

### 不确定项

主动记录当前无法判断、样本可能误导、需要跨章验证的地方。

### Discovery 建议重点

告诉后续观察者“这里值得多看一眼”，但必须附一句：

> 本列表不构成排除项；观察者仍按自身合同直接读原著并允许发现未列价值。

## 完成后的修订规则

两个 Discovery 和必要 Deep Dive 完成后，最终 `book_profile.md` 应对初步 Profile 做一次复盘：

- confirmed：哪些初步判断被原著全书证据确认；
- revised：哪些需要降级/改写；
- rejected：哪些初步判断被推翻；
- newly_discovered：哪些重要价值 Scout 根本没有看见。

“Scout 没看见但后续发现了重要东西”是正常结果，不是失败。
