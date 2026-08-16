# MaterialIntake（MI）Skill

版本：0.3.0（Phase 2B2：inbox intake + post-action writeback）
能力状态：CANONICAL_CATALOG_AVAILABLE + INTAKE_AND_WRITEBACK_AVAILABLE

## 目标

`01_原始素材/素材资产.json` 是**唯一 canonical material registry**（tracked）。MI 负责：
- 加载 ledger（schema 校验）→ 校验磁盘 registered files → 读取 SP/BKP 证据
- 刷新机器事实（files SHA）与 derived status（purification / knowledge）
- 保存 ledger → 生成 `素材清单.csv`（9 列 derived author view）→ 生成 `素材总索引.md`（derived human view）

MI 负责「资产登记与状态推导」+「新素材入库（inbox intake）」+「Post-Action git writeback」；
不触碰蒸馏/知识链路（蒸馏由 BookDistill 负责，knowledge 状态由 refresh 自动推导）。
**默认运行不读取 legacy 22 列 CSV；CSV / MD 永远从 ledger 派生，禁止反向生成 ledger。**

## 输入与输出

### 输入（全部只读，绝不修改）

- `01_原始素材/素材资产.json` —— **唯一 canonical 输入**（Phase 2B1 cutover 完成，legacy CSV 已退出输入链）。
- `01_原始素材` 磁盘全量扫描（逐文件 SHA256，排除 `collection_manifest.json`）。
- `02_原著蒸馏/<book_id>_*/bkp/identity.json` —— 正式 BKP 证据（`schema_status` 以 `FINALIZED` 开头才算可用）。
- `06_工作区/SourcePrepare/<book_id>_<书名>/metadata.json` —— SP 提纯证据（A 级证据，SP 正式合同路径；
  工作区清理后通常不存在）。目录名前缀 `<book_id>_` 必须恰好匹配 1 个目录，多目录直接报歧义错误。

### 输出

| 产物 | 位置 | 是否 tracked | 说明 |
|---|---|---|---|
| 素材资产.json | `01_原始素材/` | ✅ | canonical ledger，schema v1.0 |
| 素材清单.csv | `01_原始素材/` | ✅ | 9 列 derived author view（素材ID/名称/类型/作者/标签/位置/提纯/知识/备注） |
| 素材总索引.md | `01_原始素材/` | ✅ | GitHub 人类视图（总览 + 分区表，不含 SHA/大小/文件名等敏感易变字段） |

## 运行模型（Phase 2B1，默认）

```
素材资产.json
    ↓ load + schema validation（schema_version / assets / containers）
    ↓ 验证磁盘 registered files（MISSING_REGISTERED_FILE → 停止且不写盘）
    ↓ 读取 SourcePrepare / BKP evidence
    ↓ 刷新机器事实（files SHA）与 derived status（purification / knowledge）
    ↓ 保存素材资产.json
    ↓ 生成素材清单.csv（9 列）→ 生成素材总索引.md
```

- **MISSING_REGISTERED_FILE**：registered path 在磁盘缺失 → FAIL/STOP（退出码 1），原 ledger 不被半写。
- **UNREGISTERED_FILE**：磁盘多出未登记文件 → 仅报告，不自动建 asset / 分类 / 分配 ID / 移动。
  已知系统文件（README.md / 素材资产.json / 素材清单.csv / 素材总索引.md / .gitkeep）不算未登记。
- **canonical 字段保留**：`id/name/type/author/tags/notes/files[].path/primary/source_container/container membership`
  不被文件名 / 旧分类 / AI 自动覆盖；`files[].sha256` 是机器事实快照，registered 存在则重算。
- **CLI**：`catalog.py --root E:/AI-Write`（refresh + render）与 `--check`（只校验不写盘）。
  legacy 22 列 → ledger 的 migration helper（`load_legacy_csv / build_assets / build_containers` 等）
  保留在 `catalog.py` 的 MIGRATION_ONLY 区，仅供测试 / 历史用，**绝不被 production 路径调用**。

## 关键语义（已实现）

### 类型

- `REFERENCE_WORK`（参考作品，当前 130）/ `RESEARCH`（研究资料，当前 5）/ `NEEDS_REVIEW`（待确认，当前 6）。
- `LOOSE_MATERIAL`（零散素材）Phase 2B2 起为正式枚举，路由到 `03_零散素材/`，
  提纯状态恒为「不适用」（refresh 强制，不退回「未处理」）。

### 提纯状态推导（Phase 2B1.1 持久化版：SP 证据 + ledger 持久 record）

