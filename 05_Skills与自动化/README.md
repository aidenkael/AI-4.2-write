# 05_Skills与自动化

工作台**已验证的基座能力 / Skills**。

## 放什么

- 正式 Skill 目录（MaterialIntake / SourcePrepare / BookDistill / KnowledgeRetrieve / StoryDesign / StoryPlan / ContextCompiler / StoryWrite）
- 运行时必要工具（如 pandoc，仅本地使用）

## 不放什么

- 开发 Benchmark（已完成使命的实验）
- 一次性开发脚本
- 过时 Agent 指令
- 临时模板

## 当前 Skill

| Skill | 职责 | 状态 |
|---|---|---|
| MaterialIntake | 素材资产 canonical ledger（素材资产.json）+ 9 列 CSV / 索引 derived views | **CANONICAL_CATALOG_AVAILABLE** |
| SourcePrepare | 原著 EPUB/TXT → 纯净 Markdown（canonical ledger consumer） | available |
| BookDistill | 参考作品知识提取（BKP + evidence） | freeze / available |
| KnowledgeRetrieve | BKP 多轴检索 | freeze / available |
| StoryDesign | 故事设计运行底座 | closed / frozen |
| StoryPlan | 长篇规划（合同/投影/重规划） | closed / frozen |
| ContextCompiler | 上下文编译（显式选择） | consumer-driven freeze |
| StoryWrite | 写作原语与机械结算辅助 | keep / freeze |
| ProjectWorkspace | 真实作品机械接线层，不负责文学判断 | available |

## Agent 操作规则

- 作者平时不需要手动进入此目录
- Agent 应优先复用现有能力
- 禁止为一次任务新造长期 Skill
- 不重构冻结 Skill 内部结构，除非路径迁移所必需

## 与 07_工作台应用 的关系

- `07_工作台应用`（作者侧桌面应用）通过 **Agent Adapter** 调用这里的 Skill
- UI 禁止直接调用 StoryWrite / StoryPlan / BookDistill 等 Skill
- 现有 Skill 不迁移到 `07_工作台应用`，保留在 05 由 Agent Adapter 复用
