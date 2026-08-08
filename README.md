# AI-Write 项目说明（目录使用说明）

> 本文件是项目目录与协作规则的权威说明。详细准则见 [`目录规范.md`](目录规范.md)；
> 原始素材的 GitHub 可见索引见 [`00_项目控制/原始素材总索引.md`](00_项目控制/原始素材总索引.md)。

## 这是什么

AI-Write 是一个“把第三方原著标准化 → 蒸馏为写作模型 → 用于作品工程”的协作项目。
核心约束：**第三方原著全文只在本地保留（Local Only），GitHub 上只放索引与可协作的知识产物。**

## 顶层目录（8 个，冻结，不擅自新增）

| 目录 | 作用 | 是否上传 GitHub |
|---|---|---|
| `00_项目控制` | 索引、规范、报告、跨作品控制文件 | ✅ 索引/规范上传（不含第三方全文） |
| `01_原始素材` | 第三方原著全文（6 大分类） | ❌ **Local Only**，仅二进制被 gitignore |
| `02_原著蒸馏` | BookDistill 产出的单书写作模型 | ✅ 可协作知识产物 |
| `03_作品工程` | 具体作品的写作工程 | ✅ |
| `04_写作知识库` | 写作方法、优秀案例、古今制度转换等 | ✅ |
| `05_Skills与自动化` | Skills、脚本、工具（pandoc 等本地大文件 gitignored） | ✅ Skill/脚本上传 |
| `06_工作区` | Agent 中间状态（含 SourcePrepare 输出） | ❌ **Local Only**，整体 gitignore |
| `99_归档` | 归档 | 视情况 |

## 原始素材的 6 大分类（在 `01_原始素材/` 下）

1. `01_网络小说`
2. `02_中文文学`
3. `03_外国文学`
4. `04_历史与古代资料`
5. `05_现代专业资料` ← 非书籍类专业资料，SourcePrepare 标记 `NOT_APPLICABLE`
6. `06_其他参考资料`（含 `00_待核验` 子目录，待人工归类）

每部作品一个物理目录：`<分类>/<作品>/`，目录内直接放源文件（EPUB/TXT/PDF），
**不再嵌套 `00_原始文件`**。每部作品有稳定 ID `book_XXXX`（见索引）。

## 数据流向

```text
01_原始素材 ──(SourcePrepare, 只读)──> 06_工作区/SourcePrepare/<ID>_<作品>/
                                            │ full.md / chapters/
                                            ▼ (仅读 PASS)
                                        BookDistill
                                            ▼
                                      02_原著蒸馏/<ID>_<作品>/
                                            ▼
                                      03_作品工程
```

## GitHub 上传规则（务必遵守）

- **上传**：索引（`00_项目控制/原始素材清单.csv`、`00_项目控制/原始素材总索引.md`）、
  规范与说明、Skill/脚本（`05_Skills与自动化/` 下，除 pandoc 等本地大文件）、
  蒸馏产物（`02_原著蒸馏/`）、写作知识库（`04_写作知识库/`）。
- **不上传**：第三方原著全文（`01_原始素材/**/*.{epub,txt,zip,pdf,azw3,mobi}`）、
  Agent 中间产物（`06_工作区/**`，含 SourcePrepare 的 `full.md`/`chapters`）。
- 上述排除已由 `.gitignore` 覆盖；索引文件**不**在其中，会被正常提交。

## 索引（GitHub 可见的素材真相）

- `00_项目控制/原始素材清单.csv`：给 Agent / 自动化，一部作品可对应多条文件记录，
  含作品ID、作者、格式、SHA256、是否主来源、SourcePrepare 状态等 21 列。
- `00_项目控制/原始素材总索引.md`：给人阅读，按分类列出作品与状态。
- 运行 SourcePrepare 后，索引会被**自动回写**（状态/字符数/章节数）。

## 快速开始

```powershell
# 1) 预览 SP 会发现哪些作品（不转换、不写索引）
python "05_Skills与自动化/01_Skills/SourcePrepare/scripts/source_prepare.py" `
  --root "E:\AI-Write" --all --dry-run

# 2) 处理单部作品（Local Only，不改原始素材）
python "05_Skills与自动化/01_Skills/SourcePrepare/scripts/source_prepare.py" `
  --root "E:\AI-Write" --book "一九八四"

# 3) 重新生成索引（如需）
python "05_Skills与自动化/01_Skills/SourcePrepare/scripts/index_builder.py" `
  --root "E:\AI-Write"
```

详细 Skill 行为见 `05_Skills与自动化/01_Skills/SourcePrepare/SKILL.md`；
BookDistill 接口约定见 `05_Skills与自动化/01_Skills/BookDistill/SKILL.md`。
