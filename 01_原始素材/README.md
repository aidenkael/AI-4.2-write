# 01_原始素材

> 未经 AI 加工的原始来源。`素材资产.json` 是本目录的 **canonical ledger**（唯一真源）；
> `素材清单.csv` / `素材总索引.md` 是其 derived 视图，由 `MaterialIntake/catalog.py` 自动重建。

## 目录布局（三种作者类型 ↔ 角色目录）

| 目录 | 角色 | 作者类型 |
|---|---|---|
| `00_待入库/` | **作者投放新素材的唯一 inbox**。MaterialIntake 从这里 scan / 去重 / 机械入库 | — |
| `01_原著/` | 原著（参考作品） | `REFERENCE_WORK` |
| `02_技巧类/` | 技巧类（写作/编剧/叙事方法资料） | `METHOD_SOURCE` |
| `03_其他/` | 其他（登记后退出提纯/蒸馏链） | `LOOSE_MATERIAL` |

硬不变量：**Workbench 类型 == canonical ledger 类型 == 物理角色目录含义**。

- `RESEARCH` 不再是作者可创建的普通类型；历史 `RESEARCH` 记录确定性归入 `LOOSE_MATERIAL / 03_其他`。
- `NEEDS_REVIEW` 不是作者分类：不支持的收件箱文件留在 `00_待入库`，绝不创建 canonical 资产。
- 旧六分类目录已在 Phase 2C1.2 全部清理；`01_参考作品 / 02_研究资料 / 03_零散素材` 已重命名为上表三角色目录。

## 作者的两个交互面：Workbench 与文件夹

- **Workbench**：导入 `EPUB/PDF/TXT` → `00_待入库` → 选批次类型（原著/技巧类/其他）→「入库」（确定性 intake，**不自动提纯**）；原著/技巧类入库后为「待提纯」，作者在详情里逐本显式「提纯」。
- **文件夹**：作者可直接在 Explorer 移动/改名/新建素材文件夹。这些手动编辑**只在点「刷新状态」时**由 MaterialIntake reconcile 按**精确内容身份**并入 canonical ledger（manual sync unit = 一个素材文件夹）：保留 asset id、更新路径/类型/名称；歧义或重复身份 fail closed（不写盘）；来源缺失保留登记为可读 attention，绝不静默删除。无实时文件监听。

## Git 安全

- 原著正文 / 版权源文件（`*.epub` `*.txt` `*.pdf` `*.mobi` `*.azw3` `*.zip`）**Local Only，不上传 GitHub**（`.gitignore` 全局忽略）。
- 本目录可同步的 tracked 文件仅限：`素材资产.json` / `素材清单.csv` / `素材总索引.md` / `README.md` / `.gitkeep`。
- **Workbench 素材操作（入库 / 刷新 / 提纯 / 蒸馏结算）不依赖 Git 干净度**：不做 precheck / fetch / commit / push，不因 `DIRTY_WORKTREE` / 分支 / 远端状态失败；提交由作者在检查点显式完成。CLI 维护命令仍可显式支持 Git sync。
