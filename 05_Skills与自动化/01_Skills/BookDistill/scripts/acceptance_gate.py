# -*- coding: utf-8 -*-
"""BookDistill 全书验收门（acceptance gate，确定性脚本，非服务）。

新协议（bkp_protocol_version=0.3 / protocol=gowrite_bkp_acceptance/v1）要求：
新蒸馏的 BKP 在声明 retrieval-ready 之前，必须完成一次显式的全书综合审计
（BKP_ACCEPTANCE_REPORT.md），证明重要的全书级发现确实成为可追溯的 canonical
cards，或已显式说明不入卡原因。本脚本只做机械验证（无模型、无网络）：

  - 报告身份与 bkp/identity.json / source_snapshot 指纹一致
  - 报告的 canonical_card_count 与 knowledge/cards.md 实际卡数一致
  - 报告引用的 card id 真实存在、无重复、无虚构
  - 每个已接受重要发现至少映射一张卡；不入卡发现必须有显式原因
  - PASS 不得与 blocking 未解决缺口共存；retrieval_ready 与状态一致
  - 卡片 evidence 满足 `chapters/NNNN.md#Lx` 溯源格式；若 SourcePrepare
    快照目录可解析，章节文件必须存在（快照缺失仅告警，不阻塞）

用法：
  python acceptance_gate.py <asset_dir> [--write-identity]

`--write-identity`：全部校验通过后才把 acceptance 块写入 bkp/identity.json
（原子写）；KnowledgeRetrieve 依据该块决定新协议包是否可检索。
旧版 v0.1/v0.2 BKP 没有 acceptance 块，保持原有可检索行为（向后兼容）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import os
from pathlib import Path

try:  # package-style import when loaded as a module
    import reading_ledger as rl
except ModuleNotFoundError:  # pragma: no cover - script-style import
    from . import reading_ledger as rl  # type: ignore

REPORT_NAME = "BKP_ACCEPTANCE_REPORT.md"
ACCEPTANCE_SCHEMA = "gowrite_bkp_acceptance/v1"
ACCEPTANCE_PROTOCOL_VERSION = "0.3"
GATE_VERSION = "0.5.0"
EVIDENCE_RE = re.compile(r"^chapters/(\d{4})\.md#L(\d+)(?:-L?(\d+))?$")
CARD_HEADER_RE = re.compile(r"^##\s*K(\d{3,4})\b")
DATA_BLOCK_RE = re.compile(
    r"```json\s*\n(.*?)\n```", re.DOTALL,
)

REQUIRED_DATA_KEYS = {
    "schema", "book_id", "title", "source_sha256", "protocol", "status",
    "canonical_card_count", "findings", "unresolved_gaps", "retrieval_ready",
}


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _atomic_write_json(path: Path, value: dict) -> None:
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".bkp-acceptance-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def parse_card_ids(cards_path: Path) -> list[str]:
    """解析 knowledge/cards.md 的 canonical card id（KNNN）。"""
    if not cards_path.exists():
        return []
    ids: list[str] = []
    for line in cards_path.read_text(encoding="utf-8").splitlines():
        match = CARD_HEADER_RE.match(line.strip())
        if match:
            ids.append(f"K{match.group(1)}")
    return ids


def parse_report_data(report_path: Path) -> tuple[dict | None, str | None]:
    """提取报告中的结构化 acceptance_data JSON 块。"""
    if not report_path.exists():
        return None, f"缺少全书验收报告：{REPORT_NAME}"
    text = report_path.read_text(encoding="utf-8")
    for block in DATA_BLOCK_RE.findall(text):
        try:
            value = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and value.get("schema") == ACCEPTANCE_SCHEMA:
            return value, None
    return None, f"报告中缺少结构化 acceptance_data 块（schema={ACCEPTANCE_SCHEMA}）。"


def card_evidence_entries(cards_path: Path) -> list[tuple[str, str]]:
    """返回 (card_id, evidence_ref) 列表：兼容内联与嵌套列表两种 evidence 写法。"""
    if not cards_path.exists():
        return []
    entries: list[tuple[str, str]] = []
    current = ""
    in_evidence = False
    for line in cards_path.read_text(encoding="utf-8").splitlines():
        header = CARD_HEADER_RE.match(line.strip())
        if header:
            current = f"K{header.group(1)}"
            in_evidence = False
            continue
        stripped = line.strip()
        if stripped.lower().startswith("- evidence:"):
            value = stripped.split(":", 1)[1].strip()
            if value:
                for ref in value.split(","):
                    if ref.strip():
                        entries.append((current, ref.strip()))
                in_evidence = False
            else:
                in_evidence = True
            continue
        if in_evidence:
            if stripped.startswith("-") and line.startswith((" ", "\t")):
                entries.append((current, stripped.lstrip("- ").strip()))
                continue
            in_evidence = False
    return entries


def resolve_sourceprepare_dir(repo_root: Path, book_id: str) -> Path | None:
    sp_root = repo_root / "06_工作区" / "SourcePrepare"
    if not sp_root.exists():
        return None
    for entry in sorted(sp_root.iterdir()):
        if entry.is_dir() and entry.name.startswith(f"{book_id}_"):
            return entry
    return None


def validate_acceptance(
    asset_dir: Path,
    repo_root: Path | None = None,
) -> dict:
    """机械验证全书验收报告与 BKP 的一致性（只读）。

    返回 {"ok", "errors", "warnings", "status", "retrieval_ready", "card_count"}。
    """
    asset_dir = Path(asset_dir)
    errors: list[str] = []
    warnings: list[str] = []

    bkp_dir = asset_dir / "bkp"
    identity = _read_json(bkp_dir / "identity.json")
    if identity is None:
        return {
            "ok": False, "errors": ["bkp/identity.json 缺失或不可解析。"],
            "warnings": [], "status": None, "retrieval_ready": False, "card_count": 0,
        }

    report_data, report_error = parse_report_data(asset_dir / REPORT_NAME)
    if report_error or report_data is None:
        return {
            "ok": False, "errors": [report_error or "报告不可解析。"],
            "warnings": [], "status": None, "retrieval_ready": False, "card_count": 0,
        }

    missing = sorted(REQUIRED_DATA_KEYS - set(report_data))
    if missing:
        errors.append(f"acceptance_data 缺少字段：{', '.join(missing)}。")

    book = identity.get("book") if isinstance(identity.get("book"), dict) else {}
    snapshot = identity.get("source_snapshot") if isinstance(identity.get("source_snapshot"), dict) else {}
    if report_data.get("book_id") != book.get("book_id"):
        errors.append("报告 book_id 与 identity.json 不一致。")
    if report_data.get("title") != book.get("title"):
        errors.append("报告书名与 identity.json 不一致。")
    if report_data.get("source_sha256") != snapshot.get("source_sha256"):
        errors.append("报告来源指纹（source_sha256）与 identity.json source_snapshot 不一致。")
    if report_data.get("protocol") != ACCEPTANCE_SCHEMA:
        errors.append("报告协议版本非法（必须为 gowrite_bkp_acceptance/v1）。")

    manifest = _read_json(asset_dir / "distill_manifest.json")
    if manifest is None:
        errors.append("缺少或无法解析 distill_manifest.json。")
    else:
        if manifest.get("source_snapshot") != snapshot:
            errors.append("distill_manifest source_snapshot 与 BKP identity 不一致。")
        if manifest.get("unit_semantics") not in {"chapter", "reading_unit"}:
            errors.append("distill_manifest 缺少可信 unit_semantics。")

    # ---- 阅读完成度权威：reading manifest + ledger（不再是 scan_refs）----
    # scan_refs / scan_coverage 仅保留为调试信号，绝不作为 whole-book reading
    # completion 的权威证据。仅填写全范围 scan_refs、仅有完整行号范围、
    # 仅有 Agent 自报“已读”都必须在此失败。
    sp_dir = resolve_sourceprepare_dir(repo_root, book.get("book_id") or "") if repo_root else None
    reading_manifest = rl.read_manifest(asset_dir)
    reading_ledger = rl.read_ledger(asset_dir)
    if reading_manifest is None:
        errors.append("缺少 reading_manifest.json：无法证明全书阅读计划绑定当前来源。")
    if reading_ledger is None:
        errors.append("缺少 reading_ledger.json：无法证明全书阅读已结算。")
    if reading_manifest is not None and reading_ledger is not None:
        if reading_manifest.get("source_snapshot") != snapshot:
            errors.append("reading manifest source_snapshot 与 BKP identity 不一致（来源身份已变化）。")
        if sp_dir is not None:
            coverage = rl.validate_manifest_coverage(reading_manifest, sp_dir)
            if not coverage.get("ok"):
                errors.append(
                    "reading manifest 未完整覆盖当前冻结来源（存在 gap/overlap/缺失单元）："
                    + "；".join(coverage.get("errors", [])[:5])
                )
        else:
            warnings.append("SourcePrepare 快照不可解析：reading manifest 覆盖只做结构校验。")
        ledger_check = rl.validate_ledger(asset_dir, sp_dir) if sp_dir is not None else None
        if ledger_check is None:
            # 无 sp_dir 时仍做 ledger 与 manifest 一致性 + 批次 completed 校验。
            status_view = rl.ledger_status(asset_dir)
            if not status_view.get("ok"):
                errors.extend(status_view.get("errors", []))
            if not status_view.get("complete"):
                errors.append("reading ledger 未全部 completed：全书阅读尚未结算。")
        else:
            if not ledger_check.get("ok"):
                errors.extend(ledger_check.get("errors", [])[:8])
            if not ledger_check.get("complete"):
                errors.append("reading ledger 未全部 completed：全书阅读尚未结算。")
        # 六域 checked 审计：每个 completed batch 的 note 必须检查全部六域（0 findings 合法）。
        batches = (reading_ledger.get("batches") or {})
        for batch_id, state in sorted(batches.items()):
            if state.get("status") != rl.BATCH_STATUS_COMPLETED:
                continue
            checked = state.get("domains_checked") or state.get("six_domains_checked") or []
            missing = [d for d in rl.SIX_DOMAINS if d not in checked]
            if missing:
                errors.append(f"batch {batch_id} 未检查全部六域，缺：{missing}。")

    # bd_report 关键统计必须由同一权威 manifest 生成（不再沿用陈旧中间计数）。
    if manifest is not None:
        try:
            report_text = (asset_dir / "bd_report.md").read_text(encoding="utf-8")
        except OSError:
            report_text = ""
        expected_stats = [
            f"- 证据条目总数：{manifest.get('total_entries', 0)}",
            f"- 分类统计：{json.dumps(manifest.get('stats_by_kind', {}), ensure_ascii=False)}",
            f"- 输入单元语义：{manifest.get('unit_semantics')}",
        ]
        if not report_text or any(line not in report_text for line in expected_stats):
            errors.append("bd_report.md 的关键统计与最终权威 manifest 不一致。")

    status = report_data.get("status")
    if status not in {"PASS", "REVIEW"}:
        errors.append("acceptance status 必须是 PASS 或 REVIEW。")

    cards_path = bkp_dir / "knowledge" / "cards.md"
    card_ids = parse_card_ids(cards_path)
    if not card_ids:
        errors.append("knowledge/cards.md 缺失或没有 canonical 卡片。")
    duplicates = sorted({cid for cid in card_ids if card_ids.count(cid) > 1})
    if duplicates:
        errors.append(f"卡片 id 重复：{', '.join(duplicates)}。")
    card_count = len(set(card_ids))
    if report_data.get("canonical_card_count") != card_count:
        errors.append(
            f"报告 canonical_card_count={report_data.get('canonical_card_count')} 与实际卡数 {card_count} 不一致。"
        )

    findings = report_data.get("findings")
    if not isinstance(findings, list) or not findings:
        errors.append("findings 必须是非空列表（全书综合审计至少给出一条结论）。")
    else:
        known_ids = set(card_ids)
        for index, finding in enumerate(findings):
            if not isinstance(finding, dict) or not isinstance(finding.get("finding"), str) or not finding["finding"].strip():
                errors.append(f"findings[{index}] 缺少有效 finding 描述。")
                continue
            accepted = finding.get("accepted", True)
            finding_cards = finding.get("card_ids") or []
            if accepted:
                if not isinstance(finding_cards, list) or not finding_cards:
                    errors.append(f"findings[{index}]（已接受发现）必须映射至少一张卡。")
                else:
                    unknown = [cid for cid in finding_cards if cid not in known_ids]
                    if unknown:
                        errors.append(f"findings[{index}] 映射了不存在或非法的卡：{', '.join(map(str, unknown))}。")
            else:
                reason = finding.get("exclusion_reason")
                if not isinstance(reason, str) or not reason.strip():
                    errors.append(f"findings[{index}]（不入卡发现）必须给出显式 exclusion_reason。")

    gaps = report_data.get("unresolved_gaps")
    if not isinstance(gaps, list):
        errors.append("unresolved_gaps 必须是列表（无缺口时为空列表）。")
    else:
        blocking = [
            gap for gap in gaps
            if isinstance(gap, dict) and gap.get("blocking")
        ]
        for index, gap in enumerate(gaps):
            if not isinstance(gap, dict) or not isinstance(gap.get("description"), str) or not gap["description"].strip():
                errors.append(f"unresolved_gaps[{index}] 缺少有效 description。")
        if status == "PASS" and blocking:
            errors.append("PASS 不得与 blocking 未解决缺口共存。")

    retrieval_ready = report_data.get("retrieval_ready")
    if not isinstance(retrieval_ready, bool):
        errors.append("retrieval_ready 必须是布尔值。")
    elif retrieval_ready != (status == "PASS"):
        errors.append("retrieval_ready 必须与验收状态一致（PASS=true / REVIEW=false）。")

    # evidence 溯源：格式必须合法；可解析 SourcePrepare 快照时，章节文件必须存在。
    evidence_entries = card_evidence_entries(cards_path)
    if not evidence_entries and card_ids:
        warnings.append("cards.md 未声明任何 evidence 行，无法机械验证溯源。")
    sp_dir = resolve_sourceprepare_dir(repo_root, book.get("book_id") or "") if repo_root else None
    if sp_dir is None and repo_root is not None:
        warnings.append("SourcePrepare 快照目录不可解析：evidence 只做格式校验。")
    for card_id, ref in evidence_entries:
        match = EVIDENCE_RE.match(ref)
        if not match:
            errors.append(f"卡 {card_id} 的 evidence 不符合 chapters/NNNN.md#Lx 格式：{ref}")
            continue
        if sp_dir is not None and not (sp_dir / "chapters" / f"{match.group(1)}.md").exists():
            errors.append(f"卡 {card_id} 的 evidence 指向不存在的快照章节：{ref}")

    ok = not errors
    return {
        "ok": ok,
        "errors": errors,
        "warnings": warnings,
        "status": status if status in {"PASS", "REVIEW"} else None,
        "retrieval_ready": bool(retrieval_ready) and ok and status == "PASS",
        "card_count": card_count,
    }


def write_identity_acceptance(asset_dir: Path, result: dict) -> None:
    """验证通过且状态为 PASS 后才把 acceptance 块写入 bkp/identity.json（原子；失败抛错）。

    同时在 reading ledger 完整结算的前提下写出确定性 completion receipt，
    作为 Qoder response 丢失时的可靠兑底信号。receipt 绝不绕过任何质量门：
    backend finalize 仍会独立重跑确定性 assemble/profile/bkp/acceptance/发布门。
    """
    if not result.get("ok") or result.get("status") != "PASS":
        raise RuntimeError("验收未通过或状态不是 PASS，绝不写入 acceptance 块。")
    identity_path = Path(asset_dir) / "bkp" / "identity.json"
    identity = _read_json(identity_path)
    if identity is None:
        raise RuntimeError("bkp/identity.json 缺失，无法写入 acceptance。")
    identity["acceptance"] = {
        "schema": ACCEPTANCE_SCHEMA,
        "required": True,
        "status": result["status"],
        "report": REPORT_NAME,
        "canonical_card_count": result["card_count"],
    }
    identity["bkp_protocol_version"] = ACCEPTANCE_PROTOCOL_VERSION
    _atomic_write_json(identity_path, identity)

    # 确定性 completion receipt（仅在 ledger 完整结算 + acceptance PASS 后写出）。
    manifest = rl.read_manifest(asset_dir)
    if manifest is not None and rl.is_ledger_complete(asset_dir):
        rl.write_completion_receipt(
            asset_dir,
            request_id=str(manifest.get("request_id") or ""),
            run_id=str(manifest.get("run_id") or ""),
            source_id=str(manifest.get("source_id") or ""),
            source_snapshot=manifest.get("source_snapshot") or {},
            acceptance_status="PASS",
            canonical_card_count=int(result.get("card_count") or 0),
            gate_version=GATE_VERSION,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BookDistill 全书验收门（确定性验证）")
    parser.add_argument("asset_dir", help="02_素材知识库/<book_id>_<名称> 目录")
    parser.add_argument(
        "--repo-root", default=None,
        help="仓库根（默认取脚本推导值；用于解析 SourcePrepare 快照）",
    )
    parser.add_argument(
        "--write-identity", action="store_true",
        help="全部校验通过后把 acceptance 块写入 bkp/identity.json",
    )
    args = parser.parse_args(argv)
    asset_dir = Path(args.asset_dir).resolve()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path(__file__).resolve().parents[4]
    result = validate_acceptance(asset_dir, repo_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.write_identity and result["ok"] and result.get("status") == "PASS":
        write_identity_acceptance(asset_dir, result)
        print("[OK] acceptance 块已写入 bkp/identity.json")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
