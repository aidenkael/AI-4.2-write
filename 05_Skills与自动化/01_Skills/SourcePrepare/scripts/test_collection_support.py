# -*- coding: utf-8 -*-
"""
test_collection_support.py — SourcePrepare 合集/来源容器 支持的最小验证
（Phase 2B1：canonical ledger consumer，只读发现，不重新转换原著）。

验证三件事（对应任务 A/B/C），全部为 dry-run / 来源发现，不调用 Pandoc、不写 06_工作区：

  A) 普通单本：按作品名（如「一九八四」）能定位到唯一作品，且身份来自 ledger book_id。
  B) 合集新书：按 book_id（如 book_0096）能定位到合集拆分单书，且 来源容器 = 马伯庸作品合集。
  C) 多来源归并：book_0035 同一 asset 双 file（独立 txt + 合集 epub），合计 2 个候选来源。
  +) 合集容器完整性：ledger containers 中 马伯庸作品合集 = 21 拆本
     （复用 book_0035 + 新 book_0096..book_0115）。

运行：
  python test_collection_support.py --root "E:/AI-Write"
退出码 0 = 全部通过；非 0 = 存在失败。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import source_prepare as sp  # noqa: E402


def _fail(msg: str) -> str:
    return f"FAIL: {msg}"


def run(root: Path) -> int:
    try:
        ledger = sp.load_ledger_assets(root)
    except (FileNotFoundError, RuntimeError) as exc:
        print(_fail(f"ledger 读取失败：{exc}"))
        return 1
    failures: list[str] = []

    # ---- Test A: 普通单本，按作品名定位 ----
    a = sp.locate(root, "一九八四", False, ledger)
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
    b = sp.locate(root, "book_0096", False, ledger)
    if len(b) != 1:
        failures.append(_fail(f"Test B: book_0096 期望 1 个匹配，实际 {len(b)}"))
    else:
        g = b[0]
        if g["work_name"] != "风起陇西":
            failures.append(_fail(f"Test B: book_0096 期望 风起陇西，得到 {g['work_name']}"))
        if "马伯庸作品合集" not in g["containers"]:
            failures.append(_fail(f"Test B: book_0096 来源容器应为 马伯庸作品合集，得到 {g['containers']}"))
        print(f"[B] book_0096 -> {g['work_name']} 容器={g['containers']} 来源数={len(g['files'])}")

    # ---- Test C: book_0035 双来源（独立 txt + 合集拆分 epub） ----
    c = sp.locate(root, "book_0035", False, ledger)
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
            failures.append(_fail(f"Test C: book_0035 应同时含合集拆分本与独立单本，容器={g['containers']}"))
        if n_files < 2:
            failures.append(_fail(f"Test C: book_0035 应至少 2 个候选来源，得到 {n_files}"))
        print(f"[C] book_0035 -> {g['work_name']} 来源数={n_files} 容器={g['containers']}")

    # ---- 附加：ledger container 完整性（21 拆本：复用 book_0035 + 新 book_0096..book_0115） ----
    containers = {cc["id"]: cc for cc in ledger["containers"]}
    ma = containers.get("马伯庸作品合集")
    if ma is None:
        failures.append(_fail("附加: ledger 缺少容器 马伯庸作品合集"))
    else:
        ids = sorted(ma["split_book_ids"], key=lambda x: int(x.split("_")[1]))
        new_ids = [i for i in ids if i != "book_0035"]
        expected_new = [f"book_{i:04d}" for i in range(96, 116)]
        if ma["split_count"] != 21:
            failures.append(_fail(f"附加: 容器 split_count 应为 21，实际 {ma['split_count']}"))
        if "book_0035" not in ids:
            failures.append(_fail(f"附加: 合集应包含复用的 book_0035（长安十二时辰），实际 {ids}"))
        if new_ids != expected_new:
            failures.append(_fail(f"附加: 合集新 book_id 应为 book_0096..book_0115，实际 {new_ids}"))
        if len(ids) != 21:
            failures.append(_fail(f"附加: 合集 book_id 应共 21 个且唯一，实际 {ids}"))
    print("[+] 合集拆分本：21 条（复用 book_0035 + 新 book_0096..book_0115）")

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
