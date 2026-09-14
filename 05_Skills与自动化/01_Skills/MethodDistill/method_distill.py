#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MethodDistill —— METHOD_SOURCE 方法知识蒸馏（确定性阶段）。

不是 BookDistill 换标签：语义抽取合同是方法取向的（原则/诊断/程序/检查单/失效模式）。
操作模式沿用 BookDistill 的三段式：

    确定性 validate/prepare → Agent 语义阅读/抽取 → 确定性 assemble/finalize

本模块只实现确定性阶段（无模型）。Agent 抽取阶段由 07_工作台应用 backend 的
materials 操作按持久化 Settings 的 Direct/Interactive 路由执行（复用现有任务
基础设施，不创建第二套 Agent runtime）。

输入（唯一）：
    06_工作区/MethodPrepare/<asset_id>_<名称>/（必须 PASS）

输出：
    02_素材知识库/<asset_id>_<名称>/method/
    ├─ identity.json          gowrite_method_knowledge/v1
    ├─ method_profile.md      方法书身份/覆盖/边界（Agent 填写）
    ├─ evidence.md            精选证据（Agent 填写）
    ├─ distill_manifest.json  定稿清单（finalize 写入）
    └─ knowledge/
       └─ cards.md            规范方法卡（M0001...，Agent 填写，finalize 严格校验）

方法卡规范字段：
    statement / method_kind(principle|diagnostic|procedure|checklist|failure_mode) /
    dimension / conditions / steps[] / checks[] / failure_modes[] / scope / boundary /
    confidence / use_stages[] / problem_types[] / tags[] / evidence[] /
    capability_candidate(true|false)

定稿规则（finalize，全部机械可判定）：
  - 拒绝非 PASS 的 MethodPrepare 输入；
  - 拒绝重复卡 id / 空 statement / 非法 method_kind；
  - 拒绝断裂证据引用（每张实质卡必须可追溯到 MethodPrepare 节/行证据）；
  - 拒绝过期来源指纹（source_sha256 / prepare 内容指纹不一致）；
  - 拒绝统一 KnowledgeRetrieve 加载器无法解析的包；
  - 全部通过才写 schema_status = FINALIZED_RETRIEVAL_READY。

边界：
  - capability_candidate=true 仅表示"潜在可执行的方法知识"，绝不创建/提升任何
    Skill，绝不自动写 05_Skills与自动化；
  - 方法源绝不自动进入 04_写作知识库；
  - MethodDistill 输出是来源绑定知识，不是已验证普适真理。

用法：
  python method_distill.py validate --input <mp_dir>
  python method_distill.py prepare  --input <mp_dir> --output <method_dir>
  python method_distill.py finalize --input <mp_dir> --output <method_dir>
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

SCHEMA_VERSION = "gowrite_method_knowledge/v1"
FINALIZED_STATUS = "FINALIZED_RETRIEVAL_READY"
METHOD_KINDS = ("principle", "diagnostic", "procedure", "checklist", "failure_mode")
CONFIDENCES = ("高", "中", "低")
CARD_ID_RE = re.compile(r"^M\d{4,}$")
EVIDENCE_RE = re.compile(r"^sections/S\d{4}\.md#L(\d+)(?:-L(\d+))?$")
LIST_FIELDS = ("steps", "checks", "failure_modes", "use_stages", "problem_types", "tags", "evidence")
GATE_VERSION = "0.5.0"

# MethodDistill 复用 BookDistill 的确定性 reading manifest/ledger/completion
# primitive（任务书 §7：复用最小 deterministic batching/ledger/completion）。
# 方法取向语义合同保持不变：不加 BookDistill Observer，不用六域，
# batch note 只要求结构化 JSON（batch_id + finding_count），required_domains 为空。
_BOOK_DISTILL_SCRIPTS = Path(__file__).resolve().parent.parent / "BookDistill" / "scripts"


