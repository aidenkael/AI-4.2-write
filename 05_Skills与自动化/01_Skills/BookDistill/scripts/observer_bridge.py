#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BookDistill observer bridge.

Thin deterministic wrapper between SourcePrepare input and BookDistill's curated
evidence layer.

It does not call a model and does not decide literary value. It:
1) initializes staging workspaces for the two default observer contracts;
2) validates observer evidence against SourcePrepare chapter boundaries;
3) merges validated OBSERVATION / INFERENCE / BOUNDARY entries into the
   canonical BookDistill evidence files without overwriting existing work.

Observer synthesis remains a human/Agent judgment artifact and is not
mechanically promoted into MECHANISM or BKP.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

try:
    import book_distill as bd
except ModuleNotFoundError:  # pragma: no cover - package-style import in tests
    from . import book_distill as bd  # type: ignore

BRIDGE_VERSION = "0.1.0"

OBSERVER_IDS = (
    "longform_reader_dynamics",
    "reader_page_craft",
)

ALLOWED_KINDS = ("OBSERVATION", "INFERENCE", "BOUNDARY")

OBSERVER_LABELS = {
    "longform_reader_dynamics": "长篇运行 / 读者动力",
    "reader_page_craft": "Reader / Page Craft",
}

SECTION_HEADINGS = {
    "OBSERVATION": "## OBSERVATION（作品内观察）",
    "INFERENCE": "## INFERENCE（推断）",
    "BOUNDARY": "## BOUNDARY（边界与不确定性）",
}

ENTRY_RE = re.compile(r"^\s*-\s*\[(OBSERVATION|INFERENCE|BOUNDARY)\]\s*(.+)$")
OBSERVER_TAG_RE = re.compile(r"(?:^|\|)\s*observer\s*[:：]\s*([A-Za-z0-9_-]+)\s*(?:\||$)")
SOURCE_FILE_RE = re.compile(r"^ch_(\d{4})\.md$")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def canonical_chapter_ref(chapter_name: str) -> str:
    return f"chapters/{chapter_name}"


def source_chapter_from_observer_file(path: Path) -> str | None:
    match = SOURCE_FILE_RE.match(path.name)
    if not match:
        return None
    return f"{match.group(1)}.md"


def render_observer_chapter_template(observer_id: str, chapter: dict) -> str:
    label = OBSERVER_LABELS[observer_id]
    source_ref = canonical_chapter_ref(chapter["file"])
    return "\n".join(
        [
            f"# {label}｜{chapter['file']}",
            "",
            f"- observer_id: `{observer_id}`",
            f"- source: `{source_ref}`",
            f"- title: {chapter.get('title') or '（未识别）'}",
            "",
            "## 使用规则",
            "",
            "- 先直接读取本章原文，再记录观察；不要从其他观察者摘要二次总结。",
            "- 这里只记录作品内 Observation / Inference / Boundary；不要直接生成 MECHANISM。",
            "- 一条高价值观察可以很小，也可以跨多个普通细节，但本章文件中的证据引用必须落在本章。",
            "- 如果本章没有某类显著信号，留空，不为覆盖率硬填。",
            "",
            "格式：",
            f"`- [OBSERVATION] dimension:维度 | observer:{observer_id} | 一句话观察｜证据：{source_ref}#L起始-L结束｜置信度：高/中/低`",
            f"`- [INFERENCE] observer:{observer_id} | 推断｜证据：{source_ref}#L起始-L结束｜置信度：高/中/低`",
            f"`- [BOUNDARY] observer:{observer_id} | 边界/反证/不确定性｜证据：{source_ref}#L起始-L结束｜置信度：高/中/低`",
            "",
            "## OBSERVATION",
            "",
            "## INFERENCE",
            "",
            "## BOUNDARY",
            "",
            "## Observer Notes",
            "",
            "（可记录问题栈、阶段信号、待跨章核对项；这些 Notes 不会被桥接脚本自动写入 BookDistill canonical evidence。）",
            "",
        ]
    )


