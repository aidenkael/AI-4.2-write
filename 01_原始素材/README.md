# 01_原始素材

未经 AI 加工的原始参考来源。

## 放什么

- 网络小说（epub / txt / pdf / mobi / azw3 / zip）
- 中文文学作品
- 外国文学作品（含中文译本）
- 历史与古代资料（非小说型）
- 现代专业资料
- 其他参考资料

## 目录中的机器工件（Phase 2B1 canonical cutover）

| 文件 | 角色 | 说明 |
|---|---|---|
| 素材资产.json | **canonical registry（唯一真源）** | MaterialIntake 维护：资产登记 + 机器事实（SHA）+ 状态推导 |
| 素材清单.csv | derived author view | 9 列（素材ID/名称/类型/作者/标签/位置/提纯/知识/备注），由 ledger 派生 |
| 素材总索引.md | derived human view | GitHub 总览，由 ledger 派生 |

> 禁止用 CSV / MD 反向生成 ledger；SourcePrepare 等下游只从 ledger 读取身份与候选来源。

## 不放什么

- AI 生成的分析、蒸馏结果、知识卡片（→ 02_原著蒸馏）
- 原创作品（→ 03_作品工程）
- 跨书验证后的写作知识（→ 04_写作知识库）
- SP 转换后的 Markdown 副本（→ 06_工作区/SourcePrepare）

## 目录结构

```
01_原始素材/
├── README.md
├── 素材资产.json      ← canonical（MaterialIntake 维护）
├── 素材总索引.md     ← 人类可读，自动生成
├── 素材清单.csv      ← 机器可读（9 列），自动生成
├── 01_网络小说/
├── 02_中文文学/
├── 03_外国文学/
├── 04_历史与古代资料/
├── 05_现代专业资料/
└── 06_其他参考资料/
```

## Agent 操作规则

- 不修改、不移动原始文件
- 新素材入库与登记由 MaterialIntake 负责（inbox intake 在 Phase 2B2）
- 分类由真实内容推动，不预建空目录
- 不手工编辑素材资产.json / 素材清单.csv / 素材总索引.md（均由工具生成）
