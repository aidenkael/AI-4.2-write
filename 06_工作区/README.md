# 06_工作区

可删除、可重建的临时运行与开发空间。

## 放什么

- 当前运行中的临时产物
- SourcePrepare / MethodPrepare 提纯输出（运行时自动创建 `SourcePrepare/` / `MethodPrepare/` 子目录；可重建的真实 Markdown）
- BookDistill / MethodDistill 的 **request-scoped 蒸馏 staging**（`BookDistill/` / `MethodDistill/` 子目录）：Agent 只写此处，定稿后受控发布到 02；未定稿/失败/取消产物留此供诊断，绝不可检索
- 应用开发临时产物（`应用开发/` 子目录：UI、接口、pywebview、Agent 接入等）
- 实验过程中的中间结果

以上运行产物均 **Local Only（已 `.gitignore`）、可删除、可重建**；不是长期资产。

## 不放什么

- 任何需要长期保存的资产
- 原始素材（→ 01）
- BKP / 蒸馏成果（→ 02）
- 原创正文（→ 03）
- 验证过的写作知识（→ 04）

## 任务结束清理规则

运行结束后按以下路由归档：

| 产物类型 | 去向 |
|---|---|
| 原始来源 | → 01_原始素材 |
| 单书知识（BKP） | → 02_素材知识库 |
| 原创长期资产 | → 03_作品工程 |
| 高成熟知识 | → 04_写作知识库 |
| 正式能力 | → 05_Skills与自动化 |
| 其他 | 删除 |

## Prepare / 蒸馏运行时目录

- `SourcePrepare/<作品ID>_<作品>/`（full.md + chapters/ + metadata.json）与 `MethodPrepare/<asset>_<名称>/`（full.md + sections/ + metadata.json）是提纯真实 Markdown 产物；「已提纯」当且仅当当前包存在且与当前来源指纹匹配。任务结束后可清除（已定稿知识包不依赖它仍可检索）。
- `BookDistill/<request_id>_<asset>_<名称>/` 与 `MethodDistill/<request_id>_<asset>_<名称>/` 是请求级蒸馏 staging；定稿受控发布到 02 后可清理。`BookDistill/_incomplete_recovery/` 存放从 02 移出的可证明未定稿 runtime 残留（不删除、不可检索）。

## 应用开发（06_工作区/应用开发/）

UI、接口、pywebview、Agent 接入等**临时开发产物**放在 `06_工作区/应用开发/`：

- 已加入 `.gitignore`，Local Only，不上传 GitHub
- 正式代码（含 `07_工作台应用`）**禁止依赖**此目录中任何文件
- 不建立“01待处理 / 02处理中 / 03完成”式持久开发流水线

## Agent 操作规则

- 任何内容默认临时
- 不建立持久化的流水线子目录（01_待处理、02_格式转换等）
- 需要时 runtime 自己临时创建，任务结束清除