def render_synthesis_template(observer_id: str) -> str:
    label = OBSERVER_LABELS[observer_id]
    common = [
        f"# {label}｜跨章综合",
        "",
        f"- observer_id: `{observer_id}`",
        "- authority: discovery staging only；不是 BKP，不是 Production Rule。",
        "",
        "## 跨章发现",
        "",
        "只保留需要多章才能看见的效果链、阶段变化和真正重要的组合关系；每项列出对应章节证据。",
        "",
        "## 与 BookProfile 的关系",
        "",
        "哪些发现强化、修正或推翻了初步导航；BookProfile 只能被修订，不能反向过滤这里的新发现。",
        "",
        "## Deep Dive 候选",
        "",
        "仅列高价值且现有证据仍不足的问题；不要为了流程完整强行提出专项。",
        "",
        "## 不确定性 / 反例",
        "",
    ]
    if observer_id == "longform_reader_dynamics":
        common.extend(
            [
                "## 建议维护的跨章账本",
                "",
                "- reader promise / payoff / unresolved responsibility",
                "- information debt / reveal timing / knowledge-state changes",
                "- emotional pressure / release / breathing room",
                "- protagonist desire / obstacle / choice / consequence",
                "- relationship movement",
                "- chapter/scene function and forward pull",
                "",
            ]
        )
    else:
        common.extend(
            [
                "## 建议维护的体验轨迹",
                "",
                "- first-time reader question / prediction stack",
                "- lean-in / drift / reorientation moments",
                "- transportation / aesthetic / social simulation / curiosity / flow",
                "- psychic-distance / POV movement",
                "- dialogue / subtext / action / sensory / omission",
                "- micro-details that combine into a larger reader-state change",
                "",
            ]
        )
    return "\n".join(common)


