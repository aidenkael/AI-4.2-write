# SourcePrepare（SP）Skill

版本：0.1.0

## 目标

把 `01_原始素材` 中的第三方原著，以**只读方式**标准化为可供后续 `BookDistill` 使用的纯净 Markdown 工作副本。

SP 只负责“输入标准化”，不负责内容分析、总结、蒸馏、改写或润色。

## 输入与输出

输入位置：

- `01_原始素材/01_网络小说/<作品>/00_原始文件/`
- `01_原始素材/02_世界文学/<作品>/00_原始文件/`

当前直接支持：

- EPUB
- TXT
- PDF（仅有可提取文本层时）

ZIP 暂不作为 V0.1 的直接输入；如作品只剩 ZIP，应先人工确认其中是否有 EPUB/TXT/PDF，再进入后续版本处理。

输出位置：

`06_工作区/02_格式转换/<来源分类>/<作品>/`

标准输出：

```text
<作品>/
├─ full.md
├─ chapters/
│  ├─ 0001.md
│  ├─ 0002.md
│  └─ ...
├─ metadata.json
└─ conversion_report.md
```

其中 `full.md` 与 `chapters/*.md` 才是后续 BookDistill 的标准正文输入；`metadata.json` 与 `conversion_report.md` 只是溯源与质检记录。

## 核心原则

1. **原始素材只读。** 不覆盖、不重命名、不删除、不在 `01_原始素材` 内就地转换。
2. **机械转换优先。** EPUB 使用 Pandoc；TXT 只做编码转换与最小清理；PDF 只提取现有文本层。
3. **不使用大模型改写原文。** 不润色、不补句、不修正文风、不“智能纠错”。
4. **不自动 OCR。** PDF 无文本层时直接标记 FAIL/REVIEW，留给人工处理。
5. **多来源互相校验。** 同一作品有 EPUB/TXT/PDF 时全部评估，不因某个文件“能打开”就认定完整。
6. **输出必须可追溯。** 保存源文件路径、SHA256、格式、字符数、章节识别数、异常信息和最终选源理由。
7. **后续蒸馏只读取 PASS。** REVIEW 需要人工检查；FAIL 不得进入 BookDistill。

## 为什么不能只检查 EPUB“是否损坏”

EPUB 是容器格式。ZIP 能打开，不代表正文完整。SP 至少检查：

- 是否为有效 ZIP/EPUB 容器；
- `META-INF/container.xml` 是否存在；
- OPF 是否可定位；
- spine 是否非空；
- spine 引用正文是否大部分存在；
- Pandoc 是否实际转换成功；
- 转换后是否存在有效正文；
- 是否能识别合理章节边界；
- 与备用 TXT/PDF 的正文长度是否出现异常差异。

因此“结构合法”与“适合作为蒸馏输入”是两个不同判断。

## 来源选择规则

默认优先级不是简单地“EPUB 永远最好”，而是：

1. 先评估所有可用来源；
2. `PASS` 高于 `REVIEW`；
3. 同等质量下优先 EPUB，其次 TXT，再次 PDF；
4. 如 EPUB 结构正常但转换结果明显异常，而 TXT 完整，则使用 TXT；
5. 多来源正文长度差异过大时，不自动下结论，整体降为 REVIEW。

## 文本清理边界

允许：

- 转 UTF-8；
- 统一换行；
- 去 BOM；
- 清除纯图片 Markdown 行；
- 清除明显空 HTML 包装标签；
- 去行尾空格；
- 压缩异常连续空行；
- 根据章节标题拆分章节。

禁止：

- 改写原句；
- 修辞优化；
- AI 补全缺失文字；
- 根据语义擅自合并/删除段落；
- 自动删除认为“无用”的正文；
- 自动 OCR；
- 覆盖原始文件。

## 状态定义

### PASS

正文可正常提取，字符量基本正常，未发现明显乱码，可识别章节边界，且无严重跨来源异常。

### REVIEW

正文基本可用，但存在至少一种风险，例如：

- 无法可靠识别章节；
- EPUB/TXT/PDF 之间正文长度差异明显；
- 存在乱码迹象；
- PDF 排版噪音较重；
- 结构检查存在警告但仍可读取。

### FAIL

例如：

- EPUB 容器/OPF/spine 明显损坏；
- Pandoc 转换失败；
- TXT 无法可靠解码；
- PDF 无可用文本层；
- 转换后正文极少或为空。

## 推荐执行顺序

不要第一天直接 `--all`。

先测试三类样本：

1. 一部长篇网络小说，EPUB + TXT 都存在；
2. 一部世界文学；
3. 一部已知 EPUB 可疑或格式复杂的作品。

人工检查三本的：

- 开头；
- 中段；
- 结尾；
- 章节数量；
- EPUB 与 TXT 的差异；
- 是否有乱码、广告、缺章、顺序错乱。

三本通过后再允许批量执行。

## 调用方式

单书：

```powershell
python "05_Skills与自动化/01_Skills/SourcePrepare/scripts/source_prepare.py" `
  --root "D:\BaiduSyncdisk\AI-Wirte" `
  --book "官居一品"
```

全部作品：

```powershell
python "05_Skills与自动化/01_Skills/SourcePrepare/scripts/source_prepare.py" `
  --root "D:\BaiduSyncdisk\AI-Wirte" `
  --all
```

默认如果目标 `full.md` 已存在则跳过。只有明确需要重跑工作副本时使用 `--force`；`--force` 也永远不能覆盖原始素材。

## 与其他 Skill 的边界

```text
SourcePrepare
    ↓
标准 Markdown
    ↓
BookDistill
    ↓
单书完整写作模型
```

SP 不应该知道后续要研究“人物、节奏、爽点还是主题”；它只保证输入尽量完整、干净、可验证。
