#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
index_builder.py — DEPRECATED（Phase 2B1 canonical cutover，2026-08-16 退役）

legacy 22 列 CSV 索引构建器已停用：
- 六分类目录扫描 / 22 列 schema / book_id 分配 / discover() / update_book()
  已全部由 MaterialIntake canonical ledger（01_原始素材/素材资产.json）取代。
- 素材清单.csv（9 列）与 素材总索引.md 现在均由 MaterialIntake catalog.py
  refresh_and_render() 生成（derived views），禁止再通过本文件维护。

任何运行本文件的流程都会得到非 0 退出码；本文件不包含任何索引逻辑。
"""


def main() -> int:
    print("DEPRECATED: index_builder.py 已退役（Phase 2B1 canonical cutover）。")
    print("请改用 MaterialIntake canonical catalog：")
    print("  python 05_Skills与自动化/01_Skills/MaterialIntake/catalog.py --root E:/AI-Write")
    print("（素材清单.csv / 素材总索引.md 现在是从 素材资产.json 派生的视图）")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
