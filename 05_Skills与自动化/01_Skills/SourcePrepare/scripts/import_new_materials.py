#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
import_new_materials.py — DEPRECATED / FAIL-FAST（Phase 2B1 canonical cutover，2026-08-16 退役）

legacy importer 已停用；新的 MaterialIntake inbox intake 将在 Phase 2B2 提供。

在 Phase 2B2 之前，新素材请勿通过本脚本入库：
- book_id 分配 / 文件移动 / 22 列 CSV 回写 / 索引重建均已退役。
- 唯一 canonical registry 是 01_原始素材/素材资产.json（MaterialIntake catalog.py 维护）。

本脚本运行即失败（退出码 1），不读取、不修改任何文件。
"""


def main() -> int:
    print("FAIL: legacy importer 已停用；新的 MaterialIntake inbox intake 将在 Phase 2B2 提供。")
    print("当前 canonical 素材真源为 01_原始素材/素材资产.json（MaterialIntake 维护）。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
