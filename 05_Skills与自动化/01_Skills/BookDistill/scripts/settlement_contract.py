# -*- coding: utf-8 -*-
"""BookDistill settlement contract（Phase 2B2 第 35-38/51 节）。

settlement 是 Agent 在 BKP FINALIZED + 全部验证通过后执行一次的收尾动作
（不改 book_distill.py runtime）：catalog refresh → knowledge 自动可用 →
CSV/MD 刷新 → post_action SAFE_COMMIT_PUSH。

本模块只定义 contract 常量与校验函数，供测试与 Agent 引用。

FINALIZED settlement 允许进 Git 的 tracked 面：
  - 02_原著蒸馏/<book_id>_<书名>/  整棵 distillation subtree（含 bkp/knowledge/meta）
  - 01_原始素材 三份 material state files（素材资产.json / 素材清单.csv / 素材总索引.md）

绝不进 settlement：
  - 01 原著全文与 raw 源文件（Local Only；三份 metadata 由 allowlist 精确放行）
  - 06_工作区/（SP/BD 工作副本，Local Only）
  - 其他作品目录（03_作品工程/ 等）
"""
from pathlib import Path

# settlement 可进 Git 的 tracked 面（目录项以 / 结尾 = 前缀；文件项 = 精确匹配）
BD_SETTLEMENT_ALLOW = [
    "02_原著蒸馏/",
    "01_原始素材/素材资产.json",
    "01_原始素材/素材清单.csv",
    "01_原始素材/素材总索引.md",
]

# 绝不进 settlement 的路径标记（第二道保护）
BD_NEVER_STAGE_MARKERS = ("06_工作区/",)

# 01_原始素材 下唯一允许的 metadata 文件名（raw 全文全部 Local Only）
MI_METADATA_NAMES = {"素材资产.json", "素材清单.csv", "素材总索引.md"}


def is_settlement_allowed(rel: str) -> bool:
    """rel（posix）是否属于 settlement 允许面。返回 True 才可 stage。"""
    rel = rel.replace("\\", "/").rstrip("/")
    for a in BD_SETTLEMENT_ALLOW:
        if a.endswith("/"):
            if rel == a.rstrip("/") or rel.startswith(a):
                return True
        elif rel == a:
            return True
    return False


def is_settlement_never_stage(rel: str) -> bool:
    """第二道过滤：06_工作区 与 01 原著全文（非三份 metadata）绝不 staging。"""
    rel = rel.replace("\\", "/")
    if rel.startswith("01_原始素材/"):
        return Path(rel).name not in MI_METADATA_NAMES
    return any(rel == m.rstrip("/") or rel.startswith(m) for m in BD_NEVER_STAGE_MARKERS)
