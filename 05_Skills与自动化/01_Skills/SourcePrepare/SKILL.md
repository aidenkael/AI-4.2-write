# SourcePrepare（SP）Skill

版本：0.2.1

## 目标

把 `01_原始素材` 中的第三方原著，以**只读方式**标准化为可供后续 `BookDistill` 使用的纯净 Markdown 工作副本。

SP 只负责“输入标准化”，不负责内容分析、总结、蒸馏、改写或润色。

## 输入与输出

### 输入（直接扫描作品目录根层，不依赖 00_原始文件）

SP 直接读取 `01_原始素材/<分类>/<作品>/` 下的全部源文件；不再要求源文件放在 `00_原始文件` 子目录内。

支持 6 大分类（目录名）：

- `01_网络小说`
- `02_中文文学`
- `03_外国文学`
- `04_历史与古代资料`
- `05_现代专业资料` ← **非书籍类专业资料，SP 标记 `NOT_APPLICABLE`，不转换**
- `06_其他参考资料`

支持的源格式：

- EPUB（用 Pandoc 转换）
- TXT（编码转换 + 最小清理）
- PDF（仅提取已有文本层；无文本层不自动 OCR；**依赖 `pypdf`（Python 包）或系统 `pdftotext`（poppler），二者皆无时标记 `FAIL`**）
- ZIP / AZW3 / MOBI 暂不支持自动转换，标记为 `FAIL` 并提示人工处理

`06_其他参考资料/00_待核验/` 中的素材尚未分类，SP 不自动处理，需人工先归类。

## 运行依赖

- **Pandoc**：EPUB 转换依赖 Pandoc。SP 优先使用 `05_Skills与自动化/pandoc/pandoc.exe`（已随 Skill 提供），找不到时才回退到系统 `PATH` 中的 `pandoc`。
- **PDF 文本提取**（可选）：仅当素材含 PDF 时才需要，二者满足其一即可：
  - Python 包 `pypdf`（`pip install pypdf`，已在本机托管 venv 安装）；或
  - 系统命令 `pdftotext`（poppler-utils）。
  - 若两者皆不可用，含 PDF 的作品会被标记 `FAIL`（不自动 OCR，留给人工处理），**不影响其他格式作品**正常转换。
- **`index_builder.py`**：与 `source_prepare.py` 同目录，SP 跑完每部作品后回写中央索引。

### 合集容器（一个目录含多部作品）

“合集/套装”原著（如单作者作品合集）在物理上只占一个目录，但含多部逻辑作品。SP 通过
`collection_manifest.json`（位于合集目录内，Local Only）识别其中的拆分单书，**不**把整个合集
当成一部作品：

- 合集目录内只有 manifest 列出的拆分单书会被登记为候选来源；原始合集 EPUB 等其余文件跳过。
- 每本拆分单书在 `原始素材清单.csv` 的**「来源容器」列**写入合集名（如 `马伯庸作品合集`），
  空值表示独立来源。
- 作品身份由 **`book_id` + 中央索引**决定，而**不是文件夹名**。因此同一作品若同时存在于
  旧目录（如 `01_网络小说/长安十二时辰/`）与合集拆分（`02_中文文学/马伯庸作品合集/长安十二时辰.epub`），
  SP 会靠 `book_id` 归并为同一作品，并一起评估、交叉校验全部候选来源。
- 拆分脚本：`05_Skills与自动化/01_Skills/SourcePrepare/scripts/epub_collection_split.py`。
  详细目录规则见 [`目录规范.md`](../../../目录规范.md) 原则 4。

### 输出（06_工作区，Local Only，不传 GitHub）

`06_工作区/SourcePrepare/<作品ID>_<作品>/`

> `<作品ID>` 是中央索引里的稳定 `book_XXXX`，同一作品的不同来源（不同目录、不同格式、合集拆分本）
> 都归到同一个 `<作品ID>`，不重复建目录。

```text
<作品ID>_<作品>/
├─ full.md              # 选源后的完整正文（BookDistill 标准输入）
├─ chapters/            # 按章节拆分（0000_前置内容.md 为卷首非章节内容）
│  ├─ 0001.md
│  ├─ 0002.md
│  └─ ...
├─ metadata.json        # 溯源与质检（含 14 项 EPUB 检测结果）
└─ conversion_report.md # 人类可读的转换报告
```

