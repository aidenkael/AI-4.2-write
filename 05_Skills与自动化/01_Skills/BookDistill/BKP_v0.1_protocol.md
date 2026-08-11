# BKP v0.1 候选协议

## 1. 定位

BKP（Book Knowledge Package）是一部参考作品完成蒸馏后形成的长期知识资产。

目标不是代替原著，也不是保存全部蒸馏过程，而是让未来创作可以直接回答：

* 这本书在哪些创作问题上值得参考？
* 它具体做了什么？
* 判断依据在哪里？
* 这个结论适用于什么情况？
* 有什么边界、反例和不确定性？

正常写作阶段只检索 BKP，不重新蒸馏原著。

---

## 2. 必须长期保存

### A. 作品身份

必须保存：

* book_id / 作品名
* source snapshot / fingerprint
* 版本信息
* provenance
* 蒸馏版本与完成状态

作用：证明知识来自哪一份原著。

### B. 作品地图

保存经过整理的：

* 主要结构
* 章节 / 阶段变化
* 关键事件与因果
* 重要人物、关系和状态变化
* 重要信息释放与读者认知变化

不要求保存所有细节事实。

### C. BookProfile

保存最终作品画像：

* 已扫描维度
* 主要强项 / 潜在强项
* 不确定项
* 已完成专项深挖
* 尚未解决的重要问题

BookProfile 是未来进入这本书知识的第一入口。

### D. Observation

Observation 是 BKP 的核心知识层。

保留作品中真正有分析价值的具体观察，并关联：

* dimension / topic
* source evidence
* confidence
* scope
* boundary / counterevidence（如存在）

不得强迫所有 Observation 继续抽象成 Pattern。

### E. 重要 Inference

有创作价值、但不是原文直接事实的推断必须保留，并明确标记为 Inference。

不能把 Inference 混写成 Fact 或 Observation。

低价值、临时性推断可以只留在蒸馏工作区。

### F. Work-specific Pattern

由多个 Evidence / Observation 支撑的作品内模式可以进入 BKP。

必须保持：

* 仅对本作品成立的默认身份
* 支撑 Observation / Evidence
* 适用范围
* 边界 / 反例
* confidence

不得直接升级成普遍写作规则。

### G. Deep Dive 最终知识

专项深挖产生的高价值结果进入 BKP。

保留最终：

* Observation
* Pattern / interpretation
* Evidence
* Counterevidence
* Scope
* Confidence

不保存无价值的中间分析过程。

---

## 3. 可选保存

只有确实具有未来检索价值时保存：

* 代表性 FACT
* 重要意象 / motif 追踪
* 特殊结构索引
* 作品特有维度
* Deep Dive 衍生的专项地图
* 对未来检索有帮助的标签

不因为 schema 有字段就强行填满。

---

## 4. 只留蒸馏工作区

默认不进入正式 BKP：

* 每章原始填写模板
* 重复 FACT
* 临时统计
* Agent 工作记录
* 测试日志
* 中间 Prompt
* 重复 Observation
* 已被最终知识吸收的 Deep Dive 草稿
* 调试和 Benchmark 过程文件

这些材料可以用于审计、返查和系统升级，但不是日常创作知识。

---

## 5. Evidence 原则

BKP 不需要复制全部 Evidence 内容，但任何重要知识必须能够追溯到：

原著 → 章节 → 行号 / 位置。

重要结论不能只留下总结而失去证据链。

---

## 6. 知识成熟度边界

单本 BKP 内最高默认只到：

Evidence
→ Observation / Inference
→ Work-specific Pattern

Cross-book Pattern、Creation-tested Heuristic、Production Rule 属于 BKP 之外的跨作品知识成熟度系统。

一本书不能自行证明普遍写作规律。

---

## 7. 作者使用方式

作者默认只先看到：

**BookProfile + 这本书最值得调用的创作问题。**

具体 Observation、Pattern、Evidence 等由系统在真正需要时检索。

作者不需要手动阅读整个 BKP。

---

## 8. v0.1 不冻结的内容

当前暂不冻结：

* 最终 JSON schema
* 文件拆分数量
* Observation 数量
* BKP 总字数
* 固定 Deep Dive 次数
* Vector / RAG / KG 实现
* 永久固定的分析维度列表

原则先稳定，存储实现以后根据真实使用调整。
