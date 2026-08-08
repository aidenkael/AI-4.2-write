#!/usr/bin/env python3
"""B09 原著蒸馏 Benchmark 的确定性结构检查器。

它不判断文学质量，只检查：
- 四个标准文件是否存在；
- Evidence / Claim / Pattern ID 是否存在且引用有效；
- Claim 是否缺证据锚点；
- Mechanism Card 字段是否完整；
- Self Limits 是否明确 sampled coverage；
- 短证据是否异常过长，提示复述风险。
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


FILES = {
    "evidence": "01_evidence_notes.md",
    "interpretation": "02_interpretation.md",
    "patterns": "03_mechanism_cards.md",
    "limits": "04_self_limits.md",
}

EVID_RE = re.compile(r"\bEVID-\d{3,}\b")
CLAIM_RE = re.compile(r"\bCLAIM-\d{3,}\b")
PATTERN_RE = re.compile(r"\bPATTERN-\d{3,}\b")
H2_EVID_RE = re.compile(r"(?m)^##\s+(EVID-\d{3,})\b")
H2_CLAIM_RE = re.compile(r"(?m)^##\s+(CLAIM-\d{3,})\b")
H2_PATTERN_RE = re.compile(r"(?m)^##\s+(PATTERN-\d{3,})\b")

PATTERN_FIELDS = (
    "解决的问题",
    "必要前提",
    "作者侧动作",
    "读者侧经历",
    "中间因果链",
    "为什么有效",
    "失败模式",
    "反例/边界",
    "适用题材/阶段",
    "不适用场景",
    "安全迁移方式",
    "不可照搬元素",
    "证据来源",
    "迁移测试命题",
)


def read_required_files(root: Path) -> tuple[dict[str, str], list[str]]:
    texts: dict[str, str] = {}
    missing: list[str] = []
    for key, filename in FILES.items():
        path = root / filename
        if not path.is_file():
            missing.append(filename)
            texts[key] = ""
        else:
            texts[key] = path.read_text(encoding="utf-8")
    return texts, missing


def section_map(text: str, heading_re: re.Pattern[str]) -> dict[str, str]:
    matches = list(heading_re.finditer(text))
    sections: dict[str, str] = {}
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[match.group(1)] = text[match.start() : end]
    return sections


def field_value(section: str, field: str) -> str:
    match = re.search(
        rf"(?m)^\s*[-*]?\s*{re.escape(field)}\s*[：:]\s*(.*)$", section
    )
    return match.group(1).strip() if match else ""


def main() -> int:
    parser = argparse.ArgumentParser(description="检查一个 B09 Runner 输出目录")
    parser.add_argument("runner_dir", help="包含四个标准 Markdown 文件的目录")
    parser.add_argument("--output", help="JSON 报告路径；默认只打印 stdout")
    parser.add_argument(
        "--short-evidence-max-chars",
        type=int,
        default=120,
        help="单条‘短证据’超过该长度时提示 source_copy_risk，默认 120 字符",
    )
    args = parser.parse_args()

    root = Path(args.runner_dir)
    texts, missing = read_required_files(root)

    evidence_sections = section_map(texts["evidence"], H2_EVID_RE)
    claim_sections = section_map(texts["interpretation"], H2_CLAIM_RE)
    pattern_sections = section_map(texts["patterns"], H2_PATTERN_RE)

    evidence_ids = set(evidence_sections)
    claim_ids = set(claim_sections)

    duplicate_checks = {
        "evidence_heading_count": len(H2_EVID_RE.findall(texts["evidence"])),
        "evidence_unique_count": len(evidence_ids),
        "claim_heading_count": len(H2_CLAIM_RE.findall(texts["interpretation"])),
        "claim_unique_count": len(claim_ids),
        "pattern_heading_count": len(H2_PATTERN_RE.findall(texts["patterns"])),
        "pattern_unique_count": len(pattern_sections),
    }

    unsupported_claims: list[dict] = []
    invalid_evidence_refs: list[dict] = []
    for claim_id, section in claim_sections.items():
        support_line = field_value(section, "支持证据")
        refs = sorted(set(EVID_RE.findall(support_line)))
        if not refs:
            unsupported_claims.append({"claim": claim_id, "reason": "no_evidence_ref"})
        bad = [ref for ref in refs if ref not in evidence_ids]
        if bad:
            invalid_evidence_refs.append({"claim": claim_id, "refs": bad})

    pattern_missing_fields: list[dict] = []
    pattern_invalid_refs: list[dict] = []
    for pattern_id, section in pattern_sections.items():
        missing_fields = [field for field in PATTERN_FIELDS if not field_value(section, field)]
        if missing_fields:
            pattern_missing_fields.append(
                {"pattern": pattern_id, "missing_fields": missing_fields}
            )

        source_line = field_value(section, "证据来源")
        evid_refs = set(EVID_RE.findall(source_line))
        claim_refs = set(CLAIM_RE.findall(source_line))
        bad_evid = sorted(ref for ref in evid_refs if ref not in evidence_ids)
        bad_claim = sorted(ref for ref in claim_refs if ref not in claim_ids)
        if not evid_refs and not claim_refs:
            pattern_invalid_refs.append(
                {"pattern": pattern_id, "reason": "no_claim_or_evidence_ref"}
            )
        elif bad_evid or bad_claim:
            pattern_invalid_refs.append(
                {
                    "pattern": pattern_id,
                    "bad_evidence_refs": bad_evid,
                    "bad_claim_refs": bad_claim,
                }
            )

    long_short_evidence: list[dict] = []
    for evid_id, section in evidence_sections.items():
        value = field_value(section, "短证据")
        if len(value) > args.short_evidence_max_chars:
            long_short_evidence.append(
                {"evidence": evid_id, "chars": len(value)}
            )

    limits_lower = texts["limits"].lower()
    self_limits_checks = {
        "mentions_sampled": "sampled" in limits_lower,
        "mentions_opening": "opening" in limits_lower,
        "mentions_middle": "middle" in limits_lower,
        "mentions_whole_book_limit": any(
            token in texts["limits"]
            for token in ("整书", "全书", "不能下", "不能推断", "未覆盖")
        ),
    }

    structural_pass = not any(
        (
            missing,
            not evidence_ids,
            not claim_ids,
            not pattern_sections,
            unsupported_claims,
            invalid_evidence_refs,
            pattern_missing_fields,
            pattern_invalid_refs,
            duplicate_checks["evidence_heading_count"]
            != duplicate_checks["evidence_unique_count"],
            duplicate_checks["claim_heading_count"]
            != duplicate_checks["claim_unique_count"],
            duplicate_checks["pattern_heading_count"]
            != duplicate_checks["pattern_unique_count"],
            not all(self_limits_checks.values()),
        )
    )

    report = {
        "runner_dir": str(root),
        "structural_pass": structural_pass,
        "missing_files": missing,
        "counts": {
            "evidence": len(evidence_ids),
            "claims": len(claim_ids),
            "patterns": len(pattern_sections),
        },
        "duplicate_checks": duplicate_checks,
        "unsupported_claims": unsupported_claims,
        "invalid_evidence_refs": invalid_evidence_refs,
        "pattern_missing_fields": pattern_missing_fields,
        "pattern_invalid_refs": pattern_invalid_refs,
        "source_copy_risk": {
            "long_short_evidence": long_short_evidence,
            "note": "这是启发式风险提示，不代表版权结论。",
        },
        "self_limits_checks": self_limits_checks,
        "not_evaluated": [
            "文学质量",
            "推断是否真正正确",
            "机制因果是否成立",
            "机制是否值得迁移",
            "人工阅读价值",
        ],
    }

    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    print(payload, end="")
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")

    return 0 if structural_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