def init_workspace(sp_dir: Path, bd_output: Path, force: bool = False) -> dict:
    validation = bd.validate_input(sp_dir)
    if not validation["ok"]:
        return {
            "ok": False,
            "errors": validation["errors"],
            "warnings": validation["warnings"],
            "created": [],
        }

    chapters = bd.build_chapter_index(sp_dir)
    created: list[str] = []
    skipped: list[str] = []
    discovery_root = bd_output / "discovery"
    discovery_root.mkdir(parents=True, exist_ok=True)

    for observer_id in OBSERVER_IDS:
        observer_dir = discovery_root / observer_id
        chapter_dir = observer_dir / "chapters"
        chapter_dir.mkdir(parents=True, exist_ok=True)

        manifest_path = observer_dir / "observer_manifest.json"
        manifest = {
            "bridge_version": BRIDGE_VERSION,
            "observer_id": observer_id,
            "observer_label": OBSERVER_LABELS[observer_id],
            "book_id": validation["info"].get("book_id"),
            "book": validation["info"].get("book"),
            "source_snapshot": validation["info"].get("source_snapshot"),
            "chapter_count": len(chapters),
            "status": "prepared",
            "contract": f"observers/{observer_id}.md",
        }
        if force or not manifest_path.exists():
            write_text(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
            created.append(str(manifest_path))
        else:
            skipped.append(str(manifest_path))

        synthesis_path = observer_dir / "synthesis.md"
        if force or not synthesis_path.exists():
            write_text(synthesis_path, render_synthesis_template(observer_id))
            created.append(str(synthesis_path))
        else:
            skipped.append(str(synthesis_path))

        for chapter in chapters:
            target = chapter_dir / f"ch_{Path(chapter['file']).stem}.md"
            if force or not target.exists():
                write_text(target, render_observer_chapter_template(observer_id, chapter))
                created.append(str(target))
            else:
                skipped.append(str(target))

    return {
        "ok": True,
        "errors": [],
        "warnings": validation["warnings"],
        "created": created,
        "skipped": skipped,
        "chapter_count": len(chapters),
        "observers": list(OBSERVER_IDS),
    }


def parse_entries(path: Path, observer_id: str) -> tuple[list[tuple[str, str]], list[str]]:
    entries: list[tuple[str, str]] = []
    errors: list[str] = []
    for line_no, line in enumerate(read_text(path).splitlines(), start=1):
        match = ENTRY_RE.match(line)
        if not match:
            if re.match(r"^\s*-\s*\[[A-Za-z_]+\]", line):
                errors.append(f"{path}:{line_no}: 非法 observer kind；只允许 {', '.join(ALLOWED_KINDS)}")
            continue

        kind = match.group(1)
        tag_match = OBSERVER_TAG_RE.search(line)
        if not tag_match:
            errors.append(f"{path}:{line_no}: 缺少 observer:{observer_id} 标签")
            continue
        if tag_match.group(1) != observer_id:
            errors.append(
                f"{path}:{line_no}: observer 标签为 {tag_match.group(1)}，与目录 {observer_id} 不一致"
            )
            continue
        if kind == "OBSERVATION" and bd.parse_observation_dimension(line) is None:
            errors.append(f"{path}:{line_no}: OBSERVATION 缺少 dimension 标签")
            continue
        entries.append((kind, line.strip()))
    return entries, errors


def _valid_source_context(sp_dir: Path) -> tuple[dict, list[str], dict[str, int]]:
    validation = bd.validate_input(sp_dir)
    if not validation["ok"]:
        raise ValueError("\n".join(validation["errors"]))

    chapters = bd.build_chapter_index(sp_dir)
    valid_files = [canonical_chapter_ref(ch["file"]) for ch in chapters]
    line_bounds = {
        canonical_chapter_ref(ch["file"]): ch["lines"]
        for ch in chapters
    }
    return validation, valid_files, line_bounds


def validate_observer(
    sp_dir: Path,
    bd_output: Path,
    observer_id: str,
) -> dict:
    if observer_id not in OBSERVER_IDS:
        return {"ok": False, "errors": [f"未知 observer_id: {observer_id}"], "warnings": []}

    try:
        validation, valid_files, line_bounds = _valid_source_context(sp_dir)
    except ValueError as exc:
        return {"ok": False, "errors": str(exc).splitlines(), "warnings": []}

    observer_dir = bd_output / "discovery" / observer_id
    manifest_path = observer_dir / "observer_manifest.json"
    errors: list[str] = []
    warnings: list[str] = list(validation["warnings"])
    stats = {kind: 0 for kind in ALLOWED_KINDS}
    files_with_entries = 0

    if not manifest_path.exists():
        errors.append(f"缺少 observer_manifest.json: {manifest_path}")
    else:
        try:
            manifest = json.loads(read_text(manifest_path))
        except json.JSONDecodeError as exc:
            errors.append(f"observer_manifest.json 非法 JSON: {exc}")
            manifest = {}
        if manifest.get("observer_id") != observer_id:
            errors.append("observer_manifest.json 的 observer_id 与目录不一致")
        if manifest.get("source_snapshot") != validation["info"].get("source_snapshot"):
            errors.append("observer source_snapshot 与当前 SourcePrepare 输入不一致")

    chapter_dir = observer_dir / "chapters"
    expected_chapters = {Path(ref).name for ref in valid_files}
    seen_chapters: set[str] = set()

    if not chapter_dir.is_dir():
        errors.append(f"缺少 observer chapters 目录: {chapter_dir}")
    else:
        for path in sorted(chapter_dir.glob("ch_*.md")):
            source_chapter = source_chapter_from_observer_file(path)
            if source_chapter is None:
                continue
            seen_chapters.add(source_chapter)
            entries, parse_errors = parse_entries(path, observer_id)
            errors.extend(parse_errors)
            if entries:
                files_with_entries += 1
            for kind, line in entries:
                stats[kind] += 1
                ref = bd.extract_ref_from_line(line)
                if not ref:
                    errors.append(f"{path}: 条目缺少证据引用 -> {line[:80]}")
                    continue
                ok, msg = bd.validate_ref(ref, valid_files, line_bounds)
                if not ok:
                    errors.append(f"{path}: {msg} -> {line[:80]}")
                    continue
                expected_ref_prefix = f"chapters/{source_chapter}#"
                if not ref.startswith(expected_ref_prefix):
                    errors.append(
                        f"{path}: 章节 staging 文件只能引用同章原文；当前 {ref}，期望 {expected_ref_prefix}..."
                    )

    missing = sorted(expected_chapters - seen_chapters)
    extra = sorted(seen_chapters - expected_chapters)
    if missing:
        errors.append(f"observer staging 缺少章节文件: {', '.join(missing)}")
    if extra:
        errors.append(f"observer staging 存在非当前 SourcePrepare 章节: {', '.join(extra)}")
    if files_with_entries == 0:
        warnings.append("observer 当前没有任何可桥接条目；可能仍是空模板。")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "stats": stats,
        "files_with_entries": files_with_entries,
        "observer_id": observer_id,
    }


def _insert_entries(text: str, heading: str, lines: list[str]) -> tuple[str, int]:
    unique = [line for line in lines if line not in text]
    if not unique:
        return text, 0
    marker = heading + "\n"
    pos = text.find(marker)
    if pos < 0:
        raise ValueError(f"canonical evidence 缺少章节标题: {heading}")
    insert_at = pos + len(marker)
    prefix = "\n" if not text[insert_at:].startswith("\n") else ""
    insertion = prefix + "\n".join(unique) + "\n"
    return text[:insert_at] + insertion + text[insert_at:], len(unique)


