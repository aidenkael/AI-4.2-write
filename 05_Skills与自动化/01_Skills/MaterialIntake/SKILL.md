# MaterialIntake（MI）Skill

版本：0.1.0
能力状态：CATALOG_FOUNDATION_AVAILABLE

## 目标

把 `01_原始素材` 的第三方原著以**只读方式**建立机器 canonical ledger（`素材资产.json`），并生成
GitHub 人类视图（`素材总索引.md`）与本地 preview CSV。MI 只负责「资产登记与状态推导」，
不移动原著、不修改 legacy 素材清单、不触碰蒸馏/知识链路。

核心定位：**canonical ledger 是素材状态的唯一机器事实；其余视图（CSV / 索引 / preview）均为派生视图。**

## 输入与输出

### 输入（全部只读，绝不修改）

- `01_原始素材/素材清单.csv` —— legacy 22 列清单（Phase 2B 前仍是 migration input，本 Skill 只读）。
- `01_原始素材` 磁盘全量扫描（逐文件 SHA256，排除 `collection_manifest.json`）。
- `02_原著蒸馏/<book_id>_*/bkp/identity.json` —— 正式 BKP 证据（`schema_status` 以 `FINALIZED` 开头
  才算可用）。
- `06_工作区/SourcePrepare/<book_id>/metadata.json` —— SP 提纯证据（SP 工作区清理后通常不存在）。
- 合集目录内 `collection_manifest.json`（Local Only）—— 容器证据，用于登记合集拆分。

### 输出

| 产物 | 位置 | 是否 tracked | 说明 |
|---|---|---|---|
| 素材资产.json | `01_原始素材/` | ✅ | canonical ledger，schema v1.0 |
| 素材总索引.md | `01_原始素材/` | ✅ | GitHub 人类视图（总览 + 三个分区表，不含 SHA/大小/文件名等敏感易变字段） |
| 素材清单_v1_preview.csv | `%TEMP%/` | ❌ | 9 列 preview，Excel 友好（utf-8-sig） |

## 关键语义（已实现）

### 类型初始化（bootstrap_type）

- `现代专业资料` → `RESEARCH`（当前 5 个）。
- 边界案例清单（含逗号名变体）→ `NEEDS_REVIEW`（当前 6 个）。
- 其余（网络小说 / 中文文学 / 外国文学普通作品）→ `REFERENCE_WORK`（当前 130 个）。

### 提纯状态推导优先级（A > B > C > D > E）

1. **A** SP `metadata.json` 存在且 SHA 匹配 → `可用`（evidence=`sourceprepare_metadata`）。
2. **B** BKP FINALIZED 且 `source_sha256` 在素材文件中 → `可用`（evidence=`bkp_source_snapshot`）。
3. **C** legacy CSV 的 SP 状态 → `可用/需复核/失败`（evidence=`legacy_catalog`）。
4. **D** 有 SHA 记录但不匹配 → `需更新`。
5. **E** 无任何证据 → `未处理`（evidence=`null`）。

### 知识状态推导

- 无 FINALIZED BKP → `未开始`。
- FINALIZED 且 `source_sha256` 匹配 → `可用`（含 `path="02_原著蒸馏/book_xxxx_xxx"` 与 `source_sha256`）。
- 否则 → `需更新`。

### 作者解析优先级

`CSV 作者列` > `BKP identity.book.author` > `文件名保守解析`（括号候选 + 噪声词过滤 +
单字拒绝 + 长度 ≤ 12 + 单候选才返回）> 空。

### 路径基准

- `assets[].files[].path`：相对 `01_原始素材/`（posix 风格）。
- `knowledge.path`：相对仓库根。
- `containers[].original.path`：相对 `01_原始素材/`。

### 确定性 / 幂等性

JSON 以 `sort_keys + ensure_ascii=False + indent=2 + 末尾换行` 写出；assets 按 id、files 按 path、
containers 按 id 排序；不含时间戳等 volatile 字段。**同一输入重复 build 产出 byte-for-byte 相同。**

## 运行方式

```bash
# 仓库根目录执行（默认 --root 为当前目录）
python "05_Skills与自动化/01_Skills/MaterialIntake/catalog.py" --root E:\AI-Write

# 测试（16 项，含真实数据端到端；真实扫描仅约 1.1s）
python -m pytest "05_Skills与自动化/01_Skills/MaterialIntake/test_catalog.py" -q
```

## 当前真实状态（build 时点）

- 141 assets（REFERENCE_WORK 130 / RESEARCH 5 / NEEDS_REVIEW 6）、182 files、1 container（马伯庸作品合集，21 splits）。
- purification：可用 3 / 未处理 138；knowledge：可用 3 / 未开始 138（book_0035/0038/0065 从真实 BKP 自动恢复）。
- author 非空 91/141。

## 未实现（Phase 2B 及以后，禁止臆造）

- legacy 22 列 CSV 的 cutover（以 ledger 取代 CSV 成为主输入）。
- 增量入库（新素材 → 登记 → 状态跟踪）。
- 资产变更审计 / 历史版本化 / diff 报告。
- 原著文件移动、重命名、去重。
- 与 BookDistill / KnowledgeRetrieve 的状态联动（当前只单向读 BKP 证据）。
