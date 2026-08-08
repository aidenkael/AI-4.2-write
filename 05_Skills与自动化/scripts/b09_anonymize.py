#!/usr/bin/env python3
"""把 B09 Runner 输出复制为匿名盲审包。

- 每个 sample 独立随机映射 Runner -> 匿名标签；
- Judge 包不包含 run_metadata.json；
- 正式盲审可附带每个 sample 的冻结 OPENING/MIDDLE 原文窗口，供 Judge 核验证据；
- check_report.json 在复制时自动清理 Runner 身份与本地路径；
- 真实映射只写 Controller 目录；
- 所有输出与冻结窗口都应位于已 gitignore 的 _local_runs 下。
"""

from __future__ import annotations

import argparse
import json
import secrets
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RUNNERS = ("D0", "A", "B", "C")
PUBLIC_FILES = (
    "01_evidence_notes.md",
    "02_interpretation.md",
    "03_mechanism_cards.md",
    "04_self_limits.md",
    "check_report.json",
)
SOURCE_FILES = ("OPENING.txt", "MIDDLE.txt", "manifest_info.json")
SENSITIVE_JSON_KEYS = {
    "runner",
    "runner_id",
    "runner_name",
    "runner_dir",
    "method",
    "method_name",
    "input_dir",
    "output_dir",
    "source_dir",
    "workdir",
    "cwd",
    "task_prompt_path",
}


def random_label(used: set[str]) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    while True:
        label = "R-" + "".join(secrets.choice(alphabet) for _ in range(4))
        if label not in used:
            used.add(label)
            return label


def _sanitize_json(value: Any, *, src: Path, label: str) -> Any:
    """递归清理盲包 JSON 中可能泄露 Runner 身份或本地路径的字段。"""

    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if key.lower() in SENSITIVE_JSON_KEYS:
                cleaned[key] = f"<anonymous:{label}>"
            else:
                cleaned[key] = _sanitize_json(item, src=src, label=label)
        return cleaned
    if isinstance(value, list):
        return [_sanitize_json(item, src=src, label=label) for item in value]
    if isinstance(value, str):
        candidates = {
            str(src),
            str(src.resolve()),
            str(src).replace("\\", "/"),
            str(src.resolve()).replace("\\", "/"),
        }
        cleaned = value
        for candidate in sorted(candidates, key=len, reverse=True):
            if candidate:
                cleaned = cleaned.replace(candidate, f"<anonymous:{label}>")
        return cleaned
    return value


def copy_public_files(src: Path, dst: Path, label: str) -> list[str]:
    dst.mkdir(parents=True, exist_ok=False)
    copied: list[str] = []
    for filename in PUBLIC_FILES:
        path = src / filename
        if not path.is_file():
            continue
        target = dst / filename
        if filename == "check_report.json":
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise SystemExit(f"无法读取 check_report.json：{path}: {exc}") from exc
            payload = _sanitize_json(payload, src=src, label=label)
            target.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        else:
            shutil.copy2(path, target)
        copied.append(filename)
    return copied


def copy_source_packet(inputs_dir: Path, sample: str, dst: Path) -> list[str]:
    src = inputs_dir / sample
    if not src.is_dir():
        raise SystemExit(f"缺少 sample 冻结输入目录：{src}")
    dst.mkdir(parents=True, exist_ok=False)
    copied: list[str] = []
    for filename in SOURCE_FILES:
        path = src / filename
        if not path.is_file():
            raise SystemExit(f"缺少 Judge 核证所需冻结输入：{path}")
        shutil.copy2(path, dst / filename)
        copied.append(filename)
    return copied


def main() -> int:
    parser = argparse.ArgumentParser(description="匿名化 B09 round 输出，供 Judge 盲审")
    parser.add_argument("round_dir", help="例如 .../_local_runs/round-01-formal")
    parser.add_argument(
        "--samples",
        nargs="+",
        default=("WN-A", "WN-B", "WL-A"),
        help="要匿名化的 sample id",
    )
    parser.add_argument(
        "--source-inputs-dir",
        default=None,
        help=(
            "正式盲审时必须提供冻结输入目录，例如 round-01-formal/_inputs；"
            "脚本会把每个 sample 的 OPENING.txt、MIDDLE.txt、manifest_info.json "
            "复制到匿名包的 _source/，不包含整本原著。"
        ),
    )
    args = parser.parse_args()

    round_dir = Path(args.round_dir).resolve()
    if not round_dir.is_dir():
        raise SystemExit(f"round_dir 不存在：{round_dir}")

    inputs_dir = Path(args.source_inputs_dir).resolve() if args.source_inputs_dir else None
    if inputs_dir is not None and not inputs_dir.is_dir():
        raise SystemExit(f"source inputs dir 不存在：{inputs_dir}")

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

        if inputs_dir is not None:
            copied_source = copy_source_packet(inputs_dir, sample, blind_dir / sample / "_source")
            if len(copied_source) != len(SOURCE_FILES):
                raise SystemExit(f"冻结输入包不完整：{sample}")

        sample_map: dict[str, str] = {}
        for runner in RUNNERS:
            src = sample_dir / runner
            if not src.is_dir():
                raise SystemExit(f"缺少 Runner 目录：{src}")
            label = random_label(used_labels)
            copied = copy_public_files(src, blind_dir / sample / label, label)
            if len(copied) < 4:
                raise SystemExit(
                    f"Runner 输出不完整：{src}；至少需要四个标准 Markdown 文件"
                )
            sample_map[runner] = label
        mapping[sample] = sample_map

    map_payload = {
        "benchmark": "B09_original_work_distillation",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "warning": "CONTROLLER ONLY — Judge 与人工盲评完成前不得打开或分享此映射。",
        "source_packet_included": inputs_dir is not None,
        "check_report_identity_sanitized": True,
        "mapping": mapping,
    }
    (controller_dir / "blind_map.json").write_text(
        json.dumps(map_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    judge_readme = (
        "B09 Blind Packet\n"
        "Judge 只可读取本 _blind 目录。匿名标签每个 sample 独立随机生成。\n"
        "每个 sample 的 _source/（若存在）是同一份冻结 OPENING/MIDDLE 原文窗口，"
        "仅用于核验 Evidence；不得根据自身记忆补充窗口外正文。\n"
        "check_report.json 已在匿名化阶段清理 Runner 身份与本地路径字段。\n"
        "不要尝试根据文风猜 Runner 身份；只根据证据、推断克制、因果与迁移价值评审。\n"
    )
    (blind_dir / "README.txt").write_text(judge_readme, encoding="utf-8")

    print(f"Blind packet: {blind_dir}")
    print(f"Controller mapping: {controller_dir / 'blind_map.json'}")
    if inputs_dir is None:
        print("WARNING: 未附冻结 source packet；仅适合不核验证据忠实度的旧流程。")
    else:
        print("Frozen source packet included for Evidence fidelity judging.")
    print("check_report identity/path fields sanitized in blind packet.")
    print("Judge 与人工盲评完成前不要打开 blind_map.json。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