> `full.md` 与 `chapters/*.md` 是后续 BookDistill 的标准正文输入；
> `metadata.json` 与 `conversion_report.md` 只是溯源与质检记录。
> 这些文件都在 `06_工作区/**` 下，被 `.gitignore` 排除，**绝不上传 GitHub**。

## 核心原则

1. **原始素材只读。** 不覆盖、不重命名、不删除、不在 `01_原始素材` 内就地转换。
2. **机械转换优先。** EPUB 用 Pandoc；TXT 只做编码转换与最小清理；PDF 只提取现有文本层。
3. **不使用大模型改写原文。** 不润色、不补句、不修正文风、不“智能纠错”。
4. **不自动 OCR。** PDF 无文本层时直接标记 `FAIL`/`REVIEW`，留给人工处理。
5. **多来源互相校验。** 同一作品有 EPUB/TXT/PDF 时全部评估，不因某个文件“能打开”就认定完整。
6. **输出必须可追溯。** 保存源文件路径、SHA256、格式、字符数、章节识别数、异常信息和最终选源理由，并回写中央索引。
7. **后续蒸馏只读取 PASS。** `REVIEW` 需要人工检查；`FAIL` 不得进入 BookDistill；`NOT_APPLICABLE` 表示本 Skill 不适用。

## 来源选择规则：完整性 > 准确性 > 章节 > 格式

默认**不是**“EPUB 永远最好”，而是：

1. 先评估所有可用来源（有 `temp_md` 且非 `FAIL`）；
2. 先按**完整性**（可见字符数，越高越完整）排序；
3. 完整性接近时，按**准确性**（替换字符 `�` 越少越好）排序；
4. 再按**章节可识别数**排序；
5. 最后才用**格式**（EPUB > TXT > PDF）作为平局打破项；
6. **单 EPUB 只要通过质检即可 PASS**，不要求必须有 TXT 伴生；
7. 若某来源正文长度仅为最长来源的 70% 以下，标记“可能不完整”并降为 `REVIEW`；
8. 多来源正文长度差异 < 65% 时，整体记录交叉校验警告；
9. **近邻选源修正**：当两个候选正文长度差 ≤ 2%（即较短/较长 ≥ 98%）时，若较长来源为 `REVIEW` 且未识别章节（0 章），而另一来源为 `PASS` 且有章节，则优先选择 `PASS` + 有章节的来源（避免丢失分章、整体降级）。修正理由记录在选中来源的“单文件备注”，不因此把整体状态升为 `REVIEW`。

## EPUB 14 项质量检测

EPUB 是容器格式，ZIP 能打开 ≠ 正文完整。SP 对 EPUB 跑 14 项检测（结构 + 转换 + 正文质量），
结果写入 `conversion_report.md` 与 `metadata.json`：

| # | 检测项 | 严重度 |
|---|---|---|
| 1 | 有效 ZIP/EPUB 容器 | 关键 |
| 2 | mimetype 声明 `application/epub+zip` | 警告 |
| 3 | 含 `META-INF/container.xml` | 关键 |
| 4 | `container.xml` 指向有效 OPF | 关键 |
| 5 | OPF 文件可解析（XML well-formed） | 关键 |
| 6 | OPF 含 `dc:title` | 警告 |
| 7 | OPF 含 `dc:creator` | 警告 |
| 8 | manifest 清单非空 | 关键 |
| 9 | spine 阅读顺序非空 | 关键 |
| 10 | spine 可定位率 ≥ 80% | 关键 |
| 11 | 可定位正文文档 ≥ 1 | 关键 |
| 12 | 含 NCX / EPUB3 nav 导航 | 警告 |
| 13 | Pandoc EPUB→Markdown 转换执行成功 | 关键 |
| 14 | 转换后正文质量（可见字符 ≥ 5000 且无明显乱码） | 警告 |

任一“关键”项失败 → 该 EPUB 整体 `FAIL`。

## 文本清理边界

允许：转 UTF-8、统一换行、去 BOM、清除纯图片 Markdown 行、清除明显空 HTML 包装标签、
去行尾空格、压缩异常连续空行、根据章节标题拆分章节、识别 blockquote 形式的章号
（如 `> 五`、`> 第一部`）。

