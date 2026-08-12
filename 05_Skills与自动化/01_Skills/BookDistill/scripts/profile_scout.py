#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BookProfile Scout — deterministic scaffold for pre-Discovery navigation.

The script does not call an LLM and does not perform literary judgment. It
validates a SourcePrepare PASS package, selects stratified original-text anchor
chapters, and creates a non-destructive `book_profile_initial.md` template.

The resulting profile is explicitly a hypothesis/navigation artifact. It must
not filter later observers or become BKP authority.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    import book_distill as bd
except ModuleNotFoundError:  # pragma: no cover
    from . import book_distill as bd  # type: ignore

SCOUT_VERSION = "0.1.0"
PROFILE_FILE = "book_profile_initial.md"


def _anchor_positions(count: int) -> list[int]:
    """Return zero-based stratified positions, preserving reading order."""
    if count <= 0:
        return []
    if count <= 9:
        return list(range(count))

    raw = [
        0,
        1,
        2,
        round((count - 1) * 0.25),
        round((count - 1) * 0.50),
        round((count - 1) * 0.75),
        count - 3,
        count - 2,
        count - 1,
    ]
    return sorted({max(0, min(count - 1, pos)) for pos in raw})


def select_anchor_chapters(entries: list[dict]) -> list[dict]:
    return [entries[pos] for pos in _anchor_positions(len(entries))]


def _render_profile(info: dict, entries: list[dict], anchors: list[dict]) -> str:
    snapshot = info.get("source_snapshot") or {}
    lines = [
        "# BookProfile Initial｜导航性作品识别",
        "",
        "> 状态：**HYPOTHESIS / NAVIGATION ONLY**。这是深度 Discovery 前的初步识别，",
        "> 不是最终 BookProfile，不得用来过滤后续观察维度，也不得直接升级为 BKP 知识。",
        "",
        f"- Scout 版本：{SCOUT_VERSION}",
        f"- 作品：{info.get('book', '')}（{info.get('book_id', '')}）",
        f"- 正文章节数：{len(entries)}",
        f"- source_sha256：`{snapshot.get('source_sha256', '')}`",
        f"- chapter_content_fingerprint：`{snapshot.get('chapter_content_fingerprint', '')}`",
        "",
        "## Scout 阅读锚点",
        "",
        "> 锚点用于低成本建立全书导航，不代表完整覆盖。发现卷界、结构转向、特殊强项或疑点时，",
        "> Agent 可以直接扩展读取任何原文章节。后续 Discovery 仍必须按各自合同直接读原著。",
        "",
        "| 章节 | 标题 | 字符数 | 行数 |",
        "|------|------|-------:|-----:|",
    ]
    for chapter in anchors:
        lines.append(
            f"| chapters/{chapter['file']} | {chapter.get('title') or ''} | "
            f"{chapter.get('chars', 0)} | {chapter.get('lines', 0)} |"
        )

    lines.extend(
        [
            "",
            "## 作品初步定位",
            "",
            "（Agent 填写：题材、叙事形态、主要阅读回报的初步假设。使用谨慎措辞。）",
            "",
            "## Contract / Reader Promise 假设",
            "",
            "（Agent 填写：作品目前看起来向读者承诺什么长期问题、情绪、关系或回报。）",
            "",
            "## 粗略阶段地图",
            "",
            "（Agent 填写：只记录当前可见的阶段与转向，不强行切出完整剧情单元。）",
            "",
            "## 显著强项（待 Discovery 验证）",
            "",
            "（Agent 填写：锚点中已有强信号的能力；必须说明仍待全书验证。）",
            "",
            "## 潜在强项 / 值得继续观察",
            "",
            "（Agent 填写：只是候选，不等于已确认。）",
            "",
            "## 不确定项",
            "",
            "（Agent 填写：当前无法判断、样本可能误导或必须跨章验证的问题。）",
            "",
            "## Discovery 建议重点",
            "",
            "> 本列表不构成排除项；观察者仍按自身合同直接读原著并允许发现未列价值。",
            "",
            "（Agent 填写：后续两个观察者值得特别留意的问题。）",
            "",
            "## 后续复盘",
            "",
            "Discovery / Deep Dive 完成后由最终 BookProfile 回看：",
            "",
            "- confirmed：",
            "- revised：",
            "- rejected：",
            "- newly_discovered：",
            "",
        ]
    )
    return "\n".join(lines)


def init_profile(sp_dir: Path, output_dir: Path, force: bool = False) -> dict:
    validation = bd.validate_input(sp_dir)
    if not validation["ok"]:
        return {
            "ok": False,
            "errors": validation["errors"],
            "warnings": validation["warnings"],
        }

    entries = bd.build_chapter_index(sp_dir)
    anchors = select_anchor_chapters(entries)
    target = output_dir / PROFILE_FILE
    if target.exists() and not force:
        return {
            "ok": True,
            "created": False,
            "path": str(target),
            "anchor_chapters": [item["file"] for item in anchors],
            "warnings": validation["warnings"] + ["初步 Profile 已存在，未覆盖。"],
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    target.write_text(
        _render_profile(validation["info"], entries, anchors),
        encoding="utf-8",
        newline="\n",
    )
    return {
        "ok": True,
        "created": True,
        "path": str(target),
        "anchor_chapters": [item["file"] for item in anchors],
        "warnings": validation["warnings"],
        "source_snapshot": validation["info"].get("source_snapshot"),
    }


def validate_profile(sp_dir: Path, output_dir: Path) -> dict:
    validation = bd.validate_input(sp_dir)
    if not validation["ok"]:
        return {
            "ok": False,
            "errors": validation["errors"],
            "warnings": validation["warnings"],
        }

    target = output_dir / PROFILE_FILE
    if not target.exists():
        return {"ok": False, "errors": [f"缺少 {PROFILE_FILE}: {target}"], "warnings": []}

    text = target.read_text(encoding="utf-8")
    required_sections = [
        "## 作品初步定位",
        "## Contract / Reader Promise 假设",
        "## 粗略阶段地图",
        "## 显著强项（待 Discovery 验证）",
        "## 潜在强项 / 值得继续观察",
        "## 不确定项",
        "## Discovery 建议重点",
        "## 后续复盘",
    ]
    errors = [f"缺少必要章节: {heading}" for heading in required_sections if heading not in text]

    snapshot = validation["info"].get("source_snapshot") or {}
    for field in ("source_sha256", "chapter_content_fingerprint"):
        value = str(snapshot.get(field, ""))
        if value and value not in text:
            errors.append(f"{PROFILE_FILE} 的 {field} 与当前 SourcePrepare 输入不一致")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": validation["warnings"],
        "path": str(target),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BookProfile Scout")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="create initial navigation profile")
    p_init.add_argument("--input", required=True, type=Path)
    p_init.add_argument("--output", required=True, type=Path)
    p_init.add_argument("--force", action="store_true")

    p_validate = sub.add_parser("validate", help="validate initial navigation profile")
    p_validate.add_argument("--input", required=True, type=Path)
    p_validate.add_argument("--output", required=True, type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "init":
        result = init_profile(args.input, args.output, args.force)
    else:
        result = validate_profile(args.input, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
