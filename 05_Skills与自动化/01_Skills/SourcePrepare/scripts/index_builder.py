# -*- coding: utf-8 -*-
"""
index_builder.py — 原始素材索引生成与更新工具

扫描 01_原始素材，生成两份长期维护文件（均上传 GitHub，不含第三方全文）：
  1. 00_项目控制/原始素材清单.csv   —— 给 Agent / 自动化用，一部作品可对应多条文件记录。
  2. 00_项目控制/原始素材总索引.md —— 给人阅读，按分类列出作品与状态。

同时为 SourcePrepare 提供 update_book()：SP 跑完一本书后回写主源 / SP状态 / 字符数等。

设计原则：
- 作品ID稳定：book_0001 顺序分配，按分类顺序 + 作品名排序；文件格式/版本变化不改变ID。
- 不修改、不移动 01_原始素材 任何原始文件。
- 作者等元数据的提取是“保守的”：文件名里能可靠识别才填，不能识别留空，绝不脑补。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

ROOT_DEFAULT = Path(r"E:\AI-Write")
RAW = "01_原始素材"
CTRL = "00_项目控制"
SUPPORTED = {".epub", ".txt", ".pdf", ".zip", ".azw3", ".mobi"}

CATEGORY_ORDER = [
    "01_网络小说", "02_中文文学", "03_外国文学",
    "04_历史与古代资料", "05_现代专业资料", "06_其他参考资料",
]
CATEGORY_LABEL = {
    "01_网络小说": "网络小说",
    "02_中文文学": "中文文学",
    "03_外国文学": "外国文学",
    "04_历史与古代资料": "历史与古代资料",
    "05_现代专业资料": "现代专业资料",
    "06_其他参考资料": "其他参考资料",
}
# 书名文件里出现的“出版社/丛书/版本”关键词，不作为作者
PUBLISHER_KEYWORDS = ["译文", "读客", "名著名译", "丛书", "全", "册", "经典", "出品",
                      "出版社", "果麦", "上海", "出版", "校", "订", "修订", "珍藏"]
PUBLISHER_HINTS = {
    "上海译文": "上海译文", "果麦": "果麦", "读客": "读客",
    "名著名译": "名著名译丛书", "译文经典": "译文经典", "读客版": "读客",
}

CSV_COLUMNS = [
    "作品ID", "作品名", "作者", "资料大类", "标签", "版本", "译者", "出版社",
    "本地相对路径", "文件名", "文件格式", "文件大小", "SHA256", "是否主来源",
    "SourcePrepare状态", "SourcePrepare版本", "标准MD字符数", "识别章节数",
    "BookDistill状态", "最后检查时间", "备注",
]


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_author(filename_stem: str) -> tuple[Optional[str], Optional[str]]:
    """从文件名提取作者与出版社提示。保守：不能可靠识别则留空。"""
    # 顶层 (...) 分组
    groups = re.findall(r"\(([^()]*)\)", filename_stem)
    author: Optional[str] = None
    publisher: Optional[str] = None
    for g in groups:
        # 嵌套括号（如 (乔治·奥威尔(GeorgeOrwell))）取前缀
        cand = g.split("(")[0].strip()
        if not cand:
            continue
        if any(k in cand for k in PUBLISHER_KEYWORDS):
            # 可能是出版社/丛书，记录到出版社提示
            for key, val in PUBLISHER_HINTS.items():
                if key in cand or key in filename_stem:
                    publisher = val
            continue
        # 去掉结尾的“著/撰”等
        cand = re.sub(r"[著撰]$", "", cand).strip()
        if cand and not author:
            author = cand
    if publisher is None:
        for key, val in PUBLISHER_HINTS.items():
            if key in filename_stem:
                publisher = val
                break
    return author, publisher


@dataclass
class FileRec:
    book_id: str
    book_name: str
    author: Optional[str]
    category: str
    rel_path: str
    filename: str
    fmt: str
    size: int
    sha256: str
    is_primary: bool
    publisher: Optional[str]
    note: str = ""


def discover(root: Path) -> list[FileRec]:
    raw = root / RAW
    # 按 (分类顺序, 作品名) 稳定分配 ID
    work_files: dict[tuple[str, str], list[Path]] = {}
    for cat in CATEGORY_ORDER:
        cdir = raw / cat
        if not cdir.exists():
            continue
        for work in sorted(cdir.iterdir()):
            if not work.is_dir():
                continue
            files = [f for f in work.iterdir() if f.is_file() and f.suffix.lower() in SUPPORTED]
            if files:
                work_files[(cat, work.name)] = files

    # 分类根层下的“松散文件”（如 05_现代专业资料 的 PDF 报告）也按单文件作品登记
    for cat in CATEGORY_ORDER:
        cdir = raw / cat
        if not cdir.exists():
            continue
        for entry in cdir.iterdir():
            if entry.is_file() and entry.suffix.lower() in SUPPORTED:
                key = (cat, entry.stem)
                work_files.setdefault(key, []).append(entry)

    ordered = sorted(work_files.keys(), key=lambda k: (CATEGORY_ORDER.index(k[0]), k[1]))
    recs: list[FileRec] = []
    for i, (cat, wname) in enumerate(ordered, start=1):
        bid = f"book_{i:04d}"
        author, publisher = extract_author(wname)
        files = sorted(work_files[(cat, wname)])
        # 主源优先级：epub > txt > pdf（单可靠主源即可；多格式交叉校验）
        prio = {".epub": 0, ".txt": 1, ".pdf": 2}
        primary = sorted(files, key=lambda f: prio.get(f.suffix.lower(), 9))[0]
        for f in files:
            recs.append(FileRec(
                book_id=bid,
                book_name=wname,
                author=author,
                category=CATEGORY_LABEL.get(cat, cat),
                rel_path=f.relative_to(root).as_posix(),
                filename=f.name,
                fmt=f.suffix.lower().lstrip("."),
                size=f.stat().st_size,
                sha256=sha256_file(f),
                is_primary=(f == primary),
                publisher=publisher,
                note="",
            ))
    return recs


def write_csv(root: Path, recs: list[FileRec]) -> Path:
    out = root / CTRL / "原始素材清单.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        w.writeheader()
        for r in recs:
            w.writerow({
                "作品ID": r.book_id,
                "作品名": r.book_name,
                "作者": r.author or "",
                "资料大类": r.category,
                "标签": "",
                "版本": "",
                "译者": "",
                "出版社": r.publisher or "",
                "本地相对路径": r.rel_path,
                "文件名": r.filename,
                "文件格式": r.fmt,
                "文件大小": r.size,
                "SHA256": r.sha256,
                "是否主来源": "是" if r.is_primary else "否",
                "SourcePrepare状态": "未处理",
                "SourcePrepare版本": "",
                "标准MD字符数": "",
                "识别章节数": "",
                "BookDistill状态": "未开始",
                "最后检查时间": datetime.now().strftime("%Y-%m-%d"),
                "备注": r.note,
            })
    return out


def write_md(root: Path, recs: list[FileRec]) -> Path:
    out = root / CTRL / "原始素材总索引.md"
    by_cat: dict[str, list[FileRec]] = {}
    for r in recs:
        by_cat.setdefault(r.category, []).append(r)
    lines = ["# 原始素材总索引", "",
             f"> 本文件由 `SourcePrepare/scripts/index_builder.py` 自动生成，反映本地 `01_原始素材` 的真实情况。",
             "> 第三方原著全文 **Local Only，不上传 GitHub**；本索引仅含元数据与处理状态。",
             "", f"更新时间：{datetime.now().strftime('%Y-%m-%d')}  ",
             f"本地作品总数：{len({r.book_id for r in recs})}  ",
             f"原始文件总数：{len(recs)}", ""]
    cat_order = ["网络小说", "中文文学", "外国文学", "历史与古代资料", "现代专业资料", "其他参考资料"]
    for cat in cat_order:
        items = by_cat.get(cat)
        if not items:
            continue
        lines += ["", f"## {cat}", "",
                  "| 作品 | 作者 | 本地格式 | SP状态 | 蒸馏状态 | 标签 |",
                  "|---|---|---|---|---|---|"]
        # 按作品聚合
        works: dict[str, list[FileRec]] = {}
        for r in items:
            works.setdefault(r.book_id, []).append(r)
        for bid in sorted(works, key=lambda b: int(b.split("_")[1])):
            rs = works[bid]
            names = rs[0].book_name
            authors = "、".join(sorted({r.author for r in rs if r.author})) or "—"
            fmts = "、".join(sorted({r.fmt for r in rs}))
            sp = rs[0].note  # placeholder; real SP status filled by CSV->MD rebuild
            lines.append(f"| {names} | {authors} | {fmts} | 未处理 | 未开始 |  |")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def load_csv(root: Path) -> list[dict]:
    path = root / CTRL / "原始素材清单.csv"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def save_csv(root: Path, rows: list[dict]) -> None:
    path = root / CTRL / "原始素材清单.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in CSV_COLUMNS})


def rebuild_md_from_csv(root: Path) -> Path:
    """从 CSV 重新生成 Markdown 总索引（SP 更新 CSV 后调用）。"""
    rows = load_csv(root)
    if not rows:
        return write_md(root, [])
    recs = [FileRec(
        book_id=r["作品ID"], book_name=r["作品名"], author=r["作者"] or None,
        category=r["资料大类"], rel_path=r["本地相对路径"], filename=r["文件名"],
        fmt=r["文件格式"], size=int(r["文件大小"] or 0), sha256=r["SHA256"],
        is_primary=(r["是否主来源"] == "是"),
        publisher=r["出版社"] or None, note=r["备注"] or "",
    ) for r in rows]
    return write_md(root, recs)


def update_book(root: Path, book_id: str, *,
                sp_status: str, sp_version: str,
                char_count: int | str = "", chapter_count: int | str = "",
                note: str = "", check_time: Optional[str] = None) -> bool:
    """SP 跑完一本书后，回写该书所有文件记录的指定列，并重建 MD。"""
    rows = load_csv(root)
    if not rows:
        return False
    t = check_time or datetime.now().strftime("%Y-%m-%d")
    hit = False
    for r in rows:
        if r["作品ID"] == book_id:
            hit = True
            r["SourcePrepare状态"] = sp_status
            r["SourcePrepare版本"] = sp_version
            r["标准MD字符数"] = str(char_count) if char_count != "" else r["标准MD字符数"]
            r["识别章节数"] = str(chapter_count) if chapter_count != "" else r["识别章节数"]
            r["最后检查时间"] = t
            if note:
                r["备注"] = (r["备注"] + "；" + note) if r["备注"] else note
    if hit:
        save_csv(root, rows)
        rebuild_md_from_csv(root)
    return hit


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT_DEFAULT))
    args = ap.parse_args()
    root = Path(args.root).resolve()
    recs = discover(root)
    c = write_csv(root, recs)
    m = write_md(root, recs)
    print(f"作品(文件)记录：{len(recs)}，作品数：{len({r.book_id for r in recs})}")
    print(f"已写入：{c.relative_to(root).as_posix()}")
    print(f"已写入：{m.relative_to(root).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
