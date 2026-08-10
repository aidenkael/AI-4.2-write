# BookDistill PROVENANCE（来源与许可证记录）

## 本技能性质

AI-write 本地自研最小技能：脚本、证据模板、SKILL 文档均为本仓库原创实现。
方法纪律继承自以下来源；本轮没有整体复制任何外部项目代码进入本目录。

## 方法来源

| 来源项目 | 来源仓库 | 许可证 | 证据状态 | 本轮继承内容 |
|---|---|---|---|---|
| ani-book | ExplosiveCoderflome/ani-book-skill | Apache-2.0（P1） | B09 R01 Runner B 方法适配正式实测；证据关系=直接 | evidence-first 低推断记录、fact/inference/hypothesis 分层、confidence、counterevidence、coverage、pattern/mechanism 的证据约束 |
| oh-story | worldwonderer/oh-story-claudecode | MIT（P1） | B09 R01 方法适配正式实测 | 选择性吸收：场景/章节推进、信息释放、节奏、期待/回报、人物与关系功能、可迁移结构机制（不宣称其全部能力已验证） |
| SourcePrepare 接口草案 | 本仓库 `skill/source-prepare-v1` 旧分支 | 本仓库 | 旧分支存在 `BookDistill/SKILL.md` 草案 | 只读参考接口契约（PASS 包 -> chapters/ -> 蒸馏输出）；未整体 merge 旧分支 |

## 本轮未借用项目（浏览结论）

按门禁要求浏览候选路由中以下项目当前状态；结论：**v0.1 不存在必须借用任一项目才能解决的具体问题**。
它们停留于代码/架构审阅或方法参考级别，未宣称已验证。

| 项目 | 许可证（以候选路由 v0.2 为准） | 状态 | 未借用理由 |
|---|---|---|---|
| Apodictic | CC BY-NC-SA 4.0（P2） | 代码/架构审阅，未实测 | v0.1 无人物结构/修订诊断问题需要解决 |
| NovelClaw | MIT | 代码/架构审阅，未实测 | v0.1 无长期记忆/一致性（Canon/Memory）需求 |
| InkOS | AGPL-3.0 | 代码/架构审阅，未实测 | v0.1 无 Controller/state/trace 需求 |
| NovelForge | AGPL-3.0 | 代码/架构审阅，未实测 | v0.1 无结构化生成/知识图谱/写回需求 |
| AI-Novel-Writing-Assistant | AGPL-3.0-only + 服务型商业授权说明 | 代码/架构审阅，未实测 | v0.1 无产品工作流/状态回灌需求；其贡献者 CLA/贡献协议与本轮本地研究无关，不得误写为研究前提 |
| AuthorAgent | MIT，已核实根 LICENSE（以 `GitHub候选池_能力路由_v0.2.md` 为准） | 代码/架构审阅 | v0.1 不需要其代理/评审闭环 |
| autonovel | 候选路由记录：未找到根 LICENSE 文件 | 架构/行为参考 | 只研究公开架构思想，不复制代码/Prompt |
| novel-creator-skill | README 声明 MIT，但当前未找到根 LICENSE；冻结前需复核（以候选路由 v0.2 为准） | 未实测 | v0.1 不需要借用 |
| Long-Novel-GPT | 当前未在根目录确认 LICENSE（以候选路由 v0.2 为准） | 产品体验观察 | v0.1 不需要借用 |

若未来实现遇到具体问题（如分批处理无法恢复、章节分析状态丢失），允许从上述项目借鉴一个最小机制，
届时必须在本文件追加记录：来源项目、许可证、借用原因、实际吸收内容，且不得宣称为已验证能力。

## 许可证合规

- 本轮核心实现（`scripts/`、`tests/`、`SKILL.md`、模板）为 AI-write 自研。
- 方法继承只吸收抽象纪律与接口思想；未整段复制外部项目代码或 Prompt。
- 对 CC BY-NC-SA / AGPL 来源：当前私人本地研究允许；未来公开/商业/SaaS 分发需按 AGENTS.md 触发统一许可证审计。
- 对未核实许可证来源：仅研究公开思想与架构，未复制任何受版权保护内容进入本目录。

## 承诺

- evidence 中不大量复制原文（每条结论一句话 + 行号引用）。
- 不做原作者风格模仿器；蒸馏产物为分析性证据，供作者审阅。