优先级：
1. **当前 SourcePrepare metadata**（存在时）= 最新处理事实。`selected_source.sha256` 匹配素材文件时：
   `status=PASS → 可用`、`REVIEW → 需复核`、`FAIL → 失败`（evidence=`sourceprepare_metadata`）；
   `FAIL` 且无 `selected_source` → `失败`；`PASS/REVIEW` 缺 `sha256` / status 缺失或未知 → `需复核`；
   SHA 已不属于当前 asset → `需更新`（即使 status=PASS 也不标记可用）。
2. **已持久化 ledger purification record**（含 `input_fingerprint`）= 上一次已结算处理事实。
   当前素材 fingerprint == record fingerprint → 保持上次正式状态（可用/需复核/失败）；
   已变化 → `需更新`（evidence=`sourceprepare_record_input_changed`）。
3. **FINALIZED BKP** 且 `source_sha256` 在素材文件中 → `可用`（evidence=`bkp_source_snapshot`，
   可同时补写长期 record）；SHA 不匹配 → `需更新`。
4. **无任何证据** → `未处理`（evidence=`null`）。

持久化字段（canonical schema enrichment，schema_version 保持 1.0）：
- `source_sha256`：有 selected_source 时保存其 SHA；
- `input_fingerprint`：本次 SP 评估时 asset 全部 registered source files 的 SHA256 multiset
  fingerprint（全部 `sha256` 排序后整体取 SHA256，保留重复；与路径无关）。
不保存时间戳 / SourcePrepare 正文。

**fingerprint 语义（Phase 2B1.2）**：目录移动 / 文件改名 → fingerprint 不变，不导致 stale；
只有内容变化或来源文件集合变化（新增 / 删除 / 换版本）才导致 `需更新`。
Phase 2B1.1 旧算法（`path:sha256`）写入的 record 在内容未变时自动迁移为 content fingerprint，
状态与 `source_sha256` 不降级；迁移完成后仅使用 content fingerprint。

**06_工作区/SourcePrepare 删除后**：ledger 中已结算的提纯事实仍存在——fingerprint 匹配 → 稳定恢复
（可用/需复核/失败）；素材内容变化 → `需更新`（旧「可用」不覆盖已变化素材）。

### 知识状态推导

- 无 FINALIZED BKP → `未开始`。
- FINALIZED 且 `source_sha256` 匹配 → `可用`（含 `path="02_原著蒸馏/book_xxxx_xxx"` 与 `source_sha256`）。
- 否则 → `需更新`。

### 确定性 / 幂等性

JSON 以 `sort_keys + ensure_ascii=False + indent=2 + 末尾换行` 写出；assets 按 id、files 按 path、
containers 按 id 排序；不含时间戳等 volatile 字段。**同一输入重复 refresh/render 产出 byte-for-byte 相同**
（ledger / CSV / MD 三文件均幂等；真实数据验证 IDEMPOTENCY=True）。

## Inbox Intake（Phase 2B2 已实施）

`00_待入库/` 是唯一新素材入口；用户放入素材后 Agent 执行：

1. `intake.py scan` 输出 deterministic 事实（path / filename / sha256 /
   exact_duplicate_matches / possible_existing_candidates）；
2. **Agent 语义判断**：每文件判定 NEW_ASSET / ATTACH_EXISTING / REVIEW
   （runtime 不接 LLM、不硬编码分类字典、不做 fuzzy 自动合并）；
3. `intake.py apply --plan <plan.json>`：校验 → 移动（journal + SHA 校验）→
   ledger mutation → refresh 三视图 →（默认）post_action SAFE_COMMIT_PUSH。

规则：

- **EXACT_DUPLICATE** 三条件（重算 inbox SHA + canonical 已有同 SHA + canonical source 文件真实存在）
  全满足才删除 inbox 副本，否则 STOP 保留；
- **稳定 ID**：`book_XXXX` max+1（不补 gap、不复用删除 ID）；批量 NEW_ASSET 按 deterministic inbox path 排序分配；
- **NEW_ASSET 路由**：REFERENCE_WORK → `01_参考作品/`、RESEARCH → `02_研究资料/`、
  LOOSE_MATERIAL → `03_零散素材/`（safe_name，不建二级 taxonomy）；
- **ATTACH_EXISTING** 移到 primary source 所在目录、`primary=false` 默认；同一 asset 新版本 →
  purification 需更新、knowledge 保持可用（fingerprint 机制自动处理）；
