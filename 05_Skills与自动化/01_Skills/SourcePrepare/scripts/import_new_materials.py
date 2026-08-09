# -*- coding: utf-8 -*-
"""
import_new_materials.py — 把“新素材源目录”里的图书安全入库到 01_原始素材。

用法（在 Agent 执行“新增素材自动分类入库”指令时调用）：
    python import_new_materials.py --src "<新素材路径>"

流程：
  1. 扫描源目录，逐个计算 SHA256；
  2. 与现有 原始素材清单.csv 的 SHA256 对账，完全重复则跳过；
  3. 解析书名/作者/译者/版本，按分类字典归到对应物理目录；
  4. 复制入库（保留原文件名），复制后重算 SHA256 校验一致；
  5. 追加 CSV 记录（继承/新建作品ID，稳定编号）；
  6. 调用 index_builder.rebuild_md_from_csv 重建 Markdown 总索引。

分类只按物理目录，不脑补标签。译者仅在文件名显式含“译”时填写。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(r"E:\AI-Write")
CTRL = BASE / "00_项目控制"
RAW = BASE / "01_原始素材"
CSV_PATH = CTRL / "原始素材清单.csv"
MD_PATH = CTRL / "原始素材总索引.md"

# 物理分类目录
CAT_DIR = {
    "网络小说": "01_网络小说",
    "中文文学": "02_中文文学",
    "外国文学": "03_外国文学",
    "历史与古代资料": "04_历史与古代资料",
    "现代专业资料": "05_现代专业资料",
    "其他参考资料": "06_其他参考资料",
}

# 本次新素材的分类决策（作品名 -> 资料大类）
CLASSIFY = {
    "凡人修仙传": "网络小说", "大国重工": "网络小说", "大江东去": "网络小说",
    "完美世界": "网络小说", "悟空传": "网络小说", "惊悚乐园": "网络小说",
    "搜神记": "网络小说", "斗破苍穹": "网络小说", "斗罗大陆": "网络小说",
    "无限恐怖": "网络小说", "星辰变": "网络小说", "盗墓笔记": "网络小说",
    "盘龙": "网络小说", "神墓": "网络小说", "诛仙": "网络小说",
    "赘婿": "网络小说", "遮天": "网络小说", "阳神": "网络小说",
    "雪鹰领主": "网络小说", "鬼吹灯": "网络小说",
    "西游记": "中文文学", "骆驼祥子": "中文文学",
    "傲慢与偏见": "外国文学", "小王子": "外国文学",
    "杀死一只知更鸟": "外国文学", "老人与海": "外国文学",
}

# 出版社/丛书关键词（不作为作者）
PUBLISHER_KW = ["果麦", "经典", "出版", "译文", "读客", "丛书", "珍藏", "系列", "出版社"]

# 描述性短语关键词（括号内为“插图/目录/校对”等说明，不是作者）
DESC_KW = ["插图", "目录", "精美", "校对", "精校", "修订", "完整", "合集", "扫描", "排版", "全本"]

CSV_COLUMNS = [
    "作品ID", "作品名", "作者", "资料大类", "标签", "版本", "译者", "出版社",
    "本地相对路径", "文件名", "文件格式", "文件大小", "SHA256", "是否主来源",
    "来源容器", "SourcePrepare状态", "SourcePrepare版本", "标准MD字符数", "识别章节数",
    "BookDistill状态", "最后检查时间", "备注",
]


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_groups(stem: str):
    """提取顶层括号分组（兼容嵌套括号，如 哈珀·李(美) 著）。"""
    groups = []
    depth = 0
    cur = ""
    for ch in stem:
        if ch in "（(":
            depth += 1
            if depth == 1:
                cur = ""
                continue
        elif ch in "）)":
            depth -= 1
            if depth <= 0:
                if cur:
                    groups.append(cur)
                cur = ""
                depth = 0
                continue
        if depth >= 1:
            cur += ch
    return groups


def strip_brackets(s: str) -> str:
    """去掉字符串中的 () （） [] 括号及内部内容（可嵌套/相邻）。"""
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r"[（(][^（）()]*[）)]", "", s)
        s = re.sub(r"\[[^\]]*\]", "", s)
    return s.strip()


def parse_name(stem: str):
    """返回 (作品名, 作者, 译者, 版本补充)。"""
    groups = extract_groups(stem)
    work_raw = stem.split(" (", 1)[0].strip()
    # 去掉书名中粘连的出版社/丛书括号，如 “老人与海(果麦经典)”
    work_raw = strip_brackets(work_raw)

    version_extra = ""
    if "全集" in work_raw:
        work_raw = work_raw.replace("全集", "").strip()
        version_extra = "全集"
    m = re.search(r"\d+\s*[-—]\s*\d+", work_raw)
    if m:
        work_raw = work_raw.replace(m.group(0), "").strip()
        version_extra = (m.group(0).strip() + " " + version_extra).strip() if version_extra else m.group(0).strip()
    work_name = work_raw.strip()

    author = None
    translator = None
    for g in groups:
        if any(k in g for k in ["z-library", "1lib", "z-lib"]):
            continue
        if any(k in g for k in PUBLISHER_KW):
            continue
        if any(k in g for k in DESC_KW):
            continue
        segs = [s.strip() for s in g.split(",")]
        for s in segs:
            if "译" in s:
                t = re.sub(r"[著译]", "", s).strip()
                if t:
                    translator = t
            else:
                a = strip_brackets(s)
                a = re.sub(r"[著撰]", "", a).strip()
                if a and not author:
                    author = a
    return work_name, author, translator, version_extra


def load_existing():
    rows = []
    existing_sha = set()
    existing_names = set()
    if CSV_PATH.exists():
        with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                rows.append(r)
                if r.get("SHA256"):
                    existing_sha.add(r["SHA256"].strip().lower())
                if r.get("作品名"):
                    existing_names.add(r["作品名"].strip())
    return rows, existing_sha, existing_names


def next_id(rows):
    max_n = 0
    for r in rows:
        m = re.match(r"book_(\d+)$", (r.get("作品ID") or "").strip())
        if m:
            max_n = max(max_n, int(m.group(1)))
    return max_n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    args = ap.parse_args()
    src = Path(args.src)
    if not src.exists():
        print(f"[ERROR] 源目录不存在: {src}")
        return 2

    rows, existing_sha, existing_names = load_existing()
    counter = {"n": next_id(rows)}

    stats = dict(
        scanned=0, works=0, new_works=0, existing_files=0, dup_skip=0,
        same_name_diff_hash=0, epub=0, txt=0, pdf=0, other=0,
        cat={"网络小说": 0, "中文文学": 0, "外国文学": 0, "历史与古代资料": 0,
             "现代专业资料": 0, "其他参考资料": 0, "待核验": 0},
        multi_version=0, sha_fail=0,
    )
    plan = []

    for f in sorted(src.iterdir()):
        if not f.is_file():
            continue
        ext = f.suffix.lower().lstrip(".")
        if ext not in {"epub", "txt", "pdf", "mobi", "azw3", "zip", "doc", "docx"}:
            continue
        stats["scanned"] += 1
        src_sha = sha256_file(f)

        if src_sha in existing_sha:
            stats["dup_skip"] += 1
            plan.append((f.name, "完全重复(SHA256已存在)", "跳过"))
            continue

        work_name, author, translator, ver_extra = parse_name(f.stem)
        category = CLASSIFY.get(work_name)
        if category is None:
            category = "其他参考资料"
            stats["cat"]["待核验"] += 1
        else:
            stats["cat"][category] += 1

        # 同名不同哈希（已有同名作品但哈希不同）-> 仍作为新文件追加，不覆盖
        if work_name in existing_names:
            stats["same_name_diff_hash"] += 1
            stats["existing_files"] += 1
        else:
            stats["new_works"] += 1
            stats["works"] += 1

        counter["n"] += 1
        bid = f"book_{counter['n']:04d}"

        cat_dir = CAT_DIR[category]
        dest_dir = RAW / cat_dir / work_name
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f.name
        if dest.exists():
            # 目标已存在同名文件：比对哈希，相同则跳过，不同则加安全后缀
            if sha256_file(dest) == src_sha:
                stats["dup_skip"] += 1
                plan.append((f.name, "目标已存在且哈希一致", "跳过"))
                continue
            else:
                dest = dest_dir / (f.stem + "_版本2" + f.suffix)
        shutil.copy2(f, dest)
        dest_sha = sha256_file(dest)
        if dest_sha != src_sha:
            stats["sha_fail"] += 1
            plan.append((f.name, "SHA256复制不一致", "入库失败"))
            if dest.exists():
                dest.unlink()
            continue

        rel = dest.relative_to(BASE).as_posix()
        version = ver_extra
        fmt = ext
        if fmt == "epub":
            stats["epub"] += 1
        elif fmt == "txt":
            stats["txt"] += 1
        elif fmt == "pdf":
            stats["pdf"] += 1
        else:
            stats["other"] += 1

        row = {c: "" for c in CSV_COLUMNS}
        row.update({
            "作品ID": bid, "作品名": work_name, "作者": author or "",
            "资料大类": category, "版本": version, "译者": translator or "",
            "本地相对路径": rel, "文件名": dest.name, "文件格式": fmt,
            "文件大小": dest.stat().st_size, "SHA256": dest_sha,
            "是否主来源": "是", "来源容器": "", "SourcePrepare状态": "未处理",
            "SourcePrepare版本": "", "标准MD字符数": "", "识别章节数": "",
            "BookDistill状态": "未开始",
            "最后检查时间": datetime.now().strftime("%Y-%m-%d"), "备注": "",
        })
        rows.append(row)
        plan.append((dest.name, f"{category}/{work_name} [{bid}]", "已入库"))

    # 写回 CSV（保留原有记录 + 追加新记录）
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in CSV_COLUMNS})

    # 重建 Markdown 总索引（复用项目官方工具）
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import index_builder
    index_builder.rebuild_md_from_csv(BASE)

    print("=== 入库计划/结果 ===")
    for name, info, status in plan:
        print(f"  [{status}] {name}  ->  {info}")
    print("\n=== 统计 ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print(f"\nCSV 行数(含表头后): {len(rows)+1}")
    print(f"最大作品ID: book_{counter['n']:04d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
