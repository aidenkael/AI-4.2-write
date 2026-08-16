# 01_原始素材

> 未经 AI 加工的原始来源。`素材资产.json` 是本目录的 **canonical ledger**（唯一真源）；
> `素材清单.csv` / `素材总索引.md` 是其 derived 视图，由 `MaterialIntake/catalog.py` 自动重建。

## 目录布局（Phase 2C1.2 legacy cleanup 完成）

| 目录 | 角色 |
|---|---|
| `00_待入库/` | **作者投放新素材的唯一 inbox**。MaterialIntake 从这里 scan / 去重 / 生成 intake plan |
| `01_参考作品/` | `REFERENCE_WORK` 资产 |
| `02_研究资料/` | `RESEARCH` 资产 |
| `03_零散素材/` | `LOOSE_MATERIAL` 资产 |

旧六分类目录（`01_网络小说` / `02_中文文学` / `03_外国文学` / `04_现代专业资料` / `05_其他参考资料` 等）已在 Phase 2C1.2 全部清理。
新入库资产一律走 `00_待入库` → 角色型目录。

**Phase 2C2（`02_原著蒸馏 → 02_素材知识库` 目录重命名）尚未执行。**

## Git 安全

- 原著正文 / 版权源文件（`*.epub` `*.txt` `*.pdf` `*.mobi` `*.azw3` `*.zip`）**Local Only，不上传 GitHub**（`.gitignore` 全局忽略）。
- 本目录可同步的 tracked 文件仅限：`素材资产.json` / `素材清单.csv` / `素材总索引.md` / `README.md` / `.gitkeep`。