禁止：改写原句、修辞优化、AI 补全缺失文字、根据语义擅自合并/删除段落、
自动删除认为“无用”的正文、自动 OCR、覆盖原始文件。

## 状态定义

- **PASS**：正文可正常提取，字符量基本正常，无明显乱码，可识别章节边界，无严重跨来源异常。
- **REVIEW**：正文基本可用，但存在至少一种风险（无法可靠识别章节、跨来源长度差异明显、乱码迹象、PDF 噪音重、结构警告但仍可读取）。
- **FAIL**：EPUB 关键结构损坏 / Pandoc 失败 / TXT 无法解码 / PDF 无文本层 / 转换后正文极少或为空 / 格式不支持。
- **NOT_APPLICABLE**：非书籍类专业资料（`05_现代专业资料`），SP 不适用，不生成 `06_工作区` 输出。

## 推荐执行顺序（与本次目录改造一同确认）

不要第一天直接 `--all`。

1. 先用 `--dry-run` 确认作品发现、作品ID 解析、`NOT_APPLICABLE` 分类正确；
2. 选 1 部长篇单 EPUB 作品实测（确认新路径发现、单 EPUB 可 PASS、索引回写）；
3. 选 1 部已知可疑/损坏 EPUB 实测（确认 `FAIL` 路径与 14 项检测）；
4. 选 1 部多格式作品实测（确认交叉校验与选源）；
5. 三步通过后再允许批量执行（批量需另行授权，本轮禁止）。

## 调用方式

单书（支持作品名 **或** 作品ID；作品ID 能跨目录定位同一作品的全部候选来源）：

```powershell
python "05_Skills与自动化/01_Skills/SourcePrepare/scripts/source_prepare.py" `
  --root "E:\AI-Write" `
  --book "一九八四"

# 也可直接传 book_id（例如合集拆分本 + 旧目录单本都会命中 book_0035）
python "05_Skills与自动化/01_Skills/SourcePrepare/scripts/source_prepare.py" `
  --root "E:\AI-Write" `
  --book "book_0035"
```

静态预览（不转换、不写索引）：

```powershell
python "05_Skills与自动化/01_Skills/SourcePrepare/scripts/source_prepare.py" `
  --root "E:\AI-Write" --all --dry-run
```

> `--dry-run` 输出会显示每部作品的 `id`、格式与 **来源容器**（合集名或“独立来源”），
> 可据此确认合集拆分本与旧来源是否正确归并到同一 `book_id`。

全部作品（需另行授权）：

```powershell
python "05_Skills与自动化/01_Skills/SourcePrepare/scripts/source_prepare.py" `
  --root "E:\AI-Write" --all
```

默认如果目标 `full.md` 已存在则跳过。只有明确需要重跑工作副本时使用 `--force`；
`--force` 也永远不能覆盖原始素材。

## 索引自动回写

每跑完一部作品，SP 调用 `scripts/index_builder.py` 的 `update_book()`，
回写 `00_项目控制/原始素材清单.csv` 与 `原始素材总索引.md` 中该作品的：

`SourcePrepare状态 / SourcePrepare版本 / 标准MD字符数 / 识别章节数 / 最后检查时间 / 备注`。
（`来源容器` 列在 `index_builder.discover()` 阶段写入，SP 运行时不修改。）

> 索引 `原始素材清单.csv` 现共 22 列，新增「来源容器」列用于标记文件来自哪个合集。

`05_现代专业资料` 的作品会被直接标记为 `NOT_APPLICABLE`，不进入 `06_工作区`。

## 与其他 Skill 的边界

```text
SourcePrepare  (01_原始素材 -> 06_工作区/SourcePrepare/<ID>_<作品>/full.md)
    ↓
BookDistill    (读取 full.md / chapters -> 02_原著蒸馏)
    ↓
作品工程        (03_作品工程)
```

SP 不应该知道后续要研究“人物、节奏、爽点还是主题”；它只保证输入尽量完整、干净、可验证。
BookDistill 的接口约定见 `05_Skills与自动化/01_Skills/BookDistill/SKILL.md`。
