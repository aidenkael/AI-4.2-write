# MethodDistill

方法/技巧资料（`METHOD_SOURCE`）的方法知识蒸馏：从 MethodPrepare PASS 包抽取
来源绑定的可迁移方法知识，产出可被统一 KnowledgeRetrieve 检索的方法知识包。

`METHOD_DISTILL = AVAILABLE`（2026-08-27 上线）

**这不是 BookDistill 换标签**：语义抽取合同是方法取向的（原则 / 诊断 / 程序 /
检查单 / 失效模式），定稿合同面向可追溯方法卡。

## 职责链

```text
06_工作区/MethodPrepare/<asset>_<名称>/（必须 PASS）
  → validate（确定性）→ prepare（确定性脚手架）
  → Agent 语义抽取（复用现有 Settings Direct/Interactive 任务设施，不建第二套 runtime）
  → finalize（确定性定稿）
  → 02_素材知识库/<asset>_<名称>/method/
```

## 输出

```text
02_素材知识库/<asset>_<名称>/method/
├─ identity.json          gowrite_method_knowledge/v1
├─ method_profile.md      身份 / 方法取向 / 覆盖 / 边界（Agent 填写）
├─ evidence.md            精选证据（Agent 填写）
├─ distill_manifest.json  定稿清单（finalize 写入）
└─ knowledge/
   └─ cards.md            规范方法卡（M0001…，Agent 填写，finalize 严格校验）
```

`identity.json` 最小语义：

```text
schema_version = gowrite_method_knowledge/v1
schema_status  = FINALIZED_RETRIEVAL_READY（只在确定性定稿全部通过后写入）
source_kind    = method_source
source_id      = canonical 素材资产 id
title / author
source_snapshot = 选中来源 SHA256 + MethodPrepare 指纹
maturity       = source_bound
```

## 方法卡合同（knowledge/cards.md）

```text
## M0001｜卡片标题
- statement: 一句话方法陈述（非空）
- method_kind: principle | diagnostic | procedure | checklist | failure_mode
- dimension / conditions / scope / boundary / confidence(高|中|低)
- steps[] / checks[] / failure_modes[]     （仅原书明确给出时填写，绝不外推）
- use_stages[] / problem_types[] / tags[]
- evidence:                                （必须真实指向 MethodPrepare 节/行）
  - sections/S0001.md#L3-L12
- capability_candidate: true | false
```

抽取什么：原书**明确教授**的原理、适用条件、决策条件、程序、检查单、失效模式、
示例/反例蕴含的边界。区分原书主张（source claim）与 Go Write 已验证真理。

## 确定性定稿（唯一写 `FINALIZED_RETRIEVAL_READY` 的路径）

全部机械可判定；任一不满足即拒绝并保持可重试：

- 输入必须是 MethodPrepare `PASS` 包（validate 门）；
- 拒绝重复卡 id / 空 statement / 非法 method_kind / 非法 confidence；
- 拒绝断裂证据引用（格式必须 `sections/S####.md#Lx-Ly` 且分节存在、行号在界内）；
- 拒绝过期来源指纹（来源 SHA / MethodPrepare 内容指纹与当前不一致）；
- 拒绝仍是模板/空的知识卡；
- 拒绝统一 KnowledgeRetrieve 方法加载器无法机械解析的包（加载失败回滚为 DRAFT）。

## 检索集成

- 只有 `FINALIZED_RETRIEVAL_READY` 包进入 `KnowledgeRetrieve` 的 `method_source` 来源；
  DRAFT 包不可检索（发现门控）。
- 命中使用统一身份：`selection_ref = method_source/<source_id>/<卡 id>`。

## Post-action

- 复用 `MaterialIntake/post_action.py`（无新 Git 机制）：只提交当前资产的
  `02_素材知识库/<asset>_<名称>/method/` 子树 + 三份 material state files；
- 定稿 + 目录刷新成功后，素材 `knowledge.status = 可用` → 作者面 `writing_callable = true`；
- Git 失败不回滚已完成的定稿（保留现场人工处理）。

## 硬边界

- `capability_candidate = true` 仅表示“潜在可执行的方法知识”：绝不自动创建/晋升
  `05_Skills与自动化` 下任何 Skill；05 Skill 晋升是独立的、证据/测试驱动的人工过程。
- 方法源绝不自动进入 `04_写作知识库`；04 需要显式的 `FINALIZED_VALIDATED` 验证包。
- 输出是来源绑定知识（`maturity = source_bound`），不是已验证普适真理；
  不得写入或覆盖任何项目 Canon / Story State。

## 运行方式（确定性阶段）

```bash
python 05_Skills与自动化/01_Skills/MethodDistill/method_distill.py validate --input <mp_dir>
python 05_Skills与自动化/01_Skills/MethodDistill/method_distill.py prepare  --input <mp_dir> --output <method_dir>
python 05_Skills与自动化/01_Skills/MethodDistill/method_distill.py finalize --input <mp_dir> --output <method_dir>
```

生产路径由 `07_工作台应用` 后端 `materials.distill_material(asset_id)` 按类型分派；
测试：`test_method_distill.py`（输入门 / 重复 id / 空 statement / 非法 kind /
断裂证据 / 过期指纹 / 模板拒绝 / 检索可加载 / 混合多源检索 / 05 零写入）。
