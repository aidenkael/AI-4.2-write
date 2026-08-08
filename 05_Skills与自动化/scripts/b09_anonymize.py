#!/usr/bin/env python3
"""把 B09 Runner 输出复制为匿名盲审包。

- 每个 sample 独立随机映射 Runner -> 匿名标签；
- Judge 包不包含 run_metadata.json；
- 真实映射只写 Controller 目录；
- 所有输出应位于已 gitignore 的 _local_runs 下。
"""

from __future__ import annotations

import argparse
import json
import secrets
import shutil
from datetime import datetime, timezone
from pathlib import Path


RUNNERS = ("D0", "A", "B", "C")
PUBLIC_FILES = (
    "01_evidence_notes.md",
    "02_interpretation.md",
    "03_mechanism_cards.md",
    "04_self_limits.md",
    "check_report.json",
)


def random_label(used: set[str]) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    while True:
        label = "R-" + "".join(secrets.choice(alphabet) for _ in range(4))
        if label not in used:
            used.add(label)
            return label


def copy_public_files(src: Path, dst: Path) -> list[str]:
    dst.mkdir(parents=True, exist_ok=False)
    copied: list[str] = []
    for filename in PUBLIC_FILES:
        path = src / filename
        if path.is_file():
            shutil.copy2(path, dst / filename)
            copied.append(filename)
    return copied


def main() -> int:
    parser = argparse.ArgumentParser(description="匿名化 B09 round 输出，供 Judge 盲审")
    parser.add_argument("round_dir", help="例如 .../_local_runs/round-01")
    parser.add_argument(
        "--samples",
        nargs="+",
        default=("WN-A", "WN-B", "WL-A"),
        help="要匿名化的 sample id",
    )
    args = parser.parse_args()

    round_dir = Path(args.round_dir).resolve()
    if not round_dir.is_dir():
        raise SystemExit(f"round_dir 不存在：{round_dir}")

    blind_dir = round_dir / "_blind"
    controller_dir = round_dir / "_controller"
    if blind_dir.exists() or controller_dir.exists():
        raise SystemExit(
            "_blind 或 _controller 已存在。为避免破坏既有盲审映射，请先另建新 round。"
        )

    blind_dir.mkdir(parents=True)
    controller_dir.mkdir(parents=True)

    mapping: dict[str, dict[str, str]] = {}
    used_labels: set[str] = set()

    for sample in args.samples:
        sample_dir = round_dir / sample
        if not sample_dir.is_dir():
            raise SystemExit(f"缺少 sample 目录：{sample_dir}")

        sample_map: dict[str, str] = {}
        for runner in RUNNERS:
            src = sample_dir / runner
            if not src.is_dir():
                raise SystemExit(f"缺少 Runner 目录：{src}")
            label = random_label(used_labels)
            copied = copy_public_files(src, blind_dir / sample / label)
            if len(copied) < 4:
                raise SystemExit(
                    f"Runner 输出不完整：{src}；至少需要四个标准 Markdown 文件"
                )
            sample_map[runner] = label
        mapping[sample] = sample_map

    map_payload = {
        "benchmark": "B09_original_work_distillation",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "warning": "CONTROLLER ONLY — Judge 完成前不得打开或分享此映射。",
        "mapping": mapping,
    }
    (controller_dir / "blind_map.json").write_text(
        json.dumps(map_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    judge_readme = (
        "B09 Blind Packet\n"
        "Judge 只可读取本 _blind 目录。匿名标签每个 sample 独立随机生成。\n"
        "不要尝试根据文风猜 Runner 身份；只根据证据、推断克制、因果与迁移价值评审。\n"
    )
    (blind_dir / "README.txt").write_text(judge_readme, encoding="utf-8")

    print(f"Blind packet: {blind_dir}")
    print(f"Controller mapping: {controller_dir / 'blind_map.json'}")
    print("Judge 完成前不要打开 blind_map.json。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