def _load_reading_ledger():
    if str(_BOOK_DISTILL_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_BOOK_DISTILL_SCRIPTS))
    import reading_ledger as rl  # noqa: PLC0415
    return rl


# MethodDistill batch note 不强制叙事六域；方法语义由 finalize 的卡校验保证。
_METHOD_REQUIRED_DOMAINS: tuple[str, ...] = ()


class MethodDistillError(Exception):
    pass


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# MethodPrepare 输入校验
# --------------------------------------------------------------------------- #

def load_prepare_metadata(mp_dir: Path) -> dict:
    meta_path = mp_dir / "metadata.json"
    if not meta_path.exists():
        raise MethodDistillError(f"缺少 MethodPrepare metadata.json：{mp_dir}")
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MethodDistillError(f"MethodPrepare metadata 无法解析：{exc}") from exc
    if not isinstance(meta, dict):
        raise MethodDistillError("MethodPrepare metadata 结构无效")
    return meta


def validate_input(mp_dir: Path) -> dict:
    """只接受有效的 MethodPrepare PASS 包。"""
    mp_dir = Path(mp_dir)
    meta = load_prepare_metadata(mp_dir)
    if meta.get("status") != "PASS":
        raise MethodDistillError(
            f"MethodPrepare 状态 {meta.get('status')!r} ≠ PASS，不得进入 MethodDistill")
    if not (mp_dir / "full.md").exists():
        raise MethodDistillError("MethodPrepare 包缺少 full.md")
    structure_path = mp_dir / "structure.json"
    if not structure_path.exists():
        raise MethodDistillError("MethodPrepare 包缺少 structure.json")
    try:
        structure = json.loads(structure_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MethodDistillError(f"structure.json 无法解析：{exc}") from exc
    sections = structure.get("sections") or []
    for sec in sections:
        if not (mp_dir / sec.get("file", "")).exists():
            raise MethodDistillError(f"structure.json 引用的分节文件缺失：{sec.get('file')}")
    sel = meta.get("selected_source")
    if not isinstance(sel, dict) or not sel.get("sha256"):
        raise MethodDistillError("MethodPrepare metadata 缺少 selected_source.sha256")
    return meta


# --------------------------------------------------------------------------- #
# prepare：确定性脚手架（Agent 填写前）
# --------------------------------------------------------------------------- #

_IDENTITY_TEMPLATE = """# 方法书 Profile（MethodDistill Agent 填写）

## 身份
- 书名 / 作者 / 领域：（填写）

## 方法取向
- 该书教授的核心方法是什么：（填写）
- 适用创作阶段与问题类型：（填写）

## 覆盖范围与置信度
- （填写）

## 边界与不确定性
- （区分原书主张与 Go Write 已验证事实；不随意外推）
"""

_EVIDENCE_TEMPLATE = """# MethodDistill 精选证据（Agent 填写）

> 每条结论必须可追溯到 MethodPrepare 节/行证据：`sections/S####.md#Lx-Ly`。
> 区分原书主张（source claim）与 Go Write 已验证真理（validated truth）。
"""

_CARDS_TEMPLATE = """# 方法卡（MethodDistill 规范格式；M0001 起，id 不得重复）

<!-- 每张卡必须填写：
## M0001｜卡片标题
- statement: 一句话方法陈述（非空）
- method_kind: principle | diagnostic | procedure | checklist | failure_mode
- dimension: 创作维度（如 人物构建 / 叙事节奏 / 信息管理）
- conditions: 适用条件
- steps:
  - 步骤 1
- checks:
  - 检查项 1
- failure_modes:
  - 失效模式 1
- scope: 适用范围
- boundary: 边界/不适用场景
- confidence: 高 | 中 | 低
- use_stages: 构思, 规划, 写作, 检查
- problem_types: 问题类型
- tags: 标签
- evidence:
  - sections/S0001.md#L1-L10
- capability_candidate: false
-->
"""


def prepare_scaffold(mp_dir: Path, out_dir: Path, *, request_id: str | None = None,
                     run_id: str | None = None) -> dict:
    meta = validate_input(mp_dir)
    out_dir = Path(out_dir)
    sel = meta["selected_source"]
    source_snapshot = {
        "source_sha256": sel.get("sha256") or "",
        "prepare_fingerprint": meta.get("content_fingerprint") or "",
        "prepare_input_fingerprint": meta.get("input_fingerprint") or "",
    }
    identity = {
        "schema_version": SCHEMA_VERSION,
        "schema_status": "DRAFT",
        "source_kind": "method_source",
        "source_id": meta.get("asset_id") or "",
        "title": meta.get("asset_name") or "",
        "author": "",
        "maturity": "source_bound",
        "source_snapshot": source_snapshot,
    }
    _write(out_dir / "identity.json", json.dumps(identity, ensure_ascii=False, indent=2) + "\n")
    for fname, tmpl in (("method_profile.md", _IDENTITY_TEMPLATE),
                        ("evidence.md", _EVIDENCE_TEMPLATE),
                        ("knowledge/cards.md", _CARDS_TEMPLATE)):
        path = out_dir / fname
        if not path.exists():  # 绝不覆盖 Agent 已有产出
            _write(path, tmpl)

    # Reading manifest + ledger（复用 BookDistill primitive；按 sections/ 分节）。
    # 大型技巧资料不允许“一次上下文直接吃完全文”；逐批阅读 + 磁盘 ledger 可恢复。
    rl = _load_reading_ledger()
    rid = request_id or _infer_request_id(out_dir)
    units = rl.discover_section_units(mp_dir)
    manifest = rl.build_manifest_from_units(
        units, request_id=rid, run_id=run_id or rid,
        source_id=str(meta.get("asset_id") or ""),
        source_snapshot=source_snapshot, unit_semantics="section",
    )
    rl.write_manifest(out_dir, manifest)
    rl.init_ledger(out_dir, manifest)
    return identity


def _infer_request_id(out_dir: Path) -> str:
    """Derive a stable request_id from the staging directory name."""
    name = Path(out_dir).name
    if name == "method":  # staging 结构为 <request_id>_<asset>/method
        name = Path(out_dir).parent.name
    match = re.match(r"^([0-9a-f]{16,})_", name)
    if match:
        return match.group(1)
    return name or "manual"


# --------------------------------------------------------------------------- #
# 方法卡解析（委托统一 KnowledgeRetrieve 卡语法：单一真源，绝不双份实现）
# --------------------------------------------------------------------------- #

def _load_knowledge_retrieve_runtime():
    kr_dir = Path(__file__).resolve().parent.parent / "KnowledgeRetrieve"
    if str(kr_dir) not in sys.path:
        sys.path.insert(0, str(kr_dir))
    module_name = "ai_write_knowledge_retrieve_runtime"
    module = sys.modules.get(module_name)
    if module is None:
        spec = importlib.util.spec_from_file_location(module_name, kr_dir / "run.py")
        if spec is None or spec.loader is None:
            raise MethodDistillError("无法加载 KnowledgeRetrieve")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    return module


def parse_method_cards(cards_path: Path) -> tuple[list[dict], list[str]]:
    """解析规范方法卡（与检索加载器同一合同）。返回 (cards, errors)。"""
    module = _load_knowledge_retrieve_runtime()
    return module.parse_cards_generic(Path(cards_path))


def _validate_cards(cards: list[dict], mp_dir: Path) -> list[str]:
    """定稿级卡校验：重复 id / 空 statement / 非法字段 / 断裂证据引用。"""
    errors: list[str] = []
    seen: set[str] = set()
    section_lines: dict[str, int] = {}
    for card in cards:
        cid = card.get("id", "")
        if not CARD_ID_RE.match(cid):
            errors.append(f"卡 id 非法（应形如 M0001）：{cid!r}")
        if cid in seen:
            errors.append(f"卡 id 重复：{cid}")
        seen.add(cid)
        if not (card.get("statement") or "").strip():
            errors.append(f"{cid or '?'}：statement 为空")
        kind = card.get("method_kind") or ""
        if kind not in METHOD_KINDS:
            errors.append(f"{cid}：method_kind 非法 {kind!r}（允许：{', '.join(METHOD_KINDS)}）")
        conf = card.get("confidence")
        if conf and conf not in CONFIDENCES:
            errors.append(f"{cid}：confidence 非法 {conf!r}")
        cc = card.get("capability_candidate")
        if cc is not None and str(cc).lower() not in ("true", "false"):
            errors.append(f"{cid}：capability_candidate 必须是 true|false")
        evidence = card.get("evidence") or []
        if not evidence:
            errors.append(f"{cid}：缺少 evidence（实质卡必须可追溯到 MethodPrepare 证据）")
        for ref in evidence:
            m = EVIDENCE_RE.match(ref)
            if not m:
                errors.append(f"{cid}：证据引用格式非法：{ref!r}（应形如 sections/S0001.md#L1-L10）")
                continue
            sec_file = ref.split("#")[0]
            sec_path = mp_dir / sec_file
            if not sec_path.exists():
                errors.append(f"{cid}：证据引用指向不存在的分节：{sec_file}")
                continue
            if sec_file not in section_lines:
                section_lines[sec_file] = len(_read(sec_path).split("\n"))
            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else start
            if start < 1 or end < start or start > section_lines[sec_file]:
                errors.append(f"{cid}：证据行号越界：{ref}（分节共 {section_lines[sec_file]} 行）")
    return errors


# --------------------------------------------------------------------------- #
# KnowledgeRetrieve 机械可加载性校验（同一加载器，绝不另造解析）
# --------------------------------------------------------------------------- #

def check_retrieval_loadable(method_dir: Path) -> list:
    """用统一 KnowledgeRetrieve 的方法加载器机械加载该包；不可解析 → 拒绝定稿。"""
    module = _load_knowledge_retrieve_runtime()
    try:
        items = module.load_method_package(method_dir)
    except Exception as exc:  # noqa: BLE001 — 加载器抛错即不可加载
        raise MethodDistillError(f"KnowledgeRetrieve 无法加载该方法包：{exc}") from exc
    if not items:
        raise MethodDistillError("KnowledgeRetrieve 加载结果为空：定稿包必须含可检索知识条目")
    return items


# --------------------------------------------------------------------------- #
# finalize：确定性定稿（唯一可写 FINALIZED_RETRIEVAL_READY 的路径）
# --------------------------------------------------------------------------- #

def finalize(mp_dir: Path, out_dir: Path) -> dict:
    mp_dir, out_dir = Path(mp_dir), Path(out_dir)
    meta = validate_input(mp_dir)
    identity_path = out_dir / "identity.json"
    if not identity_path.exists():
        raise MethodDistillError("缺少 identity.json（请先运行 prepare 脚手架）")
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    if identity.get("schema_version") != SCHEMA_VERSION:
        raise MethodDistillError(f"identity schema_version 非法：{identity.get('schema_version')!r}")
    if str(identity.get("source_id") or "") != str(meta.get("asset_id") or ""):
        raise MethodDistillError("identity.source_id 与 MethodPrepare asset_id 不一致")
    if not (identity.get("title") or "").strip():
        raise MethodDistillError("identity.title 为空")

    # 过期来源指纹：来源 SHA / prepare 内容指纹必须与当前 MethodPrepare 一致
    snap = identity.get("source_snapshot") or {}
    sel = meta.get("selected_source") or {}
    if snap.get("source_sha256") != (sel.get("sha256") or ""):
        raise MethodDistillError(
            "来源指纹过期（source_sha256 与 MethodPrepare 不一致），请重新提纯/蒸馏")
    if snap.get("prepare_fingerprint") != (meta.get("content_fingerprint") or ""):
        raise MethodDistillError(
            "来源指纹过期（prepare 内容指纹与 MethodPrepare 不一致），请重新提纯/蒸馏")

    cards, parse_errors = parse_method_cards(out_dir / "knowledge" / "cards.md")
    errors = list(parse_errors) + _validate_cards(cards, mp_dir)
    if errors:
        raise MethodDistillError("定稿校验失败：\n- " + "\n- ".join(errors[:30]))

    # Reading ledger 完整性：全部 section batch 必须 completed（可恢复全量阅读权威）。
    # 仅有 Agent 自报“已读全文”、仅有 scan 范围都不得通过。
    rl = _load_reading_ledger()
    units = rl.discover_section_units(mp_dir)
    ledger_check = rl.validate_ledger(out_dir, required_domains=_METHOD_REQUIRED_DOMAINS, units=units)
    if not ledger_check.get("ok"):
        raise MethodDistillError(
            "阅读 ledger 校验失败：\n- " + "\n- ".join(ledger_check.get("errors", [])[:20]))
    if not ledger_check.get("complete"):
        raise MethodDistillError(
            f"阅读 ledger 未全部 completed（{ledger_check.get('completed_batches', 0)}/"
            f"{ledger_check.get('total_batches', 0)}），不得定稿。")

    # 机械可加载性：统一 KnowledgeRetrieve provider 必须能加载该包。
    # 加载器只接受 FINALIZED 身份 → 先落盘定稿状态，加载失败时回滚为 DRAFT。
    identity["schema_status"] = FINALIZED_STATUS
    _write(identity_path, json.dumps(identity, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    try:
        check_retrieval_loadable(out_dir)
    except MethodDistillError:
        identity["schema_status"] = "DRAFT"
        _write(identity_path, json.dumps(identity, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
        raise

    manifest = {
        "schema": "gowrite_method_distill_manifest/v1",
        "status": "FINALIZED",
        "source_id": identity["source_id"],
        "title": identity["title"],
        "card_count": len(cards),
        "capability_candidate_count": sum(
            1 for c in cards if str(c.get("capability_candidate", "")).lower() == "true"),
        "evidence_refs_total": sum(len(c.get("evidence") or []) for c in cards),
        "source_snapshot": dict(snap),
        "reading_ledger": {
            "total_batches": ledger_check.get("total_batches", 0),
            "completed_batches": ledger_check.get("completed_batches", 0),
        },
        "identity_fingerprint": _sha256_text(
            json.dumps(identity, ensure_ascii=False, sort_keys=True)),
    }
    _write(out_dir / "distill_manifest.json",
           json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n")

    # 确定性 completion receipt（ledger 完整 + 定稿全部通过后）。
    reading_manifest = rl.read_manifest(out_dir)
    if reading_manifest is not None:
        rl.write_completion_receipt(
            out_dir,
            request_id=str(reading_manifest.get("request_id") or ""),
            run_id=str(reading_manifest.get("run_id") or ""),
            source_id=str(identity["source_id"]),
            source_snapshot=dict(snap),
            acceptance_status="PASS",
            canonical_card_count=len(cards),
            gate_version=GATE_VERSION,
        )
    return manifest


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _cmd_reading(args) -> int:
    """reading-status / reading-next / reading-commit / reading-validate."""
    rl = _load_reading_ledger()
    out_dir = Path(args.output)
    if args.cmd == "reading-status":
        print(json.dumps(rl.ledger_status(out_dir), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "reading-next":
        batch = rl.next_pending_batch(out_dir)
        if batch is None:
            print(json.dumps({"ok": True, "complete": True, "batch": None}, ensure_ascii=False, indent=2))
            return 0
        manifest = rl.read_manifest(out_dir) or {}
        payload = {
            "ok": True, "complete": False, "batch": batch,
            "request_id": manifest.get("request_id"),
            "run_id": manifest.get("run_id"),
            "manifest_hash": manifest.get("manifest_hash"),
            "source_fingerprint": manifest.get("source_fingerprint"),
            "note_template": rl.render_batch_note_template(
                batch_id=batch["batch_id"],
                request_id=manifest.get("request_id") or "",
                run_id=manifest.get("run_id") or "",
                manifest_hash=manifest.get("manifest_hash") or "",
                source_fingerprint=manifest.get("source_fingerprint") or "",
                spans=batch.get("spans") or [],
                required_domains=_METHOD_REQUIRED_DOMAINS,
                domain_heading="方法抽取检查（本批是否已直接阅读原文并抽取方法卡）",
            ),
            "note_path": str(rl.batch_notes_dir(out_dir) / f"{batch['batch_id']}.md"),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "reading-commit":
        note = Path(args.note) if getattr(args, "note", None) else (
            rl.batch_notes_dir(out_dir) / f"{args.batch}.md")
        try:
            result = rl.commit_batch(out_dir, args.batch, note,
                                     required_domains=_METHOD_REQUIRED_DOMAINS)
        except rl.ReadingLedgerError as exc:
            print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False, indent=2))
            return 1
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    # reading-validate
    mp_dir = Path(args.input)
    units = rl.discover_section_units(mp_dir)
    result = rl.validate_ledger(out_dir, required_domains=_METHOD_REQUIRED_DOMAINS, units=units)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="MethodDistill 确定性阶段（validate/prepare/finalize/reading-*）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("validate", "prepare", "finalize"):
        p = sub.add_parser(name)
        p.add_argument("--input", required=True, help="MethodPrepare PASS 包目录")
        if name in ("prepare", "finalize"):
            p.add_argument("--output", required=True, help="02_素材知识库/<asset>_<名称>/method 目录")
        if name == "prepare":
            p.add_argument("--request-id", dest="request_id", default=None, help="当前请求 id（绑定 reading manifest/ledger）")
            p.add_argument("--run-id", dest="run_id", default=None, help="当前运行 id（缺省与 request-id 一致）")
    # reading-* 子命令（复用 BookDistill primitive）
    p_rs = sub.add_parser("reading-status", help="显示阅读 ledger 进度")
    p_rs.add_argument("--output", required=True)
    p_rn = sub.add_parser("reading-next", help="返回下一个未完成批次与 batch note 模板")
    p_rn.add_argument("--output", required=True)
    p_rc = sub.add_parser("reading-commit", help="提交一个已完成阅读批次")
    p_rc.add_argument("--output", required=True)
    p_rc.add_argument("--batch", required=True)
    p_rc.add_argument("--note", default=None)
    p_rv = sub.add_parser("reading-validate", help="机械验证 manifest 覆盖 + ledger 完整性")
    p_rv.add_argument("--input", required=True)
    p_rv.add_argument("--output", required=True)
    args = ap.parse_args(argv)
    try:
        if args.cmd == "validate":
            validate_input(Path(args.input))
            print("[method_distill] validate OK")
        elif args.cmd == "prepare":
            prepare_scaffold(Path(args.input), Path(args.output),
                             request_id=getattr(args, "request_id", None),
                             run_id=getattr(args, "run_id", None))
            print("[method_distill] prepare OK（脚手架 + reading manifest/ledger 已生成，等待 Agent 抽取）")
        elif args.cmd == "finalize":
            manifest = finalize(Path(args.input), Path(args.output))
            print(f"[method_distill] finalize OK：{manifest['card_count']} 张方法卡，"
                  f"status=FINALIZED_RETRIEVAL_READY")
        else:
            return _cmd_reading(args)
    except MethodDistillError as exc:
        print(f"[method_distill] ERROR: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