def merge_observers(sp_dir: Path, bd_output: Path, observer_ids: list[str]) -> dict:
    if not observer_ids:
        observer_ids = list(OBSERVER_IDS)

    validations = {
        observer_id: validate_observer(sp_dir, bd_output, observer_id)
        for observer_id in observer_ids
    }
    errors = [
        f"{observer_id}: {err}"
        for observer_id, result in validations.items()
        for err in result["errors"]
    ]
    if errors:
        return {"ok": False, "errors": errors, "merged": 0, "per_observer": validations}

    canonical_dir = bd_output / "evidence"
    if not canonical_dir.is_dir():
        return {
            "ok": False,
            "errors": [f"缺少 BookDistill canonical evidence 目录: {canonical_dir}；请先运行 book_distill.py prepare"],
            "merged": 0,
            "per_observer": validations,
        }

    pending: dict[Path, dict[str, list[str]]] = {}
    for observer_id in observer_ids:
        chapter_dir = bd_output / "discovery" / observer_id / "chapters"
        for path in sorted(chapter_dir.glob("ch_*.md")):
            source_chapter = source_chapter_from_observer_file(path)
            if source_chapter is None:
                continue
            canonical_path = canonical_dir / f"ch_{Path(source_chapter).stem}.md"
            if not canonical_path.exists():
                return {
                    "ok": False,
                    "errors": [f"缺少 canonical evidence 文件: {canonical_path}"],
                    "merged": 0,
                    "per_observer": validations,
                }
            entries, _ = parse_entries(path, observer_id)
            bucket = pending.setdefault(canonical_path, {kind: [] for kind in ALLOWED_KINDS})
            for kind, line in entries:
                bucket[kind].append(line)

    # Build all new contents before writing any file.
    new_contents: dict[Path, str] = {}
    merged_count = 0
    merged_by_kind = {kind: 0 for kind in ALLOWED_KINDS}
    for canonical_path, bucket in pending.items():
        text = read_text(canonical_path)
        for kind in ALLOWED_KINDS:
            try:
                text, added = _insert_entries(text, SECTION_HEADINGS[kind], bucket[kind])
            except ValueError as exc:
                return {
                    "ok": False,
                    "errors": [f"{canonical_path}: {exc}"],
                    "merged": 0,
                    "per_observer": validations,
                }
            merged_count += added
            merged_by_kind[kind] += added
        new_contents[canonical_path] = text

    for path, content in new_contents.items():
        write_text(path, content)

    report = {
        "bridge_version": BRIDGE_VERSION,
        "source_snapshot": _valid_source_context(sp_dir)[0]["info"].get("source_snapshot"),
        "observers": observer_ids,
        "merged": merged_count,
        "merged_by_kind": merged_by_kind,
        "validation": validations,
        "note": "observer synthesis is not mechanically promoted; BookDistill must still curate/corroborate before MECHANISM/BKP.",
    }
    report_path = bd_output / "discovery" / "merge_report.json"
    write_text(report_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return {"ok": True, **report, "report": str(report_path)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BookDistill observer bridge")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="prepare observer staging workspaces")
    p_init.add_argument("--input", required=True, type=Path, help="SourcePrepare PASS directory")
    p_init.add_argument("--output", required=True, type=Path, help="BookDistill output directory")
    p_init.add_argument("--force", action="store_true", help="overwrite observer staging templates")

    p_validate = sub.add_parser("validate", help="validate one observer staging workspace")
    p_validate.add_argument("--input", required=True, type=Path)
    p_validate.add_argument("--output", required=True, type=Path)
    p_validate.add_argument("--observer", required=True, choices=OBSERVER_IDS)

    p_merge = sub.add_parser("merge", help="merge validated observer entries into canonical evidence")
    p_merge.add_argument("--input", required=True, type=Path)
    p_merge.add_argument("--output", required=True, type=Path)
    p_merge.add_argument(
        "--observer",
        action="append",
        choices=OBSERVER_IDS,
        default=[],
        help="observer to merge; repeat flag for multiple; default = all",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "init":
        result = init_workspace(args.input, args.output, force=args.force)
    elif args.command == "validate":
        result = validate_observer(args.input, args.output, args.observer)
    else:
        result = merge_observers(args.input, args.output, args.observer)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
