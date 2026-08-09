# SourcePrepare 回收来源记录

## 来源

- **分支**：`skill/source-prepare-v1`
- **分支 HEAD**：`bee2ec7`（SourcePrepare：将 4 本残留 0.2.0 的书籍索引版本统一为 0.2.1）
- **merge-base**：`f6c1da1c`
- **分支独有 commit 数**：14（相对 main `69ee87a`）
- **回收日期**：2026-08-10

## 回收文件

| 文件 | 来源 | 说明 |
|------|------|------|
| `SKILL.md` | 分支 bee2ec7 | SP v0.2.1 完整规范 |
| `scripts/source_prepare.py` | 分支 bee2ec7 | SP 核心实现（896 行） |
| `scripts/epub_collection_split.py` | 分支 bee2ec7 | 合集 EPUB 拆分工具 |
| `scripts/test_collection_support.py` | 分支 bee2ec7 | 合集支持验证测试 |
| `scripts/index_builder.py` | 本地 untracked | 本地版本含 write_md() 缩进 bug 修复（分支版 `lines +=` 在 `continue` 后为死代码） |
| `scripts/import_new_materials.py` | 本地 untracked | 本地独有的新素材入库脚本，分支无此文件 |

## 未吸收的分支内容

以下内容明确没有吸收到 main：

- 分支中的旧目录重构 commit（04_写作知识库 8 分类改造、素材入库操作等）
- `BookDistill/SKILL.md`（仅接口草案，未实现；保留在分支中，后续如需可放 `06_工作区/Skill研发/`）
- 分支中的 `00_项目控制` 文件修改（AGENTS.md、入库报告等已由 main 独立维护）
- 分支中的 README / 知识库空目录等无关结构

## 本地修正说明

`index_builder.py` 本地版本与分支版本有 1 处差异：

- `write_md()` 函数中 `lines +=` 的缩进位置。分支版错误地将其放在 `continue` 之后（死代码，永远不会执行），
  本地版本修正为正确的 `for` 循环体缩进。这是一个真实 bug 修复，因此选择本地版本。
