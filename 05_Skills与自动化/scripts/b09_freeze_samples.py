#!/usr/bin/env python3
"""B09 原著蒸馏 Benchmark：冻结本地样本，不复制原著正文。

用途：
1. 对本地只读原著计算 SHA256；
2. 探测章节边界；
3. 固定 OPENING / MIDDLE 两个窗口；
4. 只写 manifest，不写原文副本。

仅使用 Python 标准库。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


DEFAULT_OUTPUT_DIR = Path(
    "06_工作区/01_待处理/B09_原著蒸馏Benchmark/_local_manifests"
)

CHAPTER_RE = re.compile(
    r"(?m)^[\t ]*(?:"
    r"第[0-9一二三四五六七八九十百千万零〇两]+[章回节卷][^\n]*"
    r"|(?:chapter|chap\.)[\t ]+[0-9ivxlcdm]+[^\n]*"
    r"|序章[^\n]*|楔子[^\n]*|引子[^\n]*|尾声[^\n]*|后记[^\n]*"
    r")[\t ]*$",
    re.IGNORECASE,
)


@dataclass
class Span:
    index: int
    title: str
    start_char: int
    end_char: int

    @property
    def char_count(self) -> int:
        return self.end_char - self.start_char


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def decode_text(raw: bytes) -> tuple[str, str]:
    candidates = ("utf-8-sig", "utf-8", "gb18030", "utf-16", "utf-16-le", "utf-16-be")
    for encoding in candidates:
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise UnicodeError(
        "无法用 utf-8/gb18030/utf-16 解码。请先确认文件编码；脚本不会修改源文件。"
    )


def detect_chapters(text: str) -> list[Span]:
    matches = list(CHAPTER_RE.finditer(text))
    spans: list[Span] = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        title = match.group(0).strip()
        spans.append(Span(i + 1, title, start, end))
    return spans


def make_segments(text_length: int, target_chars: int = 10_000) -> list[Span]:
    if text_length <= 0:
        return []
    spans: list[Span] = []
    index = 1
    start = 0
    while start < text_length:
        end = min(text_length, start + target_chars)
        spans.append(Span(index, f"segment-{index:03d}", start, end))
        start = end
        index += 1
    return spans


def select_windows(spans: list[Span], count: int = 6) -> dict[str, list[Span]]:
    if len(spans) < count * 2:
        raise ValueError(f"至少需要 {count * 2} 个 span，当前只有 {len(spans)} 个")

    opening = spans[:count]

    # 中段窗口以全书中点为中心，但不能与 opening 重叠。
    middle_start = max(count, (len(spans) - count) // 2)
    middle_start = min(middle_start, len(spans) - count)
    middle = spans[middle_start : middle_start + count]

    return {"OPENING": opening, "MIDDLE": middle}


def compact_window(spans: Iterable[Span]) -> dict:
    items = list(spans)
    return {
        "span_indices": [s.index for s in items],
        "span_titles": [s.title for s in items],
        "start_char": items[0].start_char,
        "end_char": items[-1].end_char,
        "char_count": items[-1].end_char - items[0].start_char,
    }


def repo_relative_or_absolute(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve())


def main() -> int:
    parser = argparse.ArgumentParser(
        description="冻结 B09 Benchmark 样本：只记录哈希、边界和窗口，不复制正文。"
    )
    parser.add_argument("--source", required=True, help="原著本地文件路径")
    parser.add_argument("--sample-id", required=True, help="如 WN-A / WN-B / WL-A")
    parser.add_argument(
        "--kind",
        required=True,
        choices=("web_novel", "world_literature"),
        help="样本类别",
    )
    parser.add_argument("--title", default="", help="作品名；可留空，默认用文件名")
    parser.add_argument(
        "--selection-reason",
        default="",
        help="为什么选作本轮样本；建议简短说明",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="本地 manifest 目录；默认位于 06_工作区并应被 gitignore",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="AI-write 仓库根目录，用于把仓库内路径记录为相对路径",
    )
    parser.add_argument(
        "--window-count",
        type=int,
        default=6,
        help="每个窗口包含的章节/span 数，默认 6",
    )
    parser.add_argument(
        "--segment-chars",
        type=int,
        default=10_000,
        help="章节不足时字符切分目标长度，默认 10000",
    )
    args = parser.parse_args()

    source = Path(args.source).expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"源文件不存在：{source}")
    if args.window_count < 1:
        raise SystemExit("--window-count 必须 >= 1")

    raw = source.read_bytes()
    text, encoding = decode_text(raw)
    chapters = detect_chapters(text)

    required = args.window_count * 2
    if len(chapters) >= required:
        boundary_mode = "chapter"
        spans = chapters
        chapter_detection_count = len(chapters)
    else:
        boundary_mode = "segment"
        spans = make_segments(len(text), args.segment_chars)
        chapter_detection_count = len(chapters)

    if len(spans) < required:
        raise SystemExit(
            f"文本过短，无法冻结两个互不重叠窗口：需要至少 {required} 个 span，当前 {len(spans)}。"
        )

    windows = select_windows(spans, args.window_count)
    repo_root = Path(args.repo_root).expanduser().resolve()

    manifest = {
        "schema_version": 1,
        "benchmark": "B09_original_work_distillation",
        "sample_id": args.sample_id,
        "kind": args.kind,
        "title": args.title.strip() or source.stem,
        "selection_reason": args.selection_reason.strip(),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "ref": repo_relative_or_absolute(source, repo_root),
            "sha256": f"sha256:{sha256_file(source)}",
            "byte_size": source.stat().st_size,
            "encoding": encoding,
            "read_only": True,
            "raw_text_copied": False,
        },
        "coverage": {
            "mode": "sampled",
            "boundary_mode": boundary_mode,
            "detected_chapter_count": chapter_detection_count,
            "usable_span_count": len(spans),
            "window_count": args.window_count,
            "windows": {
                name: compact_window(selected) for name, selected in windows.items()
            },
            "omitted_ranges_exist": True,
            "warning": "只允许对冻结窗口下结论；不得把开篇/中段样本冒充整书规律。",
        },
        "integrity": {
            "source_must_match_sha256_before_each_runner": True,
            "runner_must_not_modify_source": True,
            "runner_must_not_expand_scope_without_new_manifest": True,
        },
        "local_only": True,
        "do_not_commit": True,
    }

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    out_path = output_dir / f"{args.sample_id}.json"
    out_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"Manifest: {out_path}")
    print(f"SHA256: {manifest['source']['sha256']}")
    print(f"Boundary mode: {boundary_mode}")
    print(f"Detected chapters: {chapter_detection_count}")
    for name, window in manifest["coverage"]["windows"].items():
        print(
            f"{name}: spans {window['span_indices']} | chars "
            f"{window['start_char']}..{window['end_char']}"
        )
    print("原著正文未复制、未修改。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
