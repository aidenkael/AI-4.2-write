# AI-write 全局能力地图 v0.2

> 日期：2026-08-10
> 状态：正式导航文件（替代 v0.1 作为当前工作地图）
> 证据账本：`06_工作区/能力地图收口/G0_能力证据与比较状态盘点_v0.1.md`
> 候选路由：`00_项目控制/GitHub候选池_能力路由_v0.2.md`
> v0.1 保留为历史基线，不删除。

## 一、地图用途

真实蒸馏/创作出现问题 → 定位 C01–C20 → 查看已有证据和候选 → 优先使用已有候选 → 最小真实测试 → 必要时才升级严格 Benchmark。

不再按 B02 → B01 → B04 → B05... 串行跑 Benchmark。由真实创作暴露瓶颈，再针对瓶颈做最小测试。

## 二、成熟度定义

成熟度评价的是 **AI-write 对该能力的掌握程度**，不是某 GitHub 项目的质量。

| 等级 | 含义 |
|------|------|
| M0 未研究 | 只有问题意识，尚无稳定候选 |
| M1 候选已知 | 已有上游或初步机制，但未正式验证 |
| M2 协议可测 | 已有明确测试题/评价方法 |
| M3 初步验证 | 至少一轮对照/盲测，有方向性证据 |
| M4 跨样本验证 | 多任务/多样本验证，边界和副作用较清楚 |
| M5 生产固化 | 已成为 AI-write 本地 Skill/工作流，有回归检查 |

## 三、当前整体状态

| 指标 | 数值 |
|------|------|
| 候选来源覆盖 | **20/20 有候选** |
| 直接实证覆盖 | **5/20**（C04、C08、C09、C10、C19） |
| 生产固化（M5） | **0/20** |

**有候选 ≠ 能力已解决。** 15 个能力格没有直接实证，全部未达到生产固化。

## 四、C01–C20 能力主表

| ID | 能力 | 成熟度 | 直接实证 | 主要候选/机制 | 已知边界 | 下一触发条件 |
|----|------|--------|---------|-------------|---------|------------|
| C01 | 故事发动机 | M1 | 无（oh-story 方法适配间接涉及） | oh-story、Apodictic、AINWA、autonovel | 无实测数据 | 真实创作中故事发动机不足时 |
| C02 | 人物声音 | M2 | 无（cw-skills G2 间接相关） | cw-skills Character Sim、oh-story dialogue | 无实测数据 | B01 人物声音专项启动时 |
| C03 | 人物心理 | M1 | 无（B02 R2A M2 方向性信号但未直接测试） | Apodictic character arch、cw-skills Character Sim | B02 R2A M2 强正向但不普遍 | 真实创作中人物变工具人时 |
| C04 | 情绪传递 | **M3** | **有**：B02 R2A M2 | M2 人物特异性反应机制 | 仅 2 任务×2 重复；不进 M4/M5 | 真实创作出现情绪传递瓶颈时 |
| C05 | 关系状态 | M1 | 无（cw-skills G2 间接） | Apodictic、cw-skills、oh-story | 无实测数据 | 嵌入对话/场景专项 |
| C06 | POV/叙述距离 | M2 | 无（Apodictic 架构审阅） | Apodictic、后续文学蒸馏 | 无实测数据 | B03 专项启动时 |
| C07 | 人物化微动作 | M2 | 无（Apodictic 架构审阅） | Apodictic somatic mode | 核心模型尚未实测 | B04 专项启动时 |
| C08 | 对话/潜台词 | M2 | **有**：B09-K2 方向性 + B02 R1 G1 | oh-story G1、cw-skills G2、B09-K2 | 设计过密；需减法约束 | B05 对话专项启动时 |
| C09 | Scene Turn | M2 | **有**：B09-K1 方向性 | Apodictic scene/sequel、B09-K1 | 适合特定场景；不默认全启用 | B06 专项启动时 |
| C10 | 信息控制/悬念 | **M3（局部）** | **有**：B09-K3/K4 方向性 | B09-K3（轻规则）、B09-K4 | 仅 K3/K4 局部方向；各 1 个 Smoke Test；不进 M4 | 悬念/智斗专项继续验证 |
| C11 | 连载留存 | M1 | 无（oh-story B09 间接） | oh-story、中文网文蒸馏 | 存在压缩纪律和模板化风险 | 人物/情绪稳定后开专项 |
| C12 | Reader Sim | M2 | 无 | cw-skills Reader Sim、autonovel reader_panel | 须与真人反馈做预测对照 | B07 专项启动时 |
| C13 | Character Sim | M1 | 无 | cw-skills Character Sim、Apodictic | 无实测数据 | B02/B01 后单独验证 |
| C14 | 中文自然度 | M1 | 无（oh-story B09 间接） | oh-story deslop/voice、cw-skills style | 不能只靠禁词表 | B10 专项启动时 |
| C15 | 文学功能 | M1 | 无 | Apodictic、世界文学蒸馏 | 无实测数据 | 人物/场景基础稳定后 |
| C16 | 世界质感 | M0-M1 | 无 | Apodictic worldbuilding、世界文学蒸馏 | 候选覆盖最弱 | 后续从场景与人物行为切入 |
| C17 | Canon/Memory | M1 | 无 | NovelClaw、NovelForge、InkOS、AINWA、AuthorAgent 等 | **7 候选全部代码/架构审阅，无实测；候选丰富≠验证充分** | B08 专项启动时 |
| C18 | 修订/诊断 | M1 | 无 | Apodictic、cw-skills Critic/Editor、oh-story review | 无实测数据 | 与每个专项共用；真实创作暴露需求时 |
| C19 | 原著蒸馏/能力发现 | **M4（方法论层）** | **有**：B09 R01 正式 + R02A 轻量 | ani-book evidence-first、oh-story story-long-analyze、D0 | **M4 只指蒸馏方法论；BookDistill 生产工具尚未实现，不是 M5** | 真实蒸馏暴露问题时 |
| C20 | 工作流/Controller | M1 | 无 | InkOS、NovelForge、AINWA、AuthorAgent、NovelClaw | 6 候选全部代码/架构审阅 | 后期组合层；底层能力验证后 |