- **REVIEW** 留 inbox 不分 ID；
- **collision**：同名不同 SHA → `<stem>__<sha前8位><suffix>`（绝不覆盖）；
- **rollback**：任何移动失败 → 逆序回滚已移动文件并清理新建空目录；失败输出 RECOVERY_REQUIRED；
- 初始状态：REFERENCE_WORK/RESEARCH = 未处理/未开始；LOOSE_MATERIAL = 不适用/未开始
  （refresh 强制尊重不适用，不退回未处理）。

## Post-Action Writeback（Phase 2B2 已实施）

`post_action.py` 提供 PRECHECK + SAFE_COMMIT_PUSH（MaterialIntake 动作默认自动执行）：

- **precheck**（动作开始前）：git repo / branch=main / fetch / HEAD==origin/main / porcelain 空；
- **safe_commit_push**（动作完成后）：fetch → remote 未前进 → allowlist diff → 精确 git add →
  commit → 普通 fast-forward push（commit message `chore: intake new materials`）；
- 绝不 merge / rebase / force / reset / restore / clean / pull；
- 远端前进 → `STOP_REMOTE_ADVANCED`（拒绝自动恢复）；allowlist 外 tracked 变更 →
  `STOP_UNEXPECTED_DIFF`；无变化 → `NO_TRACKED_CHANGES`（不造空 commit）；
- 第二道过滤：原始素材后缀（*.epub/*.txt/*.pdf/*.mobi/*.azw3/*.zip）、`06_工作区/SourcePrepare/`、
  `collection_manifest.json` 任何情况不 staging；
- `--no-git-sync` 跳过 git（仅测试/调试）；`01_原始素材` 下只放行三份 metadata + README + `.gitkeep`。

## 阶段边界（Phase 2B1/2B1.1 完成；Phase 2B2 inbox intake + writeback 完成）

- `素材资产.json` 是唯一 canonical 输入；legacy 22 列 CSV 已**正式退役为 derived 9 列视图**。
- 6 个 `NEEDS_REVIEW` 资产（马伯庸笑翻中国简史 / 殷商玛雅征服史 / 她死在QQ上 /
  事实证明，人民永远是最可爱的 / 明朝那些事儿 / 我读书少你可别骗我）不自动处理。
- Phase 2B1.1：提纯结果持久化进 ledger（`source_sha256` / `input_fingerprint`）；
  06_工作区 清理后已结算提纯事实不消失；container `original.path` 缺失 → MISSING 且不写盘。
- Phase 2B2：inbox intake 与 post-action writeback 已实施（见下节）；
  旧六分类目录保留为 LEGACY_PHYSICAL_LAYOUT（Phase 2C 再迁移）。

## 运行方式

```bash
# 仓库根目录执行
python "05_Skills与自动化/01_Skills/MaterialIntake/catalog.py" --root E:\AI-Write
python "05_Skills与自动化/01_Skills/MaterialIntake/catalog.py" --root E:\AI-Write --check

# inbox 扫描与入库（Phase 2B2）
python "05_Skills与自动化/01_Skills/MaterialIntake/intake.py" --root E:\AI-Write scan
python "05_Skills与自动化/01_Skills/MaterialIntake/intake.py" --root E:\AI-Write apply --plan <plan.json> [--no-git-sync]

# 测试（58 项：catalog 34 + intake 14 + post_action 10；真实扫描仅约 1s）
python -m pytest "05_Skills与自动化/01_Skills/MaterialIntake" -q
```

## 当前真实状态（Phase 2B1.1 时点）

- 141 assets（REFERENCE_WORK 130 / RESEARCH 5 / NEEDS_REVIEW 6）、182 files、1 container（马伯庸作品合集，21 splits）。
- purification：可用 3 / 未处理 138；knowledge：可用 3 / 未开始 138（book_0035/0038/0065 从真实 BKP 自动恢复，
  并补写长期 record：`source_sha256` + `input_fingerprint`）。
- 幂等验证：连续 refresh 两次 ledger/CSV/MD 三文件 byte-for-byte 不变；record 补写后 CSV/MD 零变化。

## 未实现（禁止臆造）

- 资产变更审计 / 历史版本化 / diff 报告。
- 素材语义分类自动化（intake 语义判断由 Agent 完成；runtime 不接 LLM、无分类字典）。
- 与 BookDistill / KnowledgeRetrieve 的状态联动（当前只单向读 BKP 证据；settlement 由 BookDistill SKILL 驱动）。
- Phase 2C：旧六分类目录物理迁移到新角色目录（当前保留 LEGACY_PHYSICAL_LAYOUT）。
