# -*- coding: utf-8 -*-
"""
test_collection_support.py — SourcePrepare 合集/来源容器 支持的最小验证（仅发现阶段，不转换）。

验证三件事（对应任务 A/B/C），全部为 dry-run / 来源发现，不调用 Pandoc、不写 06_工作区：

  A) 普通单本：按作品名（如「一九八四」）能定位到唯一作品，且身份来自中央索引 book_id。
  B) 合集新书：按 book_id（如 book_0096）能定位到合集拆分单书，且 来源容器 = 马伯庸作品合集。
  C) 跨目录归并：book_0035 同时命中旧目录单本 + 合集拆分本，两者归并为同一作品、合计 2 个候选来源。

运行：
  python test_collection_support.py --root "E:/AI-Write"
退出码 0 = 全部通过；非 0 = 存在失败。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import index_builder  # noqa: E402
import source_prepare as sp  # noqa: E402


def _fail(msg: str) -> str:
    return f"FAIL: {msg}"


def run(root: Path) -> int:
    book_map, name_map = sp.build_book_map(root)
    failures: list[str] = []

    # ---- Test A: 普通单本，按作品名定位 ----
    a = sp.locate(root, "一九八四", False, book_map, name_map)
    if len(a) != 1:
        failures.append(_fail(f"Test A: 期望 1 个匹配，实际 {len(a)}"))
    else:
        g = a[0]
        if g["book_id"] is None:
            failures.append(_fail("Test A: 一九八四 未解析到 book_id"))
        if g["containers"] != {""}:
            failures.append(_fail(f"Test A: 一九八四 不应有来源容器，得到 {g['containers']}"))
        print(f"[A] 一九八四 -> id={g['book_id']} 来源数={len(g['files'])} 容器={g['containers']}")

    # ---- Test B: 合集新书，按 book_id 定位 ----
    b = sp.locate(root, "book_0096", False, book_map, name_map)
    if len(b) != 1:
        failures.append(_fail(f"Test B: book_0096 期望 1 个匹配，实际 {len(b)}"))
    else:
        g = b[0]
        if g["work_name"] != "风起陇西":
            failures.append(_fail(f"Test B: book_0096 期望 风起陇西，得到 {g['work_name']}"))
        if "马伯庸作品合集" not in g["containers"]:
            failures.append(_fail(f"Test B: book_0096 来源容器应为 马伯庸作品合集，得到 {g['containers']}"))
        print(f"[B] book_0096 -> {g['work_name']} 容器={g['containers']} 来源数={len(g['files'])}")

    # ---- Test C: book_0035 跨目录归并（旧单本 + 合集拆分） ----
    c = sp.locate(root, "book_0035", False, book_map, name_map)
    if len(c) != 1:
        failures.append(_fail(f"Test C: book_0035 期望 1 个分组，实际 {len(c)}"))
    else:
        g = c[0]
        if g["work_name"] != "长安十二时辰":
            failures.append(_fail(f"Test C: book_0035 期望 长安十二时辰，得到 {g['work_name']}"))
        n_files = len(g["files"])
        has_container = "马伯庸作品合集" in g["containers"]
        has_loose = "" in g["containers"]
        if not (has_container and has_loose):
            failures.append(_fail(f"Test C: book_0035 应同时含合集拆分本与旧单本，容器={g['containers']}"))
        if n_files < 2:
            failures.append(_fail(f"Test C: book_0035 应至少 2 个候选来源，得到 {n_files}"))
        print(f"[C] book_0035 -> {g['work_name']} 来源数={n_files} 容器={g['containers']}")

    # ---- 附加：合集清单完整性（21 拆本全部入索引；其中 20 个为新 ID，
    #       长安十二时辰 复用 book_0035） ----
    recs = index_builder.discover(root)
    ma = [r for r in recs if r.source_container == "马伯庸作品合集"]
    if len(ma) != 21:
        failures.append(_fail(f"合集拆分本入索引数应为 21，实际 {len(ma)}"))
    else:
        ids = sorted({r.book_id for r in ma}, key=lambda x: int(x.split("_")[1]))
        # 21 条 = book_0035（长安十二时辰复用） + book_0096..book_0115（20 个新 ID）
        new_ids = [i for i in ids if i != "book_0035"]
        expected_new = [f"book_{i:04d}" for i in range(96, 116)]
        if "book_0035" not in ids:
            failures.append(_fail(f"合集应包含复用的 book_0035（长安十二时辰），实际 {ids}"))
        if new_ids != expected_new:
            failures.append(_fail(f"合集新 book_id 应为 book_0096..book_0115，实际 {new_ids}"))
        if len(ids) != 21:
            failures.append(_fail(f"合集 book_id 应共 21 个且唯一，实际 {ids}"))
    print(f"[+] 合集拆分本入索引：{len(ma)} 条（含复用 book_0035 + 新 book_0096..book_0115）")

    if failures:
        print("\n".join(failures))
        return 1
    print("\nALL TESTS PASSED")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=r"E:\AI-Write")
    return run(Path(ap.parse_args().root).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