## 五、关键说明

### 项目整体 ≠ 方法适配

12 个重点上游项目中，**0 个项目整体原样运行**。以下项目的方法/机制适配进入过正式 Runner：

| 项目 | 适配记录 | 执行状态 | 证据关系 |
|------|---------|---------|---------|
| oh-story | B09 R01 Runner A（story-long-analyze 方法适配） | 正式实测（12 run） | 间接（测蒸馏质量） |
| oh-story | B02 R1 G1 注入（7 条规则机制子集） | 正式实测（9 run 中 3 cell） | 直接（测情绪传递） |
| ani-book | B09 R01 Runner B（evidence-first 方法适配） | 正式实测（12 run） | 直接（测蒸馏能力） |
| cw-skills | B02 R1 G2 注入（8 条规则机制子集） | 正式实测（9 run 中 3 cell） | 直接（测情绪传递） |

**方法适配被正式测试 ≠ 整个项目所有能力已验证。** 不得扩大归因。

### B09 Round02A 归因

Round02A 测试的是从 Round01 抽象出的 K1–K4 候选能力迁移（4 原创任务 × Control/Treatment = 8 run），不是 ani-book 或 oh-story 项目直接参赛。

### Apodictic 特殊说明

Apodictic 在 B02 冻结适配中被详细审阅（Meaning Pipeline、Wound/Lie/Want/Need、relational charge、somatic mode 等），但**机制未进入任何 Runner**。全部能力停留代码/架构审阅级别。未参赛 ≠ 失败；仍是 C03/C04/C06/C09/C15/C18 的高价值诊断候选。

### B09-K1/K2/K3/K4 定位

四项方向性候选机制（来自 B09 Round02A 轻量实测），不是已验证能力：

- K1 可计算风险系统 → C09 场景因果/风险专项
- K2 外部约束改变表达形式 → C08 对话/潜台词
- K3 主动诱发式信息获取 → C10 调查/智斗轻规则
- K4 可逆证据与竞争性解释 → C10 悬念/伏笔

仍不进入 `04_写作知识库` 正式层；未来在对应专项中与新的 GitHub 候选共同验证。

### 后续验证原则

真实蒸馏/创作暴露瓶颈 → 定位能力地图 → 优先调用已有候选 → 最小真实任务测试 → 作者快速判断 → 必要时才升级严格 Benchmark。

严格 Benchmark 只用于：机制可能成为长期核心能力 + 现有证据矛盾或易误判 + 错误固化代价高。

## 六、当前明确不做

- 不批量蒸馏现有全部原著。
- 不整体启动 B09 Round02B。
- 不因 AGPL / CC BY-NC-SA 自动排除高价值候选。
- 不在工作流未稳定前投入本地模型部署工程。
- 不把"候选池中存在"写成"已经实测验证"。
