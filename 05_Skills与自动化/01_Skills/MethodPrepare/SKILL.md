# MethodPrepare

方法/技巧资料（`METHOD_SOURCE`）的确定性预处理。把方法类非虚构来源标准化为
结构可寻址的 Markdown 包，供 MethodDistill 消费。

`METHOD_PREPARE = AVAILABLE`（2026-08-27 上线）

## 职责

- 输入：`素材资产.json` 中 `type == METHOD_SOURCE` 的资产（来源文件只读，绝不修改）。
- 输出：`06_工作区/MethodPrepare/<asset_id>_<名称>/`
  - `full.md`：归一化全文（保持原文档顺序）
  - `sections/S0001.md…`：行稳定的分节文件（下游证据寻址 `sections/S0001.md#Lx-Ly`）
  - `structure.json`：稳定节 id / 顺序 / 父级（仅真实已知时给出）
  - `metadata.json`：asset id / 选中来源 SHA256 / input_fingerprint / content_fingerprint /
    structure_fingerprint / 解析器身份 / `PASS|REVIEW|FAIL` / 分节数 / 限制清单
  - `conversion_report.md`：人类可读报告
- 产物属 `06_工作区`（Local Only：gitignore + post_action 第二道过滤绝不 staging）。

## 硬合同

1. **确定性**：无 LLM、无语义摘要、无改写、无 OCR；同输入重复运行产物逐字节一致。
2. **保真**：保留文档顺序；标题/列表/编号步骤/表格/引用/示例在可靠可得时保留。
3. **绝不虚构层级**：无法可靠恢复结构时保留线性内容并在 metadata/报告标注限制；
   限制重大时用 `REVIEW`，不用假 `PASS`。
4. **诚实失败**：坏编码 / 不支持格式 / 空内容 / 结构不可靠 → `REVIEW|FAIL`；
   来源 SHA 与台账不一致 → 拒绝运行。
5. **隔离**：不把 SourcePrepare 改造成多用途分支解析器，不改 SourcePrepare 生产行为；
   转换器是独立函数层（`convert_to_markdown` / `extract_structure`），
   未来可加 Docling 适配器而不改本输出合同。
6. **类型边界**：只处理 `METHOD_SOURCE`；参考作品请用 SourcePrepare。

## 支持来源与判定

| 来源 | 方式 | 失败时 |
|---|---|---|
| `.md` / `.markdown` | 直通 + 归一化 | 编码异常 → REVIEW |
| `.txt` | 多编码确定性解码（utf-8-sig/utf-8/gb18030/big5） | 不可解码 → REVIEW；无标题 → REVIEW（线性保留） |
| `.epub` | 仓库 Pandoc（epub → gfm） | Pandoc 缺失/转换失败 → REVIEW |
| `.pdf` | 仅文本层（pypdf / pdftotext） | 无文本层 → REVIEW（绝不 OCR） |
| 其他 | 不支持 | REVIEW（需人工确认） |

状态判定：转换成功且可见内容充足且检出真实标题结构 → `PASS`；
其余一律 `REVIEW`（含限制清单），转换层异常不产生假 `PASS`。

## 与 MaterialIntake 的结算关系

- 提纯状态由 `metadata.json` 推导（`catalog.find_mp_metadata`，evidence 前缀 `methodprepare_*`）：
  `PASS → 可用` / `REVIEW → 需复核` / `FAIL → 失败`；选中来源 SHA 不属于当前素材 → 需更新。
- 成功后（作者面「提纯」动作）刷新三份 material state files 并经 `post_action` 安全同步；
  Git 失败不回滚业务动作。

## 运行方式

```bash
python 05_Skills与自动化/01_Skills/MethodPrepare/scripts/method_prepare.py \
  --root E:/AI-Write --asset book_XXXX
```

生产路径由 `07_工作台应用` 后端 `materials.prepare_material(asset_id)` 按类型分派调用；
测试：`scripts/test_method_prepare.py`（tmp fixture：只读来源 / 确定性 / 稳定节 /
结构保留 / 不虚构层级 / 证据寻址 / 坏输入不假 PASS）。

## 禁止

- 不调用模型；不语义摘要；不改写原文；不 OCR。
- 不虚构标题层级；不把 `REVIEW` 结果包装成 `PASS`。
- 不写入 `01_原始素材` / `02_素材知识库` / `05_Skills与自动化`。
- 不新增根目录、不迁移已有素材目录。
