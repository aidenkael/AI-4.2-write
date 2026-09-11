# -*- coding: utf-8 -*-
"""素材目录 Author Operations：真实 canonical catalog（MaterialIntake）消费者。

职责（对应 UI 1.0 Materials 真实消费者）：
- list_materials：只读读取 `01_原始素材/素材资产.json`（canonical ledger）投影；
- refresh_materials：显式触发 MaterialIntake 确定性 catalog refresh（重算机器事实
  + 派生状态 + 三视图），无模型；
- scan_material_inbox：只读扫描 `01_原始素材/00_待入库`（MaterialIntake inbox scan）；
- apply_material_intake：作者显式选择 NEW_ASSET / ATTACH_EXISTING / REVIEW 后，
  走 MaterialIntake 的确定性 intake 事务（绝不绕过其 transaction/rollback）。

约束（严格遵守 MaterialIntake 合同）：
- 页面加载绝不调用 Agent / 模型 / SourcePrepare / BookDistill；refresh 只写
  三份 material state files + 由 MaterialIntake 派生三视图；
- intake 绝不绕过 MaterialIntake 的 transaction/rollback 规则；
- 绝不隐式执行 SourcePrepare / BookDistill（它们是离线 curation 工作）；
- §6：Workbench 素材热路径（intake / refresh / Prepare / Distill 结算）不依赖 Git
  （不 precheck / fetch / commit / push），不因 DIRTY_WORKTREE / 分支 / 远端状态失败；
  CLI 维护命令仍可显式支持 Git sync；
- 测试使用 temp roots。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from operations import execution_audit as audit
from operations import material_settlement

_REPO_ROOT = Path(__file__).resolve().parents[3]

_MI_DIR = _REPO_ROOT / "05_Skills与自动化" / "01_Skills" / "MaterialIntake"

# 允许从本地导入到 00_待入库 的素材后缀（MaterialIntake 支持的类型）
_SUPPORTED_IMPORT_SUFFIXES = {".epub", ".txt", ".pdf"}
# 单文件导入上限（200 MB；防误选超大文件）
_MAX_IMPORT_BYTES = 200 * 1024 * 1024


class MaterialsError(Exception):
    """素材目录操作错误（面向 UI 的稳定错误类型，普通用户可读）。"""


# ---------------------------------------------------------------------------
# MaterialIntake frozen runtime 加载（只 import，绝不复制其规则）
# ---------------------------------------------------------------------------

def _load_materialintake() -> tuple[Any, Any, Any]:
    """返回 (catalog, intake, post_action) 模块；失败抛 MaterialsError。"""
    if str(_MI_DIR) not in sys.path:
        sys.path.insert(0, str(_MI_DIR))
    try:
        import catalog  # noqa: F401
        import intake  # noqa: F401
        import post_action  # noqa: F401
    except Exception as exc:  # noqa: BLE001 — 模块加载失败是稳定错误
        raise MaterialsError(f"素材能力加载失败：{exc}") from exc
    return catalog, intake, post_action


def get_repo_root() -> Path:
    """仓库根目录（测试可 monkeypatch 本函数指向 temp root）。"""
    return _REPO_ROOT


# ---------------------------------------------------------------------------
# 只读投影
# ---------------------------------------------------------------------------

def _load_ledger(catalog: Any) -> dict[str, Any]:
    ledger_path = get_repo_root() / "01_原始素材" / "素材资产.json"
    try:
        return catalog.load_ledger(ledger_path)
    except (FileNotFoundError, RuntimeError) as exc:
        raise MaterialsError(str(exc)) from exc


def _bkp_acceptance_view(a: dict[str, Any]) -> str | None:
    """BKP 全书验收的真实作者面状态（确定性读 identity.json，零模型）。

    返回：None（无 BKP / 旧版 v0.1、v0.2 包，不要求验收）；
    "ready"（BKP 可检索）/ "review"（需要复核）/ "pending"（未完成全书验收）。
    """
    asset_id = str(a.get("id") or "").strip()
    if not asset_id:
        return None
    distill_root = get_repo_root() / "02_素材知识库"
    if not distill_root.exists():
        return None
    asset_dir = next(
        (entry for entry in sorted(distill_root.iterdir())
         if entry.is_dir() and entry.name.startswith(f"{asset_id}_")),
        None,
    )
    if asset_dir is None:
        return None
    try:
        identity = json.loads((asset_dir / "bkp" / "identity.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    acceptance = identity.get("acceptance")
    if not isinstance(acceptance, dict) or not acceptance.get("required"):
        return None  # 旧协议包：不要求全书验收，保持原有可检索语义。
    status = acceptance.get("status")
    if status == "PASS":
        return "ready"
    return "review" if status == "REVIEW" else "pending"


# 作者可见类型只有三种（§2）：原著 / 技巧类 / 其他。历史 RESEARCH / NEEDS_REVIEW
# 不再是普通作者类型；如仍出现在旧 ledger，一律按「其他」展示（不隐藏、不伪造）。
_AUTHOR_TYPE_LABELS = {
    "REFERENCE_WORK": "原著",
    "METHOD_SOURCE": "技巧类",
    "LOOSE_MATERIAL": "其他",
}


def _author_type_label(asset_type: str) -> str:
    return _AUTHOR_TYPE_LABELS.get(asset_type, "其他")


def _list_prepare_dir_names(base: Path) -> list[str]:
    """一次列出 Prepare 工作区下的目录名（避免逐 asset 重复 glob 扫盘）。"""
    try:
        if base.is_dir():
            return [d.name for d in base.iterdir() if d.is_dir()]
    except OSError:
        pass
    return []


def _prepare_package_path(asset: dict[str, Any], *,
                          sp_names: list[str] | None = None,
                          mp_names: list[str] | None = None) -> Path | None:
    """Resolve the existing Prepare package by canonical asset id."""
    asset_id = str(asset.get("id") or "").strip()
    asset_type = str(asset.get("type") or "")
    if not asset_id or asset_type not in ("REFERENCE_WORK", "METHOD_SOURCE"):
        return None
    if asset_type == "METHOD_SOURCE":
        base = get_repo_root() / "06_工作区" / "MethodPrepare"
        names = mp_names if mp_names is not None else _list_prepare_dir_names(base)
    else:
        base = get_repo_root() / "06_工作区" / "SourcePrepare"
        names = sp_names if sp_names is not None else _list_prepare_dir_names(base)
    name = next((item for item in names if item.startswith(f"{asset_id}_")), None)
    return base / name if name else None


def _known_prepare_reason(text: str) -> str | None:
    """Map known Prepare diagnostics to concise author language; never echo raw text."""
    value = str(text or "")
    if not value:
        return None
    if "container.xml" in value or "OPF" in value or "关键结构" in value:
        return "EPUB 结构检查未通过：container.xml / OPF 无效。"
    if "章节边界" in value or "未生成 chapters" in value or "linear_no_heading" in value:
        return "未识别到足够的正文或章节。"
    if "正文字符数过少" in value or "too_few_visible_chars" in value or "可见内容过少" in value:
        return "正文可见字符过少。"
    if "PDF 无可用文本层" in value or "PDF 无有用文本层" in value:
        return "PDF 没有可读取的文字层。"
    if "Pandoc" in value or "conversion_unavailable" in value or "conversion_error" in value \
            or "转换失败" in value or "无法转换" in value:
        return "文件转换失败。"
    if "garbled" in value or "替换字符" in value or "编码损坏" in value:
        return "正文可能存在编码损坏。"
    if "no_supported_source" in value or "不支持" in value:
        return "没有可提纯的受支持来源文件。"
    return None


def _prepare_artifact_reasons(pkg: Path, meta: dict[str, Any]) -> list[str]:
    """Project at most three safe, concrete reasons from an existing Prepare artifact."""
    raw_reasons: list[str] = []
    for key in ("cross_source_warnings", "limitations", "warnings", "notes"):
        values = meta.get(key)
        if isinstance(values, list):
            raw_reasons.extend(str(item) for item in values)
    candidates = meta.get("candidates")
    if isinstance(candidates, list):
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            for key in ("warnings", "limitations"):
                values = candidate.get(key)
                if isinstance(values, list):
                    raw_reasons.extend(str(item) for item in values)
            checks = candidate.get("epub_checks")
            if isinstance(checks, list):
                failed = [str(check.get("title") or "") for check in checks
                          if isinstance(check, dict) and check.get("status") == "fail"]
                if failed:
                    raw_reasons.insert(0, "EPUB 关键结构检测未通过：" + "、".join(failed))

    reasons: list[str] = []
    for raw in raw_reasons:
        reason = _known_prepare_reason(raw)
        if reason and reason not in reasons:
            reasons.append(reason)
        if len(reasons) == 3:
            return reasons

    if reasons:
        return reasons

    # Historical artifacts may only retain the human-readable report.  Parse only
    # known phrases and never surface report text verbatim.
    try:
        report = (pkg / "conversion_report.md").read_text(encoding="utf-8")
    except OSError:
        report = ""
    in_reason_section = False
    for line in report.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            in_reason_section = any(label in stripped for label in ("需要注意", "限制与不确定性", "单文件备注"))
            continue
        is_failed_check = bool(re.search(r"\|\s*fail\s*\|", stripped, flags=re.IGNORECASE))
        if not is_failed_check and not (in_reason_section and (stripped.startswith("-") or "⚠" in stripped)):
            continue
        reason = _known_prepare_reason(re.sub(r"^[\s#>*\-]+", "", stripped))
        if reason and reason not in reasons:
            reasons.append(reason)
        if len(reasons) == 3:
            break
    return reasons


def _prepare_package_current(asset: dict[str, Any],
                             sp_names: list[str] | None = None,
                             mp_names: list[str] | None = None) -> dict[str, Any]:
    """§7 「已提纯」真值：确定性校验 06 是否存在与当前来源匹配的有效 Prepare Markdown 包。

    返回 {"available": bool, "format": "MD"|None, "reason": str|None}。
    - REFERENCE_WORK：06/SourcePrepare/<id>_*/ 需 full.md + chapters/ + metadata.json(status=PASS)
      且 metadata.selected_source.sha256 ∈ 当前 asset 文件 SHA（内容身份，与路径无关）；
    - METHOD_SOURCE：06/MethodPrepare/<id>_*/ 需 full.md + sections/ + metadata.json(status=PASS) 且指纹匹配。
    绝不从 BKP 存在推断「已提纯」；历史 purification=可用 但 06 MD 缺失 → 不算已提纯。
    """
    mtype = asset.get("type") or ""
    asset_id = str(asset.get("id") or "").strip()
    none = {"available": False, "format": None, "reason": None}
    if not asset_id or mtype not in ("REFERENCE_WORK", "METHOD_SOURCE"):
        return none
    if mtype == "METHOD_SOURCE":
        required_subdir = "sections"
    else:
        required_subdir = "chapters"
    pkg = _prepare_package_path(asset, sp_names=sp_names, mp_names=mp_names)
    if pkg is None:
        return none
    if not (pkg / "full.md").is_file() or not (pkg / required_subdir).is_dir() \
            or not (pkg / "metadata.json").is_file():
        return {"available": False, "format": None, "reason": "提纯结果文件不完整。"}
    try:
        meta = json.loads((pkg / "metadata.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"available": False, "format": None,
                "reason": "历史提纯记录未保存具体失败原因，请重新提纯以生成新的检查结果。"}
    if meta.get("status") != "PASS":
        reasons = _prepare_artifact_reasons(pkg, meta)
        return {"available": False, "format": None, "reason": " ".join(reasons) if reasons else
                "历史提纯记录未保存具体失败原因，请重新提纯以生成新的检查结果。"}
    sel = meta.get("selected_source") or {}
    sha = sel.get("sha256") if isinstance(sel, dict) else None
    file_shas = {f.get("sha256") for f in (asset.get("files") or []) if isinstance(f, dict)}
    if not sha or sha not in file_shas:
        return {"available": False, "format": None,
                "reason": "提纯结果与当前来源文件不一致，需要重新提纯。"}
    return {"available": True, "format": "MD", "reason": None}


def _knowledge_package_kind(asset: dict[str, Any]) -> str | None:
    """已定稿且可检索的知识包类型（§8）：BKP（参考作品）/ METHOD（方法）/ None。"""
    if (asset.get("knowledge") or {}).get("status") != "可用":
        return None
    if not _knowledge_is_discoverable(asset):
        return None
    return "METHOD" if asset.get("type") == "METHOD_SOURCE" else "BKP"


def _source_formats(asset: dict[str, Any]) -> list[str]:
    """只投影作者能理解的来源格式，绝不泄露路径或 hash。"""
    formats: list[str] = []
    for entry in asset.get("files") or []:
        path = entry.get("path") if isinstance(entry, dict) else entry
        suffix = Path(str(path or "")).suffix.lower().lstrip(".")
        if suffix:
            label = suffix.upper()
            if label not in formats:
                formats.append(label)
    return formats


def _material_learning_paths(asset_id: str, asset_type: str) -> list[Path]:
    root = get_repo_root() / "02_素材知识库"
    asset_dir = next((p for p in sorted(root.glob(f"{asset_id}_*")) if p.is_dir()), None)
    if asset_dir is None:
        return []
    if asset_type == "REFERENCE_WORK":
        return [asset_dir / "bkp" / "author_view.md", asset_dir / "model.md"]
    if asset_type == "METHOD_SOURCE":
        return [asset_dir / "method" / "method_profile.md"]
    return []


def _parse_learning_markdown(text: str) -> tuple[str | None, list[dict[str, str]]]:
    """解析现有作者投影 Markdown；这是展示层，不产生任何新知识。"""
    summary_lines: list[str] = []
    sections: list[dict[str, Any]] = []
    title: str | None = None
    body: list[str] = []

    def flush() -> None:
        nonlocal body
        content = "\n".join(body).strip()
        if title and content:
            sections.append({"title": title, "body": content})
        elif content:
            summary_lines.append(content)
        body = []

    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("# ") or (not line and not body):
            continue
        if line.startswith(">") and not title and not summary_lines:
            continue
        if line.startswith("## "):
            flush()
            title = line[3:].strip()
            continue
        body.append(raw)
    flush()
    summary = "\n".join(summary_lines).strip() or None
    return summary, sections


def _learning_projection(asset: dict[str, Any]) -> tuple[str | None, list[dict[str, str]]]:
    for path in _material_learning_paths(str(asset.get("id") or ""), str(asset.get("type") or "")):
        try:
            if path.is_file():
                return _parse_learning_markdown(path.read_text(encoding="utf-8"))
        except OSError:
            continue
    return None, []


def _knowledge_is_discoverable(asset: dict[str, Any]) -> bool:
    """使用唯一 KnowledgeRetrieve loader 验证来源真实可加载。"""
    root = get_repo_root()
    kr_dir = _REPO_ROOT / "05_Skills与自动化" / "01_Skills" / "KnowledgeRetrieve"
    if str(kr_dir) not in sys.path:
        sys.path.insert(0, str(kr_dir))
    try:
        import registry
        expected_kind = "method_source" if asset.get("type") == "METHOD_SOURCE" else "reference_bkp"
        return any(
            source.get("source_kind") == expected_kind and source.get("source_id") == asset.get("id")
            for source in registry.discover_sources(str(root))
        )
    except Exception:
        return False


def _source_files_missing(asset: dict[str, Any]) -> bool:
    """已登记来源是否在磁盘全部缺失（作者手动删除文件夹）；用于可读 attention，绝不静默删除登记。"""
    files = [f for f in (asset.get("files") or []) if isinstance(f, dict) and f.get("path")]
    if not files:
        return False
    mat_dir = get_repo_root() / "01_原始素材"
    return not any((mat_dir / f["path"]).is_file() for f in files)


def _classify_author_group(a: dict[str, Any], *, sp_names: list[str] | None = None,
                           mp_names: list[str] | None = None) -> dict[str, Any]:
    """把后端 catalog/type/status 机器事实 + 06 真实提纯产物映射为作者可读分类。

    workflow_stage（作者工作流阶段；与 needs_attention 相互独立）：
    - writing：knowledge 已定稿可用 + 通过验收 + KnowledgeRetrieve 真实可发现（§7 兼容：
      即使 06 Prepare 产物已删，已定稿可检索知识包仍可用于写作）；
    - purified：存在与当前来源匹配的真实 Prepare Markdown（§7：历史 purification=可用
      但 06 MD 缺失 → 不算已提纯）；
    - new：尚未提纯成功（含提纯失败/来源缺失需重新处理）；
    - other：其他（LOOSE_MATERIAL；历史 RESEARCH）只登记，不进入三生产区。
    needs_attention 只决定该阶段内是否显示错误提示与重试，绝不改变素材所属阶段。
    同时投影 §8 派生字段：prepared_available / prepared_format / knowledge_package_kind。
    """
    mtype = a.get("type")
    # 其他（LOOSE_MATERIAL；历史 RESEARCH 同样归其他）：不进提纯→蒸馏→写作生产链，
    # 只参与素材总览类型统计（canonical type 保持不变，不迁移历史类型）。
    if mtype in ("LOOSE_MATERIAL", "RESEARCH"):
        return {"author_group": "pending", "state": "pending_prepare", "workflow_stage": "other",
                "writing_callable": False, "attention_message": None,
                "prepared_available": False, "prepared_format": None, "knowledge_package_kind": None}

    know = (a.get("knowledge") or {}).get("status") or "未开始"
    pur = (a.get("purification") or {}).get("status") or "未处理"

    # 1) 写作阶段：knowledge 已定稿可用（优先于来源/提纯检查；BKP 已冻结可检索）。
    if know == "可用":
        view = _bkp_acceptance_view(a)
        if view not in ("review", "pending") and _knowledge_is_discoverable(a):
            kind = "METHOD" if mtype == "METHOD_SOURCE" else "BKP"
            return {"author_group": "usable", "state": "ready", "workflow_stage": "writing",
                    "writing_callable": True, "attention_message": None,
                    "prepared_available": False, "prepared_format": None, "knowledge_package_kind": kind}
        # 已蒸馏出知识但 BKP 未通过验收或 KnowledgeRetrieve 尚不可发现：失败发生在蒸馏之后，
        # 阶段停留在 purified（绝不回落到 new）。
        return {"author_group": "needs_attention", "state": "needs_attention", "workflow_stage": "purified",
                "writing_callable": False, "attention_message": "资料还需要检查，确认完成后才能用于写作。",
                "prepared_available": False, "prepared_format": None, "knowledge_package_kind": None}

    # 2) 来源缺失（作者手动删除文件夹）→ 可读 attention，绝不静默删除登记。
    if _source_files_missing(a):
        return {"author_group": "needs_attention", "state": "needs_attention", "workflow_stage": "new",
                "writing_callable": False, "attention_message": "来源文件缺失，请检查或恢复素材文件夹后刷新状态。",
                "prepared_available": False, "prepared_format": None, "knowledge_package_kind": None}

    # 3) 已提纯阶段：必须有真实当前 Prepare Markdown（§7）。
    prep = _prepare_package_current(a, sp_names=sp_names, mp_names=mp_names)
    if prep["available"]:
        return {"author_group": "pending", "state": "pending_distill", "workflow_stage": "purified",
                "writing_callable": False, "attention_message": None,
                "prepared_available": True, "prepared_format": prep["format"], "knowledge_package_kind": None}

    # 4) 提纯失败/需复核/不适用 → new + attention（作者在此重新提纯）。
    if pur in ("需复核", "失败", "不适用") or a.get("type") == "NEEDS_REVIEW":
        formats = _source_formats(a)
        unsupported = {"ZIP", "MOBI", "AZW3"}.intersection(formats)
        message = ("当前格式不能直接提纯，请先转换为 EPUB、TXT 或带文字层的 PDF。"
                   if unsupported else (prep["reason"] or "资料需要检查后才能继续整理。"))
        return {"author_group": "needs_attention", "state": "needs_attention", "workflow_stage": "new",
                "writing_callable": False, "attention_message": message,
                "prepared_available": False, "prepared_format": None, "knowledge_package_kind": None}

    # 5) 待提纯（含历史 purification=可用 但 06 MD 缺失 → 回落待提纯）。
    return {"author_group": "pending", "state": "pending_prepare", "workflow_stage": "new",
            "writing_callable": False, "attention_message": prep["reason"],
            "prepared_available": False, "prepared_format": None, "knowledge_package_kind": None}


def list_materials() -> dict[str, Any]:
    """只读读取 canonical ledger，返回作者可读投影。

    绝不调用模型 / Agent / SourcePrepare / BookDistill；只读，无任何写副作用。
    只暴露真实字段：id / name / type / author / tags / notes / purification /
    knowledge /（files 数量）+ 作者面分类（author_group / writing_callable /
    why / next_step）。不返回 SHA 明细等机器事实（UI 用不到）。
    """
    catalog, _, _ = _load_materialintake()
    ledger = _load_ledger(catalog)
    root = get_repo_root()
    sp_names = _list_prepare_dir_names(root / "06_工作区" / "SourcePrepare")
    mp_names = _list_prepare_dir_names(root / "06_工作区" / "MethodPrepare")
    materials = []
    for a in ledger.get("assets", []):
        classified = _classify_author_group(a, sp_names=sp_names, mp_names=mp_names)
        materials.append({
            "id": a.get("id"),
            "name": a.get("name") or "",
            "type": a.get("type") or "",
            "author": a.get("author") or "",
            "type_label": _author_type_label(str(a.get("type") or "")),
            "source_formats": _source_formats(a),
            **classified,
        })
    return {"materials": materials}


def _workbench_projection_is_writing_ready(asset_id: str) -> bool:
    """Re-read the author-facing projection after settlement; no cached completion claims."""
    try:
        material = next(
            item for item in list_materials()["materials"]
            if item.get("id") == asset_id
        )
    except (KeyError, StopIteration, TypeError):
        return False
    return (
        material.get("workflow_stage") == "writing"
        and material.get("writing_callable") is True
    )


# ---------------------------------------------------------------------------
# 显式动作（只有作者明确点击才执行）
# ---------------------------------------------------------------------------

def refresh_materials() -> dict[str, Any]:
    """显式「刷新状态」：先把作者手动 Explorer 编辑（移动/改名/新建素材文件夹）
    确定性并入 canonical ledger（reconcile：事务性、内容身份、无模型），再刷新派生状态与三视图。

    §6：Workbench 路径不依赖 Git（不 precheck / commit / push）；§5：来源缺失保留登记并
    投影为可读 attention，不静默删除；歧义/重复身份 fail closed（不写盘）。
    """
    request_id = audit.new_request_id()
    audit.AuditRecorder(request_id, "material_refresh")
    audit.append_event(request_id, audit.EVENT_SKILL_STARTED, "material_intake", details={"skill": "MaterialIntake"})
    catalog, intake, _ = _load_materialintake()
    root = get_repo_root()

    # manual reconcile + derived-view refresh is one shared canonical mutation.
    with material_settlement.serialized():
        rec = intake.reconcile_manual_edits(root)
        if not rec.get("ok"):
            errors = rec.get("errors") or ["素材状态刷新失败"]
            message = errors[0] if len(errors) == 1 else "；".join(errors)
            audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "material_intake",
                               details={"skill": "MaterialIntake", "errors": errors})
            audit.finish_file(request_id, audit.STATUS_FAILED, error=message)
            raise MaterialsError(message)

        if not rec.get("changed"):
            rc = catalog.refresh_and_render(root, check_only=False, tolerate_missing=True)
            if rc != 0:
                audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "material_intake", details={"skill": "MaterialIntake"})
                audit.finish_file(request_id, audit.STATUS_FAILED, error="素材状态刷新失败")
                raise MaterialsError("素材状态刷新失败，请检查素材目录是否完整。")

    audit.append_event(request_id, audit.EVENT_SKILL_COMPLETED, "material_intake",
                       details={"skill": "MaterialIntake", "registered": len(rec.get("registered") or []),
                                "moved": len(rec.get("moved") or []), "renamed": len(rec.get("renamed") or [])})
    audit.finish_file(request_id, audit.STATUS_COMPLETED)
    ledger = _load_ledger(catalog)
    removed = rec.get("removed_assets") or []
    source_deleted = rec.get("source_deleted") or []
    registered = rec.get("registered") or []
    message = "素材状态已刷新"
    if registered:
        message = f"素材状态已刷新，新登记 {len(registered)} 份素材"
    if removed:
        message += f"；{len(removed)} 份素材来源已全部删除，已从素材库移除"
    elif source_deleted:
        message += f"；{len(source_deleted)} 份素材已同步手动删除的来源文件"
    return {
        "assets": len(ledger.get("assets", [])),
        "files": sum(len(a.get("files", [])) for a in ledger.get("assets", [])),
        "containers": len(ledger.get("containers", [])),
        "registered": registered,
        "moved": rec.get("moved") or [],
        "renamed": rec.get("renamed") or [],
        "removed_assets": removed,
        "source_deleted": source_deleted,
        "missing_sources": rec.get("missing_sources") or [],
        "message": message,
    }


def _inbox_file_view(f: dict[str, Any]) -> dict[str, Any]:
    """给收件箱文件补上作者可读的 display_name / format（确定性，零模型，不读全文）。

    display_name 优先用文件名 stem：尚未入库的原始文件没有更可靠的书名来源，
    绝不为了显示书名而读取全文或调用 AI（符合 CP1.3 优先级：已有 helper → stem）。
    format 只投影 EPUB/PDF/TXT 等作者能理解的来源格式，不泄露 SHA/路径。
    """
    view = dict(f)
    filename = str(f.get("filename") or "")
    stem = Path(filename).stem if filename else ""
    view["display_name"] = stem or filename
    view["format"] = Path(filename).suffix.lstrip(".").upper() if filename else ""
    return view


def scan_material_inbox() -> dict[str, Any]:
    """只读扫描 00_待入库（MaterialIntake inbox scan）。

    返回实际扫描到的文件与 deterministic 事实（sha256 / exact_duplicate_matches /
    possible_existing_candidates / unsupported）。绝不移动 / 登记任何文件。
    """
    request_id = audit.new_request_id()
    audit.AuditRecorder(request_id, "material_scan")
    audit.append_event(request_id, audit.EVENT_SKILL_STARTED, "material_intake", details={"skill": "MaterialIntake"})
    catalog, intake, _ = _load_materialintake()
    mat_dir = get_repo_root() / "01_原始素材"
    ledger = None
    ledger_path = mat_dir / "素材资产.json"
    if ledger_path.exists():
        try:
            ledger = catalog.load_ledger(ledger_path)
        except (FileNotFoundError, RuntimeError) as exc:
            audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "material_intake", details={"skill": "MaterialIntake"})
            audit.finish_file(request_id, audit.STATUS_FAILED, error=str(exc))
            raise MaterialsError(str(exc)) from exc
    files = [_inbox_file_view(f) for f in intake.scan_inbox(mat_dir, ledger)]
    audit.append_event(request_id, audit.EVENT_SKILL_COMPLETED, "material_intake", details={"skill": "MaterialIntake", "files": len(files)})
    audit.finish_file(request_id, audit.STATUS_COMPLETED)
    return {"inbox": "00_待入库", "files": files}


def _intake_error_message(errors: list[str]) -> str:
    """把 MaterialIntake 内部错误映射为作者可读中文（§13：技术细节只留审计/日志）。

    文件系统失败（已回滚）绝不向作者暴露 WinError / 绝对路径 / Python 异常文本 / traceback；
    只给出一句可执行中文提示，技术详情保留在审计与 report["errors"]。
    """
    joined = " ".join(errors)
    if "INTAKE_FILESYSTEM_FAILURE" in joined or "RECOVERY_REQUIRED" in joined:
        return "素材入库失败，文件已恢复到待入库，请重试。"
    if "STOP_BEFORE_MOVE" in joined or "MISSING_REGISTERED_FILE" in joined:
        return "素材目录与登记不一致，请先点「刷新状态」同步手动改动后重试。"
    if "EXACT_DUPLICATE" in joined:
        return "重复文件的处理条件不满足，已保留现场，请检查待入库文件后重试。"
    if "type 非法" in joined or "NEW_ASSET" in joined:
        return "入库信息不完整，请选择批次类型后重试。"
    if "不存在" in joined:
        return "待入库文件已变化，请重新扫描后重试。"
    return "素材入库失败，请重试。"


def apply_material_intake(plan: dict[str, Any]) -> dict[str, Any]:
    """作者显式「入库」：走 MaterialIntake 确定性 intake 事务。

    §6：Workbench 入库不做 Git precheck / fetch / commit / push，不因 DIRTY_WORKTREE /
    分支 / 远端状态失败；保留确定性文件校验、snapshot/rollback、request 身份、审计。
    （CLI 维护命令仍可显式支持 Git sync；Workbench 显式走本地/无 Git 模式。）
    intake 绝不自动调用 Prepare（§4）。
    """
    request_id = audit.new_request_id()
    audit.AuditRecorder(request_id, "material_intake")
    catalog, intake, _ = _load_materialintake()
    root = get_repo_root()
    mat_dir = root / "01_原始素材"
    ledger_path = mat_dir / "素材资产.json"
    # ledger read + intake apply/rollback is one shared canonical transaction.
    with material_settlement.serialized():
        try:
            ledger = catalog.load_ledger(ledger_path)
        except (FileNotFoundError, RuntimeError) as exc:
            audit.finish_file(request_id, audit.STATUS_FAILED, error=str(exc))
            raise MaterialsError("素材目录不可用，请检查素材文件夹后重试。") from exc
        audit.append_event(request_id, audit.EVENT_SKILL_STARTED, "material_intake", details={"skill": "MaterialIntake"})
        report = intake.apply_plan(plan, ledger, root)
    if not report.get("ok"):
        errors = report.get("errors") or ["素材入库失败"]
        audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "material_intake",
                           details={"skill": "MaterialIntake", "errors": errors})
        audit.finish_file(request_id, audit.STATUS_FAILED, error="; ".join(errors))
        raise MaterialsError(_intake_error_message(errors))
    audit.append_event(
        request_id, audit.EVENT_SKILL_COMPLETED, "material_intake",
        details={"skill": "MaterialIntake", "new_ids": report.get("new_ids") or [], "attached": report.get("attached") or []},
    )
    audit.finish_file(request_id, audit.STATUS_COMPLETED)
    return {
        "ok": True,
        "new_ids": report.get("new_ids") or [],
        "attached": report.get("attached") or [],
        "duplicates_removed": report.get("duplicates_removed") or [],
        "reviews": report.get("reviews") or [],
        "moves": report.get("moves") or [],
        "message": "素材入库已完成",
    }


def validate_intake_plan(plan: dict[str, Any]) -> list[str]:
    """对作者构造的 intake plan 做纯校验（不执行任何移动），返回错误列表。

    供 UI 在提交前做最小校验提示；真正的完整校验与执行由 apply_material_intake
    （MaterialIntake.apply_plan）统一完成。
    """
    if not isinstance(plan, dict) or not isinstance(plan.get("items"), list):
        return ["入库计划格式错误。"]
    errors: list[str] = []
    for i, item in enumerate(plan["items"]):
        action = item.get("action") if isinstance(item, dict) else None
        if action not in ("NEW_ASSET", "ATTACH_EXISTING", "REVIEW"):
            errors.append(f"第 {i + 1} 项动作无效。")
        files = (item or {}).get("files") if isinstance(item, dict) else None
        if not isinstance(files, list) or not files:
            errors.append(f"第 {i + 1} 项缺少文件。")
        if action == "NEW_ASSET" and not ((item or {}).get("name") or "").strip():
            errors.append(f"第 {i + 1} 项缺少名称。")
        if action == "NEW_ASSET" and (item or {}).get("type") not in (
            "REFERENCE_WORK", "LOOSE_MATERIAL", "METHOD_SOURCE",
        ):
            errors.append(f"第 {i + 1} 项类型无效。")
        if action == "ATTACH_EXISTING" and not (item or {}).get("asset_id"):
            errors.append(f"第 {i + 1} 项缺少目标素材。")
    return errors


# ---------------------------------------------------------------------------
# 4.1 本地文件导入（drop/选择 → 先进入 MaterialIntake 收件箱，绝无旁路）
# ---------------------------------------------------------------------------

def _inbox_dir() -> Path:
    return get_repo_root() / "01_原始素材" / "00_待入库"


def pick_material_files() -> dict[str, Any]:
    """调用 pywebview 原生文件对话框（Python 侧控制路径来源）。

    返回作者选择的本地文件路径（仅供后续 import 使用；不复制、不移动）。
    无 pywebview 环境（测试/纯浏览器）时返回 not_supported。
    """
    try:
        import webview  # noqa: F401 — 延迟导入：测试环境无桌面壳
    except Exception:  # noqa: BLE001
        return {"supported": False, "paths": [], "message": "当前环境不支持文件选择对话框。"}
    try:
        window = webview.windows[0] if webview.windows else None
        if window is None:
            return {"supported": False, "paths": [], "message": "未找到桌面窗口。"}
        result = window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=True,
            file_types=("素材文件 (*.epub;*.pdf;*.txt)", "所有文件 (*.*)"),
        )
        paths = [str(p) for p in (result or []) if p]
        return {"supported": True, "paths": paths, "message": ""}
    except Exception as exc:  # noqa: BLE001
        return {"supported": False, "paths": [], "message": f"文件选择失败：{exc}"}


def import_material_files(files: list[dict[str, Any]]) -> dict[str, Any]:
    """把本地文件字节 stage 到 MaterialIntake 收件箱（00_待入库）。

    所有导入文件一律先进 inbox 合同（MaterialIntake scan/apply 的唯一来源）；
    绝不直接写入最终 canonical 目录。只接受受支持后缀；超上限文件拒绝。
    """
    request_id = audit.new_request_id()
    audit.AuditRecorder(request_id, "material_intake")
    if not isinstance(files, list) or not files:
        raise MaterialsError("没有选择要导入的文件。")
    inbox = _inbox_dir()
    inbox.mkdir(parents=True, exist_ok=True)
    imported: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for entry in files:
        raw_path = (entry or {}).get("path") if isinstance(entry, dict) else None
        if not isinstance(raw_path, str) or not raw_path.strip():
            skipped.append({"path": "", "reason": "缺少路径"})
            continue
        src = Path(raw_path)
        if not src.is_file():
            skipped.append({"path": str(src), "reason": "文件不存在"})
            continue
        suffix = src.suffix.lower()
        if suffix not in _SUPPORTED_IMPORT_SUFFIXES:
            skipped.append({"path": str(src), "reason": f"不支持的类型（{suffix or '无后缀'}）"})
            continue
        try:
            size = src.stat().st_size
        except OSError as exc:
            skipped.append({"path": str(src), "reason": f"读取失败：{exc}"})
            continue
        if size > _MAX_IMPORT_BYTES:
            skipped.append({"path": str(src), "reason": "超过 200 MB 上限"})
            continue
        # 安全目标名：保留原文件名；重名时加序号（绝不覆盖收件箱已有文件）
        dest = _unique_inbox_name(inbox, src.name)
        try:
            shutil.copy2(src, dest)
        except OSError as exc:
            skipped.append({"path": str(src), "reason": f"复制失败：{exc}"})
            continue
        imported.append({"path": f"00_待入库/{dest.name}", "filename": dest.name, "size": size})
    audit.append_event(
        request_id, audit.EVENT_SKILL_STARTED, "material_intake",
        details={"skill": "MaterialIntake", "imported": len(imported), "skipped": len(skipped)},
    )
    audit.append_event(
        request_id, audit.EVENT_SKILL_COMPLETED, "material_intake",
        details={"skill": "MaterialIntake", "imported": len(imported)},
    )
    audit.finish_file(request_id, audit.STATUS_COMPLETED)
    return {
        "inbox": "00_待入库",
        "imported": imported,
        "skipped": skipped,
        "message": f"已放入待入库 {len(imported)} 个文件" + (f"，跳过 {len(skipped)} 个" if skipped else ""),
    }


def _unique_inbox_name(inbox: Path, name: str) -> Path:
    dest = inbox / name
    if not dest.exists():
        return dest
    stem, suffix = Path(name).stem, Path(name).suffix
    for i in range(1, 100):
        candidate = inbox / f"{stem}-{i}{suffix}"
        if not candidate.exists():
            return candidate
    raise MaterialsError(f"收件箱同名文件过多，无法导入：{name}")


# ---------------------------------------------------------------------------
# 4.2 批次机械入库计划（零 AI；作者选批次类型，代码组装 intake plan）
# ---------------------------------------------------------------------------

def build_intake_plan_from_inbox(batch_type: str) -> dict[str, Any]:
    """作者选批次类型后，机械构建入库计划（零 AI，零模型）。

    exact_duplicate → ATTACH_EXISTING（确定性）；
    unsupported → REVIEW（确定性）；
    其余文件 → NEW_ASSET（按作者选择的批次类型）。
    返回可直接传给 apply_material_intake 的 plan。
    """
    type_map = {
        "REFERENCE_WORK": "REFERENCE_WORK",
        "METHOD_SOURCE": "METHOD_SOURCE",
        "LOOSE_MATERIAL": "LOOSE_MATERIAL",
    }
    if batch_type not in type_map:
        raise MaterialsError("批次类型无效，请选择原著、技巧类或其他。")

    request_id = audit.new_request_id()
    audit.AuditRecorder(request_id, "material_intake_plan")
    catalog, intake, _ = _load_materialintake()
    mat_dir = get_repo_root() / "01_原始素材"
    ledger_path = mat_dir / "素材资产.json"
    ledger = None
    if ledger_path.exists():
        try:
            ledger = catalog.load_ledger(ledger_path)
        except (FileNotFoundError, RuntimeError):
            ledger = None
    files = intake.scan_inbox(mat_dir, ledger)
    audit.append_event(request_id, audit.EVENT_SKILL_COMPLETED, "material_intake",
                       details={"skill": "MaterialIntake", "files": len(files)})
    audit.finish_file(request_id, audit.STATUS_COMPLETED)

    plan_items: list[dict[str, Any]] = []
    for f in files:
        if f["unsupported"]:
            plan_items.append({
                "action": "REVIEW",
                "files": [f["filename"]],
                "reason": "不支持的类型，需人工确认",
            })
        elif f["exact_duplicate_matches"]:
            match = f["exact_duplicate_matches"][0]
            asset_id = match.split("(")[0] if "(" in match else match
            plan_items.append({
                "action": "ATTACH_EXISTING",
                "files": [f["filename"]],
                "asset_id": asset_id,
            })
        else:
            # §2.3：新书入库边界统一用同一归一化 helper——同一归一化标题驱动
            # asset.name / 角色文件夹名 / 来源文件名 stem（去括号，避免 Windows 路径失败）。
            stem = intake.normalize_book_title(Path(f["filename"]).stem)
            plan_items.append({
                "action": "NEW_ASSET",
                "files": [f["filename"]],
                "name": stem,
                "type": type_map[batch_type],
            })

    return {
        "status": "ready",
        "plan": {"items": plan_items},
        "message": "入库计划已生成" if plan_items else "没有需要入库的文件",
    }


# ---------------------------------------------------------------------------
# 4.4 SourcePrepare 显式提纯（真实 SP CLI；确定性，无模型）
# ---------------------------------------------------------------------------

def _ledger_asset(asset_id: str) -> dict[str, Any]:
    catalog, _, _ = _load_materialintake()
    ledger = _load_ledger(catalog)
    asset = next((a for a in ledger.get("assets", []) if a.get("id") == asset_id), None)
    if asset is None:
        raise MaterialsError(f"素材不存在：{asset_id}")
    return asset


def _prepare_error_message(detail: str) -> str:
    """把提纯子进程的内部输出映射为作者可读中文（§12；技术细节只留审计）。"""
    low = (detail or "").lower()
    if "ocr" in low or "no text layer" in low or "文字层" in (detail or "") or "image-only" in low:
        return "PDF 没有可读取的文字层，当前不支持 OCR。"
    if "corrupt" in low or "bad zip" in low or "not a zip" in low or "损坏" in (detail or ""):
        return "文件无法读取，请检查文件是否损坏。"
    if "pandoc" in low or "convert" in low or "转换" in (detail or ""):
        return "EPUB 无法转换为 Markdown，请更换来源文件后重试。"
    if "timeout" in low or "超时" in (detail or ""):
        return "提纯超时，请重试或检查素材。"
    return "提纯失败，请重试或更换来源文件。"


def _distill_error_message(detail: str) -> str:
    """把蒸馏子进程的内部输出映射为作者可读中文（§12）。"""
    low = (detail or "").lower()
    if "markdown" in low or "full.md" in low or "chapters" in low or "sections" in low:
        return "学习输入不是当前有效的 Markdown，请先重新提纯。"
    if "timeout" in low or "超时" in (detail or ""):
        return "学习超时，请重试。"
    return "学习失败，请重试。"


class _PublishTransaction:
    """Request-scoped 06 -> 02 publish held open through discovery/catalog settlement."""

    def __init__(self, src: Path, dest: Path, request_id: str) -> None:
        self.src = src
        self.dest = dest
        token = f"{request_id}.{uuid.uuid4().hex}"
        self.backup = dest.with_name(f"{dest.name}.__publish_backup__.{token}")
        self._had_previous = False
        self._previous_moved = False
        self._candidate_published = False
        self._begun = False
        self._committed = False
        self._metadata: dict[Path, bytes | None] = {}

    def begin(self) -> None:
        if self._begun:
            raise RuntimeError("publish transaction already begun")
        catalog, _, _ = _load_materialintake()
        mat_dir = get_repo_root() / "01_原始素材"
        for name in (catalog.LEDGER_FILENAME, catalog.LEGACY_CSV_FILENAME, catalog.INDEX_FILENAME):
            path = mat_dir / name
            self._metadata[path] = path.read_bytes() if path.exists() else None
        self.dest.parent.mkdir(parents=True, exist_ok=True)
        self._had_previous = self.dest.exists()
        self._begun = True
        try:
            if self._had_previous:
                shutil.move(str(self.dest), str(self.backup))
                self._previous_moved = True
            shutil.move(str(self.src), str(self.dest))
            self._candidate_published = True
        except OSError:
            self.rollback()
            raise

    def commit(self) -> None:
        if not self._begun or self._committed:
            raise RuntimeError("publish transaction is not open")
        if self.backup.exists():
            shutil.rmtree(self.backup)
        self._committed = True

    def rollback(self) -> None:
        if not self._begun or self._committed:
            return
        failures: list[str] = []
        try:
            if self._candidate_published and self.dest.exists():
                self.src.parent.mkdir(parents=True, exist_ok=True)
                failed_target = self.src
                if failed_target.exists():
                    failed_target = self.src.with_name(
                        f"{self.src.name}.__failed_publish__.{uuid.uuid4().hex}")
                shutil.move(str(self.dest), str(failed_target))
        except OSError as exc:
            failures.append(f"candidate: {type(exc).__name__}: {exc}")
        try:
            if self._previous_moved and self.backup.exists():
                if self.dest.exists():
                    raise OSError("formal destination remains occupied")
                shutil.move(str(self.backup), str(self.dest))
        except OSError as exc:
            failures.append(f"previous: {type(exc).__name__}: {exc}")
        for path, data in self._metadata.items():
            try:
                if data is None:
                    path.unlink(missing_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
            except OSError as exc:
                failures.append(f"metadata:{path.name}: {type(exc).__name__}: {exc}")
        if failures:
            raise RuntimeError("; ".join(failures))


def _rollback_publish_or_fail(tx: _PublishTransaction, request_id: str, component: str) -> None:
    try:
        tx.rollback()
    except Exception as exc:  # noqa: BLE001 - rollback diagnostics stay in audit
        audit.append_event(request_id, audit.EVENT_SKILL_FAILED, component,
                           details={"step": "publish_rollback", "error": str(exc)[:400]})
        raise MaterialsError("学习结果暂不能用于写作，自动恢复未完成，请查看运行记录。") from exc


def run_source_prepare(asset_id: str) -> dict[str, Any]:
    """对指定素材显式运行真实 SourcePrepare（SP CLI，确定性、无模型）。

    前置：asset 存在且 type 为 SP 可处理（REFERENCE_WORK / RESEARCH）；
    输出落 06_工作区/SourcePrepare/<book_id>_<name>/；ledger 的 purification
    由 SP 自身的 catalog refresh 派生（PASS→可用 / REVIEW→需复核 / FAIL→失败）。
    """
    asset_id = (asset_id or "").strip()
    if not asset_id:
        raise MaterialsError("缺少素材标识（asset_id）。")
    asset = _ledger_asset(asset_id)
    mtype = asset.get("type") or ""
    if mtype == "LOOSE_MATERIAL":
        raise MaterialsError("其他类素材不适用提纯。")
    if mtype == "NEEDS_REVIEW":
        raise MaterialsError("该素材待人工确认，暂不能提纯。")
    if mtype == "METHOD_SOURCE":
        raise MaterialsError("技巧类资料请走通用入口（后端会自动改用 MethodPrepare）。")

    request_id = audit.new_request_id()
    audit.AuditRecorder(request_id, "source_prepare", project_id=None)
    audit.append_event(request_id, audit.EVENT_SKILL_STARTED, "source_prepare", details={"skill": "SourcePrepare", "asset_id": asset_id})

    script = _REPO_ROOT / "05_Skills与自动化" / "01_Skills" / "SourcePrepare" / "scripts" / "source_prepare.py"
    if not script.is_file():
        audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "source_prepare", details={"skill": "SourcePrepare"})
        audit.finish_file(request_id, audit.STATUS_FAILED, error="SourcePrepare 运行脚本缺失")
        raise MaterialsError("SourcePrepare 运行脚本缺失。")
    cmd = [
        sys.executable, str(script),
        "--root", str(get_repo_root()),
        "--book", asset_id,
        "--no-git-sync",
        "--no-catalog-writeback",
    ]
    audit.append_event(
        request_id, audit.EVENT_AGENT_DIRECT_PROCESS_STARTED, "source_prepare",
        details={"asset_id": asset_id,
                 "command": "source_prepare.py --book " + asset_id + " --no-git-sync --no-catalog-writeback"},
    )
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=10 * 60,
        )
    except subprocess.TimeoutExpired as exc:
        audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "source_prepare", details={"skill": "SourcePrepare"})
        audit.finish_file(request_id, audit.STATUS_FAILED, error="提纯超时（10 分钟）")
        raise MaterialsError("提纯超时（10 分钟），请重试或检查素材。") from exc
    except OSError as exc:
        audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "source_prepare", details={"skill": "SourcePrepare"})
        audit.finish_file(request_id, audit.STATUS_FAILED, error=str(exc))
        raise MaterialsError(f"提纯启动失败：{exc}") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "")[:800]
        audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "source_prepare",
                           details={"skill": "SourcePrepare", "returncode": proc.returncode, "detail": detail})
        audit.finish_file(request_id, audit.STATUS_FAILED, error=detail)
        raise MaterialsError(_prepare_error_message(detail))
    # The long conversion stayed outside the lock; only shared catalog writeback is serialized.
    _refresh_catalog_or_fail(request_id, "source_prepare")
    audit.append_event(request_id, audit.EVENT_SKILL_COMPLETED, "source_prepare", details={"skill": "SourcePrepare", "asset_id": asset_id})
    audit.finish_file(request_id, audit.STATUS_COMPLETED)
    return {
        "asset_id": asset_id,
        "status": "completed",
        "message": "提纯完成（SourcePrepare 已运行并刷新素材状态）",
        "output_tail": "\n".join((proc.stdout or "").splitlines()[-6:]),
    }


# ---------------------------------------------------------------------------
# 4.5 BookDistill 显式蒸馏（真实 BD CLI 阶段 + 持久化 Agent 路由的一次阅读 turn）
# ---------------------------------------------------------------------------

_BD_SCRIPT = _REPO_ROOT / "05_Skills与自动化" / "01_Skills" / "BookDistill" / "scripts" / "book_distill.py"
_ACCEPTANCE_GATE_SCRIPT = _REPO_ROOT / "05_Skills与自动化" / "01_Skills" / "BookDistill" / "scripts" / "acceptance_gate.py"
_BOOK_DISTILL_AGENT_TASK_BUILDER = (
    Path(__file__).resolve().parents[3]
    / "05_Skills与自动化" / "01_Skills" / "BookDistill" / "agent_task.py"
)

def _find_sp_dir(asset_id: str, name: str) -> Path:
    root = get_repo_root() / "06_工作区" / "SourcePrepare"
    if not root.exists():
        raise MaterialsError("还没有任何提纯产物，请先对素材执行「提纯」。")
    candidates = list(root.glob(f"{asset_id}_*"))
    if not candidates:
        raise MaterialsError(f"素材 {asset_id} 还没有提纯产物（06_工作区/SourcePrepare），请先提纯。")
    return candidates[0]


def _run_bd_cli(args: list[str], request_id: str, *, timeout: int = 10 * 60) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(_BD_SCRIPT)] + args
    audit.append_event(
        request_id, audit.EVENT_AGENT_DIRECT_PROCESS_STARTED, "book_distill",
        details={"command": "book_distill.py " + " ".join(args[:3])},
    )
    return subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
    )


def _mark_reference_acceptance_pending(bd_dir: Path) -> None:
    """新工作台包在刷新 catalog 前先 fail closed，旧 BKP 一律不追溯修改。"""
    identity_path = bd_dir / "bkp" / "identity.json"
    try:
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MaterialsError("原著学习结果不完整，请重试。") from exc
    identity["acceptance"] = {
        "schema": "gowrite_bkp_acceptance/v1", "required": True, "status": "PENDING",
        "report": "BKP_ACCEPTANCE_REPORT.md",
    }
    identity["bkp_protocol_version"] = "0.3"
    identity_path.write_text(json.dumps(identity, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _run_reference_acceptance(request_id: str, stage_dir: Path) -> None:
    """确定性全书验收门（against 06 staging；写 bkp/identity.json acceptance）。

    discovery 检查在受控发布到 02 之后进行（staging 不在 02，尚不可检索）。
    验收与统一 loader discovery 是原著蒸馏的完成门，不是作者动作。
    """
    _mark_reference_acceptance_pending(stage_dir)
    if not _ACCEPTANCE_GATE_SCRIPT.is_file():
        raise MaterialsError("原著学习检查工具缺失。")
    try:
        proc = subprocess.run(
            [sys.executable, str(_ACCEPTANCE_GATE_SCRIPT), str(stage_dir), "--repo-root", str(get_repo_root()), "--write-identity"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10 * 60,
        )
    except subprocess.TimeoutExpired as exc:
        raise MaterialsError("原著学习检查超时，请重试。") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "")[:800]
        audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "book_distill",
                           details={"skill": "BookDistill", "stage": "acceptance", "detail": detail})
        raise MaterialsError("原著学习结果未通过检查，请重新原著学习。")


def _finalize_reference_distill(request_id: str, asset: dict[str, Any], sp_dir: Path, stage_dir: Path) -> dict[str, Any]:
    """确定性完成门（against 06 staging）→ 受控发布到 02 → discovery → 刷新素材状态。

    重新执行所有确定性边界；Agent 输出从不直接构成完成信任。未全部通过则绝不发布到 02。
    """
    for sub_args, label in (
        (["assemble", "--input", str(sp_dir), "--output", str(stage_dir)], "原著学习检查"),
        (["profile", "--output", str(stage_dir)], "资料整理"),
        (["bkp", "--output", str(stage_dir)], "学习资料整理"),
    ):
        try:
            proc = _run_bd_cli(sub_args, request_id)
        except subprocess.TimeoutExpired as exc:
            raise MaterialsError(f"{label}超时，请重试。") from exc
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "")[:800]
            audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "book_distill",
                               details={"skill": "BookDistill", "stage": label, "detail": detail})
            raise MaterialsError(f"{label}失败，请重试。")
    _run_reference_acceptance(request_id, stage_dir)
    # 发布事务保持开放，直到 discovery + catalog settlement 都成功。
    target_dir = get_repo_root() / "02_素材知识库" / sp_dir.name
    tx = _PublishTransaction(stage_dir, target_dir, request_id)
    with material_settlement.serialized():
        try:
            tx.begin()
            if not _knowledge_is_discoverable(asset):
                raise MaterialsError("knowledge discovery failed")
            catalog, _, _ = _load_materialintake()
            rc = catalog.refresh_and_render(get_repo_root(), check_only=False)
            if rc != 0:
                raise MaterialsError(f"catalog settlement rc={rc}")
            if not _workbench_projection_is_writing_ready(str(asset.get("id") or "")):
                raise MaterialsError("workbench projection is not writing-ready")
            tx.commit()
        except Exception as exc:  # noqa: BLE001 - technical detail stays in audit
            audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "book_distill",
                               details={"step": "post_publish_verification", "error": str(exc)[:300]})
            _rollback_publish_or_fail(tx, request_id, "book_distill")
            raise MaterialsError("原著学习结果暂不能用于写作，已保留原知识包，请重试。") from exc
    return {"output_dir": str(target_dir)}


def run_book_distill(asset_id: str) -> dict[str, Any]:
    """对已提纯（真实当前 Prepare MD）的原著素材显式运行真实 BookDistill。

    阶段：§9 前置校验当前 Prepare MD → validate（确定性）→ prepare 到 06 request-scoped
    staging（确定性）→ Agent 阅读/收敛 turn（只写 staging）→ assemble + profile + bkp +
    acceptance（确定性 finalize，against staging）→ 受控发布到 02 → KnowledgeRetrieve
    discovery → 素材状态刷新。未完成/失败/取消的输出绝不进入正式 02。
    """
    asset_id = (asset_id or "").strip()
    if not asset_id:
        raise MaterialsError("缺少素材标识（asset_id）。")
    asset = _ledger_asset(asset_id)
    if asset.get("type") == "LOOSE_MATERIAL":
        raise MaterialsError("其他类素材不适用原著学习。")
    if asset.get("type") == "METHOD_SOURCE":
        raise MaterialsError("技巧类资料请走通用入口（后端会自动改用 MethodDistill）。")

    request_id = audit.new_request_id()
    audit.AuditRecorder(request_id, "book_distill")
    audit.append_event(request_id, audit.EVENT_SKILL_STARTED, "book_distill", details={"skill": "BookDistill", "asset_id": asset_id})

    # 0) §9 前置：必须有真实当前 Prepare Markdown（绝不直接读 EPUB/PDF/TXT）
    prep = _prepare_package_current(asset)
    if not prep["available"]:
        audit.finish_file(request_id, audit.STATUS_FAILED, error="prepare-not-current")
        raise MaterialsError(prep["reason"] or "原著学习输入不是当前有效的 Markdown，请先重新提纯。")

    # 1) 定位 SP PASS 包 + validate
    sp_dir = _find_sp_dir(asset_id, asset.get("name") or "")
    try:
        proc = _run_bd_cli(["validate", "--input", str(sp_dir)], request_id)
    except subprocess.TimeoutExpired:
        audit.finish_file(request_id, audit.STATUS_FAILED, error="蒸馏校验超时")
        raise MaterialsError("原著学习检查超时，请重试。")
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "")[:800]
        audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "book_distill", details={"skill": "BookDistill", "detail": detail})
        audit.finish_file(request_id, audit.STATUS_FAILED, error=detail)
        raise MaterialsError(_distill_error_message(detail))

    # 2) prepare（确定性脚手架）→ 06 request-scoped staging（绝不写正式 02）
    stage_dir = get_repo_root() / "06_工作区" / "BookDistill" / f"{request_id}_{sp_dir.name}"
    stage_dir.mkdir(parents=True, exist_ok=True)
    try:
        proc = _run_bd_cli(["prepare", "--input", str(sp_dir), "--output", str(stage_dir)], request_id)
    except subprocess.TimeoutExpired:
        audit.finish_file(request_id, audit.STATUS_FAILED, error="蒸馏准备超时")
        raise MaterialsError("原著学习准备超时，请重试。")
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "")[:800]
        audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "book_distill", details={"skill": "BookDistill", "detail": detail})
        audit.finish_file(request_id, audit.STATUS_FAILED, error=detail)
        raise MaterialsError(_distill_error_message(detail))

    # 3) Agent 阅读/收敛 turn（只写 staging；持久化 Settings 路由）
    try:
        _run_distill_agent_stage(request_id, asset_id, sp_dir, stage_dir)
    except _PendingDistill as pending:
        return _pending_material_distill_result(
            asset_id, pending.request_id,
            "等待 Qoder /gowrite：正在原著学习，完成后将自动整理参考知识",
        )

    # 4) 确定性完成门 + 受控发布到 02 + discovery + 刷新
    try:
        fin = _finalize_reference_distill(request_id, asset, sp_dir, stage_dir)
    except MaterialsError as exc:
        audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "book_distill", details={"skill": "BookDistill"})
        audit.finish_file(request_id, audit.STATUS_FAILED, error=str(exc))
        raise
    audit.append_event(request_id, audit.EVENT_SKILL_COMPLETED, "book_distill", details={"skill": "BookDistill", "asset_id": asset_id})
    audit.finish_file(request_id, audit.STATUS_COMPLETED)
    return {
        "asset_id": asset_id,
        "status": "completed",
        "output_dir": fin["output_dir"],
        "message": "原著学习完成（已整理参考知识并刷新素材状态）",
    }


def _run_distill_agent_stage(request_id: str, asset_id: str, sp_dir: Path, stage_dir: Path) -> None:
    """蒸馏的 Agent 阅读/收敛阶段：走持久化 Settings 执行路由（一次 turn）。

    - Direct：adapter 同步执行（长任务可接受；这是显式离线处理操作）；
    - Interactive：创建 /gowrite 请求，由 get_book_distill_request 轮询后接续
      assemble/profile/bkp。
    本函数只负责 Direct 与 Interactive 请求创建；Interactive 的 finalize 由
    get_book_distill_request 调用 _finalize_distill 完成。
    """
    from config.settings import EXECUTION_MODE_DIRECT, SettingsStore
    settings = SettingsStore().load()
    import importlib.util
    builder_path = _BOOK_DISTILL_AGENT_TASK_BUILDER
    spec = importlib.util.spec_from_file_location("gowrite_bookdistill_agent_task", builder_path)
    if spec is None or spec.loader is None:
        raise MaterialsError("BookDistill Agent 任务构建器缺失。")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    task = module.build_distill_agent_task(sp_dir, stage_dir)

    if settings.default_execution_mode != EXECUTION_MODE_DIRECT:
        from operations import qoder_bridge as bridge
        try:
            bridge.create_request(
                task=task,
                kind="book_distill_propose",
                meta={
                    "request_id": request_id,
                    "asset_id": asset_id,
                    "target_label": str(_ledger_asset(asset_id).get("name") or ""),
                    "sp_dir": str(sp_dir),
                    "stage_dir": str(stage_dir),
                    "execution": {
                        "execution_mode": "interactive_bridge",
                        "agent_id": settings.interactive_agent,
                        "model": None,
                    },
                },
                request_id=request_id,
                timeout_seconds=6 * 60 * 60,
                activate_for_gowrite=True,  # Interactive：显式激活 /gowrite
            )
        except bridge.BridgeBusyError as exc:
            # 已有等待 /gowrite 的交互任务：绝不清除/覆盖它
            audit.finish_file(request_id, audit.STATUS_FAILED, error=str(exc))
            raise MaterialsError(str(exc)) from exc
        audit.append_event(request_id, audit.EVENT_BRIDGE_WAITING, component="book_distill")
        raise _PendingDistill(request_id)
    from operations import agent_runner as runner
    try:
        adapter, agent_request = runner._build_adapter()
    except Exception as exc:  # noqa: BLE001
        audit.finish_file(request_id, audit.STATUS_FAILED, error=str(exc))
        raise MaterialsError("原著学习执行配置不可用，请检查设置后重试。") from exc
    agent_request.task = task
    agent_request.cwd = str(get_repo_root())
    audit.append_event(
        request_id, audit.EVENT_AGENT_DIRECT_PROCESS_STARTED, "book_distill",
        details={"agent": adapter.name, "asset_id": asset_id},
    )
    try:
        result = adapter.run(agent_request)
    except Exception as exc:  # noqa: BLE001
        audit.append_event(request_id, audit.EVENT_AGENT_FAILED, "book_distill", details={"error": str(exc)[:200]})
        audit.finish_file(request_id, audit.STATUS_FAILED, error=f"蒸馏执行失败：{exc}")
        raise MaterialsError("原著学习失败，请重试。") from exc
    if result.status != "completed":
        audit.append_event(request_id, audit.EVENT_AGENT_FAILED, "book_distill", details={"error": (result.error or "")[:200]})
        audit.finish_file(request_id, audit.STATUS_FAILED, error=result.error or "蒸馏未完成")
        raise MaterialsError("原著学习未完成，请重试。")
    audit.append_event(request_id, audit.EVENT_AGENT_COMPLETED, "book_distill")


class _PendingDistill(Exception):
    """Interactive 蒸馏等待唯一一次 /gowrite（内部控制流）。"""

    def __init__(self, request_id: str) -> None:
        super().__init__(request_id)
        self.request_id = request_id


def _material_execution_facts(request: dict[str, Any]) -> dict[str, Any]:
    """Expose only the existing request's author-safe execution facts."""
    meta = request.get("meta") or {}
    execution = meta.get("execution") or {}
    return {
        "execution_mode": execution.get("execution_mode"),
        "agent_id": execution.get("agent_id"),
        "model": execution.get("model"),
        "agent_command": request.get("agent_command"),
        "execution_phase": request.get("execution_phase"),
    }


def _pending_material_distill_result(asset_id: str, request_id: str, message: str) -> dict[str, Any]:
    from operations import qoder_bridge as bridge
    request = bridge.get_request(request_id) or {}
    return {
        "asset_id": asset_id,
        "status": "pending",
        "request_id": request_id,
        "message": message,
        **_material_execution_facts(request),
    }


def _finalize_distill(request_id: str, asset_id: str, sp_dir: Path, stage_dir: Path) -> dict[str, Any]:
    """Interactive 蒸馏的确定性完成门；与 Direct 路径严格一致。

    §9/§11：发布前再次确认请求仍有效且未取消（TOCTOU 防护）；取消的请求绝不发布到 02。
    """
    from operations import qoder_bridge as bridge
    req = bridge.get_request(request_id)
    if req is None or req.get("state") == "canceled":
        bridge.cleanup_request(request_id)
        audit.finish_file(request_id, audit.STATUS_CANCELED)
        raise MaterialsError("原著学习已取消。")
    try:
        fin = _finalize_reference_distill(request_id, _ledger_asset(asset_id), sp_dir, stage_dir)
    except MaterialsError as exc:
        audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "book_distill", details={"skill": "BookDistill"})
        audit.finish_file(request_id, audit.STATUS_FAILED, error=str(exc))
        bridge.cleanup_request(request_id)
        raise
    bridge.cleanup_request(request_id)
    audit.append_event(request_id, audit.EVENT_SKILL_COMPLETED, "book_distill", details={"skill": "BookDistill"})
    audit.finish_file(request_id, audit.STATUS_COMPLETED)
    return {
        "asset_id": asset_id,
        "status": "completed",
        "output_dir": fin["output_dir"],
        "message": "原著学习完成（已整理参考知识并刷新素材状态）",
    }


def get_book_distill_request(request_id: str) -> dict[str, Any]:
    """轮询 Interactive 蒸馏：pending / completed / failed / canceled。

    收到 Agent 完成响应后立即执行确定性 finalize（assemble/profile/bkp/刷新）。
    """
    from operations import qoder_bridge as bridge
    request_id = (request_id or "").strip()
    if not request_id:
        raise MaterialsError("缺少任务标识（request_id）。")
    request = bridge.get_request(request_id)
    if request is None:
        audit.finish_file(request_id, audit.STATUS_FAILED, error="任务已失效，请重新发起。")
        return {"request_id": request_id, "status": "failed", "error": "任务已失效，请重新发起。"}
    state = request.get("state")
    meta = request.get("meta") or {}
    if state == "canceled":
        bridge.cleanup_request(request_id)
        audit.finish_file(request_id, audit.STATUS_CANCELED)
        return {"request_id": request_id, "status": "canceled"}
    if bridge.is_expired(request):
        bridge.cleanup_request(request_id)
        audit.finish_file(request_id, audit.STATUS_FAILED, error="任务已超时")
        return {"request_id": request_id, "status": "expired", "error": "任务已超时，请重新发起。"}
    response = bridge.read_response(request_id)
    if response is None:
        if request.get("execution_phase") == "running":
            message = "Agent 正在执行素材学习"
        else:
            message = "等待 Qoder /gowrite：正在原著学习，完成后将自动整理参考知识"
        return {
            "request_id": request_id, "status": "pending", "message": message,
            **_material_execution_facts(request),
        }
    if response.get("request_id") != request_id:
        bridge.cleanup_request(request_id)
        return {"request_id": request_id, "status": "failed", "error": "返回结果与任务不匹配，已丢弃。"}
    if response.get("status") != "completed":
        error = "原著学习失败，请重试。"
        bridge.cleanup_request(request_id)
        audit.finish_file(request_id, audit.STATUS_FAILED, error=error)
        return {"request_id": request_id, "status": "failed", "error": error}
    audit.append_event(request_id, audit.EVENT_BRIDGE_RESPONSE_RECEIVED, "book_distill")
    asset_id = meta.get("asset_id")
    if not isinstance(asset_id, str) or not asset_id.strip():
        bridge.cleanup_request(request_id)
        audit.finish_file(request_id, audit.STATUS_FAILED, error="蒸馏任务缺少素材标识")
        return {"request_id": request_id, "status": "failed", "error": "原著学习任务缺少素材标识，请重新发起。"}
    try:
        result = _finalize_distill(
            request_id, asset_id.strip(), Path(meta["sp_dir"]), Path(meta["stage_dir"]),
        )
    except MaterialsError as exc:
        return {"request_id": request_id, "status": "failed", "error": str(exc)}
    return {"request_id": request_id, "status": "completed", "result": result}


def cancel_book_distill_request(request_id: str) -> dict[str, Any]:
    from operations import qoder_bridge as bridge
    request_id = (request_id or "").strip()
    if not request_id:
        raise MaterialsError("缺少任务标识（request_id）。")
    request = bridge.get_request(request_id)
    if request is not None:
        bridge.mark_canceled(request_id)
        stage_dir = Path(str((request.get("meta") or {}).get("stage_dir") or ""))
        allowed_root = (get_repo_root() / "06_工作区" / "BookDistill").resolve()
        try:
            resolved = stage_dir.resolve()
            if resolved.parent == allowed_root and resolved.name.startswith(f"{request_id}_"):
                shutil.rmtree(resolved, ignore_errors=True)
        except (OSError, ValueError):
            pass
        audit.finish_file(request_id, audit.STATUS_CANCELED)
    bridge.cleanup_request(request_id)
    return {"request_id": request_id, "status": "canceled"}


# ---------------------------------------------------------------------------
# 4.6 MethodPrepare 显式提纯（方法/技巧资料；确定性，无模型）
# ---------------------------------------------------------------------------

_MP_SCRIPT = _REPO_ROOT / "05_Skills与自动化" / "01_Skills" / "MethodPrepare" / "scripts" / "method_prepare.py"
_MD_SCRIPT = _REPO_ROOT / "05_Skills与自动化" / "01_Skills" / "MethodDistill" / "method_distill.py"


def _refresh_catalog_or_fail(request_id: str, component: str) -> None:
    """结算后刷新素材状态；失败抛稳定错误（不阻断已完成的产物）。"""
    catalog, _, _ = _load_materialintake()
    with material_settlement.serialized():
        rc = catalog.refresh_and_render(get_repo_root(), check_only=False)
    if rc != 0:
        audit.append_event(request_id, audit.EVENT_SKILL_FAILED, component, details={"step": "catalog_refresh"})
        raise MaterialsError("处理完成，但素材状态刷新失败，请手动刷新素材页。")


def run_method_prepare(asset_id: str) -> dict[str, Any]:
    """对 METHOD_SOURCE 素材显式运行 MethodPrepare（确定性、无模型）。

    输出落 06_工作区/MethodPrepare/<asset_id>_<名称>/（Local Only，不进 Git）；
    成功后刷新三份 material state files（§6：Workbench 路径不做 Git 同步）。
    """
    asset_id = (asset_id or "").strip()
    if not asset_id:
        raise MaterialsError("缺少素材标识（asset_id）。")
    asset = _ledger_asset(asset_id)
    if asset.get("type") != "METHOD_SOURCE":
        raise MaterialsError(f"素材 {asset_id} 不是方法/技巧资料（METHOD_SOURCE），不适用 MethodPrepare。")

    request_id = audit.new_request_id()
    audit.AuditRecorder(request_id, "method_prepare", project_id=None)
    audit.append_event(request_id, audit.EVENT_SKILL_STARTED, "method_prepare",
                       details={"skill": "MethodPrepare", "asset_id": asset_id})
    if not _MP_SCRIPT.is_file():
        audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "method_prepare", details={"skill": "MethodPrepare"})
        audit.finish_file(request_id, audit.STATUS_FAILED, error="MethodPrepare 运行脚本缺失")
        raise MaterialsError("MethodPrepare 运行脚本缺失。")
    cmd = [sys.executable, str(_MP_SCRIPT), "--root", str(get_repo_root()), "--asset", asset_id]
    audit.append_event(
        request_id, audit.EVENT_AGENT_DIRECT_PROCESS_STARTED, "method_prepare",
        details={"asset_id": asset_id, "command": "method_prepare.py --asset " + asset_id},
    )
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30 * 60,
        )
    except subprocess.TimeoutExpired as exc:
        audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "method_prepare", details={"skill": "MethodPrepare"})
        audit.finish_file(request_id, audit.STATUS_FAILED, error="方法提纯超时（30 分钟）")
        raise MaterialsError("方法提纯超时（30 分钟），请重试或检查素材。") from exc
    except OSError as exc:
        audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "method_prepare", details={"skill": "MethodPrepare"})
        audit.finish_file(request_id, audit.STATUS_FAILED, error=str(exc))
        raise MaterialsError(f"方法提纯启动失败：{exc}") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "")[:800]
        audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "method_prepare",
                           details={"skill": "MethodPrepare", "detail": detail})
        audit.finish_file(request_id, audit.STATUS_FAILED, error=detail)
        raise MaterialsError(_prepare_error_message(detail))

    # settlement：刷新三份 material state files（§6：Workbench 路径不做 Git precheck/commit/push）
    _refresh_catalog_or_fail(request_id, "method_prepare")
    audit.append_event(request_id, audit.EVENT_SKILL_COMPLETED, "method_prepare",
                       details={"skill": "MethodPrepare", "asset_id": asset_id})
    audit.finish_file(request_id, audit.STATUS_COMPLETED)
    return {
        "asset_id": asset_id,
        "status": "completed",
        "message": "方法提纯完成（MethodPrepare 已运行并刷新素材状态）",
        "output_tail": "\n".join((proc.stdout or "").splitlines()[-6:]),
    }


# ---------------------------------------------------------------------------
# 4.7 MethodDistill 显式蒸馏（方法知识；确定性阶段 + 一次 Agent 抽取 turn）
# ---------------------------------------------------------------------------

_METHOD_DISTILL_TASK_TEMPLATE = """你是 Go Write 的方法知识蒸馏执行器（MethodDistill 语义抽取阶段）。

输入：
- MethodPrepare PASS 包：{mp_dir}（full.md 全文 + sections/ 分节 + structure.json）
- 蒸馏输出目录：{method_dir}（脚手架已生成：identity.json / method_profile.md /
  evidence.md / knowledge/cards.md 模板）
（validate 与 prepare 已由 Go Write 完成。）

你的任务（按顺序）：
1. 通读 {mp_dir}/full.md（需要精确行号时对照 sections/ 分节）。
2. 抽取该书**明确教授**的可迁移创作方法，逐张写入 {method_dir}/knowledge/cards.md
   （严格遵守模板中的规范卡格式：## M0001｜标题，字段齐全，id 从 M0001 起递增不重复）：
   - statement 一句话方法陈述；method_kind 五选一；
   - 适用条件/步骤/检查项/失效模式/边界只在原书明确给出时填写，绝不外推；
   - evidence 必须是真实存在的 MethodPrepare 行号引用，形如 sections/S0001.md#L3-L12。
3. 区分原书主张与 Go Write 已验证事实：未验证的一律写 source-bound，不得声明为普适真理。
4. capability_candidate 只标记潜在可执行的方法知识；它绝不创建任何 Skill。
5. 填写 {method_dir}/method_profile.md（身份/覆盖/边界）与 {method_dir}/evidence.md
   （精选证据）。
6. 不修改 {mp_dir} 与 identity.json 中的任何内容。

全部写入完成后，在最终回复中输出一行 JSON：{{"status": "completed", "card_count": <写入方法卡数>}}"""


def _find_mp_dir(asset_id: str) -> Path:
    root = get_repo_root() / "06_工作区" / "MethodPrepare"
    if not root.exists():
        raise MaterialsError("还没有任何方法提纯产物，请先对素材执行「提纯」。")
    candidates = list(root.glob(f"{asset_id}_*"))
    if not candidates:
        raise MaterialsError(f"素材 {asset_id} 还没有方法提纯产物（06_工作区/MethodPrepare），请先提纯。")
    return candidates[0]


def _run_md_cli(args: list[str], request_id: str, *, timeout: int = 10 * 60) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(_MD_SCRIPT)] + args
    audit.append_event(
        request_id, audit.EVENT_AGENT_DIRECT_PROCESS_STARTED, "method_distill",
        details={"command": "method_distill.py " + " ".join(args[:2])},
    )
    return subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
    )


def run_method_distill(asset_id: str) -> dict[str, Any]:
    """对 MethodPrepare PASS 的方法素材显式运行 MethodDistill。

    阶段：validate（确定性）→ prepare（确定性）→ Agent 抽取 turn（持久化
    Settings 路由；Direct 同步 / Interactive /gowrite）→ finalize（确定性定稿：
    重复 id / 空 statement / 断裂证据 / 过期指纹 / 检索加载器不可解析 → 拒绝）
    → 受控发布到 02 → knowledge 可用（§6：不做 Git 同步）。
    """
    asset_id = (asset_id or "").strip()
    if not asset_id:
        raise MaterialsError("缺少素材标识（asset_id）。")
    asset = _ledger_asset(asset_id)
    if asset.get("type") != "METHOD_SOURCE":
        raise MaterialsError(f"素材 {asset_id} 不是方法/技巧资料（METHOD_SOURCE），不适用 MethodDistill。")

    request_id = audit.new_request_id()
    audit.AuditRecorder(request_id, "method_distill")
    audit.append_event(request_id, audit.EVENT_SKILL_STARTED, "method_distill",
                       details={"skill": "MethodDistill", "asset_id": asset_id})

    # 0) §9 前置：必须有真实当前 MethodPrepare Markdown（绝不直接读 EPUB/PDF/TXT）
    prep = _prepare_package_current(asset)
    if not prep["available"]:
        audit.finish_file(request_id, audit.STATUS_FAILED, error="prepare-not-current")
        raise MaterialsError(prep["reason"] or "方法学习输入不是当前有效的 Markdown，请先重新提纯。")

    # 1) 定位 MethodPrepare PASS 包并 validate
    mp_dir = _find_mp_dir(asset_id)
    try:
        proc = _run_md_cli(["validate", "--input", str(mp_dir)], request_id)
    except subprocess.TimeoutExpired:
        audit.finish_file(request_id, audit.STATUS_FAILED, error="方法蒸馏校验超时")
        raise MaterialsError("方法学习检查超时，请重试。")
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "")[:800]
        audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "method_distill", details={"skill": "MethodDistill", "detail": detail})
        audit.finish_file(request_id, audit.STATUS_FAILED, error=detail)
        raise MaterialsError(_distill_error_message(detail))

    # 2) prepare（确定性脚手架）→ 06 request-scoped staging（绝不写正式 02）
    stage_dir = get_repo_root() / "06_工作区" / "MethodDistill" / f"{request_id}_{mp_dir.name}"
    stage_method_dir = stage_dir / "method"
    try:
        proc = _run_md_cli(["prepare", "--input", str(mp_dir), "--output", str(stage_method_dir)], request_id)
    except subprocess.TimeoutExpired:
        audit.finish_file(request_id, audit.STATUS_FAILED, error="方法蒸馏准备超时")
        raise MaterialsError("方法学习准备超时，请重试。")
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "")[:800]
        audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "method_distill", details={"skill": "MethodDistill", "detail": detail})
        audit.finish_file(request_id, audit.STATUS_FAILED, error=detail)
        raise MaterialsError(_distill_error_message(detail))

    # 3) Agent 语义抽取 turn（只写 staging；持久化 Settings 路由）
    try:
        _run_method_distill_agent_stage(request_id, asset_id, mp_dir, stage_method_dir)
    except _PendingMethodDistill as pending:
        return _pending_material_distill_result(
            asset_id, pending.request_id,
            "等待 Qoder /gowrite：正在方法学习，完成后将自动整理方法知识",
        )

    # 4) Direct 路径直接调用无 bridge 依赖的确定性核心。
    try:
        fin = _finalize_method_distill_core(request_id, asset_id, mp_dir, stage_method_dir)
    except MaterialsError as exc:
        audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "method_distill",
                           details={"skill": "MethodDistill"})
        audit.finish_file(request_id, audit.STATUS_FAILED, error=str(exc))
        raise
    audit.append_event(request_id, audit.EVENT_SKILL_COMPLETED, "method_distill",
                       details={"skill": "MethodDistill", "asset_id": asset_id})
    audit.finish_file(request_id, audit.STATUS_COMPLETED)
    return {
        "asset_id": asset_id,
        "status": "completed",
        "output_dir": fin["output_dir"],
        "message": "方法学习完成（已整理为可调用的方法知识）",
    }


def _finalize_method_distill_core(request_id: str, asset_id: str,
                                  mp_dir: Path, stage_method_dir: Path) -> dict[str, Any]:
    """Bridge-independent deterministic finalize + transactional publish/verification."""
    try:
        proc = _run_md_cli(["finalize", "--input", str(mp_dir), "--output", str(stage_method_dir)], request_id)
    except subprocess.TimeoutExpired:
        audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "method_distill", details={"skill": "MethodDistill"})
        raise MaterialsError("方法知识定稿超时，请重试。")
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "")[:800]
        audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "method_distill", details={"skill": "MethodDistill", "detail": detail})
        raise MaterialsError(_distill_error_message(detail))

    target_method_dir = get_repo_root() / "02_素材知识库" / mp_dir.name / "method"
    tx = _PublishTransaction(stage_method_dir, target_method_dir, request_id)
    with material_settlement.serialized():
        try:
            tx.begin()
            if not _knowledge_is_discoverable({"id": asset_id, "type": "METHOD_SOURCE"}):
                raise MaterialsError("knowledge discovery failed")
            _refresh_catalog_or_fail(request_id, "method_distill")
            tx.commit()
        except Exception as exc:  # noqa: BLE001 - technical detail stays in audit
            audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "method_distill",
                               details={"step": "post_publish_verification", "error": str(exc)[:300]})
            _rollback_publish_or_fail(tx, request_id, "method_distill")
            raise MaterialsError("方法学习结果暂不能用于写作，已保留原知识包，请重试。") from exc
    return {"output_dir": str(target_method_dir)}


def _finalize_method_distill_interactive(request_id: str, asset_id: str,
                                          mp_dir: Path,
                                          stage_method_dir: Path) -> dict[str, Any]:
    """Validate Interactive request ownership, then call the bridge-independent core."""
    from operations import qoder_bridge as bridge
    request = bridge.get_request(request_id)
    valid = (
        request is not None
        and request.get("request_id") == request_id
        and request.get("kind") == "method_distill_propose"
        and request.get("state") != "canceled"
        and not bridge.is_expired(request)
    )
    if not valid:
        if request is not None:
            bridge.cleanup_request(request_id)
        audit.finish_file(request_id, audit.STATUS_CANCELED,
                          error="interactive request missing/canceled/expired")
        raise MaterialsError("方法学习已取消。")
    try:
        fin = _finalize_method_distill_core(
            request_id, asset_id, mp_dir, stage_method_dir)
    except MaterialsError as exc:
        audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "method_distill",
                           details={"skill": "MethodDistill"})
        audit.finish_file(request_id, audit.STATUS_FAILED, error=str(exc))
        bridge.cleanup_request(request_id)
        raise
    bridge.cleanup_request(request_id)
    audit.append_event(request_id, audit.EVENT_SKILL_COMPLETED, "method_distill",
                       details={"skill": "MethodDistill", "asset_id": asset_id})
    audit.finish_file(request_id, audit.STATUS_COMPLETED)
    return {
        "asset_id": asset_id,
        "status": "completed",
        "output_dir": fin["output_dir"],
        "message": "方法学习完成（已整理为可调用的方法知识）",
    }


class _PendingMethodDistill(Exception):
    """Interactive 方法蒸馏等待 /gowrite（内部控制流）。"""

    def __init__(self, request_id: str) -> None:
        super().__init__(request_id)
        self.request_id = request_id


def _run_method_distill_agent_stage(request_id: str, asset_id: str,
                                    mp_dir: Path, stage_method_dir: Path) -> None:
    """方法蒸馏 Agent 抽取阶段：复用持久化 Settings 执行路由（一次 turn；只写 06 staging）。"""
    from config.settings import EXECUTION_MODE_DIRECT, SettingsStore
    settings = SettingsStore().load()
    task = _METHOD_DISTILL_TASK_TEMPLATE.format(mp_dir=str(mp_dir), method_dir=str(stage_method_dir))

    if settings.default_execution_mode != EXECUTION_MODE_DIRECT:
        from operations import qoder_bridge as bridge
        try:
            bridge.create_request(
                task=task,
                kind="method_distill_propose",
                meta={
                    "request_id": request_id,
                    "asset_id": asset_id,
                    "target_label": str(_ledger_asset(asset_id).get("name") or ""),
                    "mp_dir": str(mp_dir),
                    "stage_method_dir": str(stage_method_dir),
                    "execution": {
                        "execution_mode": "interactive_bridge",
                        "agent_id": settings.interactive_agent,
                        "model": None,
                    },
                },
                request_id=request_id,
                timeout_seconds=6 * 60 * 60,
                activate_for_gowrite=True,
            )
        except bridge.BridgeBusyError as exc:
            audit.finish_file(request_id, audit.STATUS_FAILED, error=str(exc))
            raise MaterialsError(str(exc)) from exc
        audit.append_event(request_id, audit.EVENT_BRIDGE_WAITING, component="method_distill")
        raise _PendingMethodDistill(request_id)
    from operations import agent_runner as runner
    try:
        adapter, agent_request = runner._build_adapter()
    except Exception as exc:  # noqa: BLE001
        audit.finish_file(request_id, audit.STATUS_FAILED, error=str(exc))
        raise MaterialsError("方法学习执行配置不可用，请检查设置后重试。") from exc
    agent_request.task = task
    agent_request.cwd = str(get_repo_root())
    audit.append_event(
        request_id, audit.EVENT_AGENT_DIRECT_PROCESS_STARTED, "method_distill",
        details={"agent": adapter.name, "asset_id": asset_id},
    )
    try:
        result = adapter.run(agent_request)
    except Exception as exc:  # noqa: BLE001
        audit.append_event(request_id, audit.EVENT_AGENT_FAILED, "method_distill", details={"error": str(exc)[:200]})
        audit.finish_file(request_id, audit.STATUS_FAILED, error=f"方法蒸馏执行失败：{exc}")
        raise MaterialsError("方法学习失败，请重试。") from exc
    if result.status != "completed":
        audit.append_event(request_id, audit.EVENT_AGENT_FAILED, "method_distill", details={"error": (result.error or "")[:200]})
        audit.finish_file(request_id, audit.STATUS_FAILED, error=result.error or "方法蒸馏未完成")
        raise MaterialsError("方法学习未完成，请重试。")
    audit.append_event(request_id, audit.EVENT_AGENT_COMPLETED, "method_distill")


def get_method_distill_request(request_id: str) -> dict[str, Any]:
    """轮询 Interactive 方法蒸馏：pending / completed / failed / canceled。"""
    from operations import qoder_bridge as bridge
    request_id = (request_id or "").strip()
    if not request_id:
        raise MaterialsError("缺少任务标识（request_id）。")
    request = bridge.get_request(request_id)
    if request is None:
        audit.finish_file(request_id, audit.STATUS_FAILED, error="任务已失效，请重新发起。")
        return {"request_id": request_id, "status": "failed", "error": "任务已失效，请重新发起。"}
    state = request.get("state")
    meta = request.get("meta") or {}
    if state == "canceled":
        bridge.cleanup_request(request_id)
        audit.finish_file(request_id, audit.STATUS_CANCELED)
        return {"request_id": request_id, "status": "canceled"}
    if bridge.is_expired(request):
        bridge.cleanup_request(request_id)
        audit.finish_file(request_id, audit.STATUS_FAILED, error="任务已超时")
        return {"request_id": request_id, "status": "expired", "error": "任务已超时，请重新发起。"}
    response = bridge.read_response(request_id)
    if response is None:
        if request.get("execution_phase") == "running":
            message = "Agent 正在执行素材学习"
        else:
            message = "等待 Qoder /gowrite：正在方法学习，完成后将自动整理方法知识"
        return {
            "request_id": request_id, "status": "pending", "message": message,
            **_material_execution_facts(request),
        }
    if response.get("request_id") != request_id:
        bridge.cleanup_request(request_id)
        return {"request_id": request_id, "status": "failed", "error": "返回结果与任务不匹配，已丢弃。"}
    if response.get("status") != "completed":
        error = "方法学习失败，请重试。"
        bridge.cleanup_request(request_id)
        audit.finish_file(request_id, audit.STATUS_FAILED, error=error)
        return {"request_id": request_id, "status": "failed", "error": error}
    audit.append_event(request_id, audit.EVENT_BRIDGE_RESPONSE_RECEIVED, "method_distill")
    try:
        result = _finalize_method_distill_interactive(
            request_id, str(meta.get("asset_id") or ""),
            Path(meta["mp_dir"]), Path(meta["stage_method_dir"]),
        )
    except MaterialsError as exc:
        return {"request_id": request_id, "status": "failed", "error": str(exc)}
    return {"request_id": request_id, "status": "completed", "result": result}


def cancel_method_distill_request(request_id: str) -> dict[str, Any]:
    from operations import qoder_bridge as bridge
    request_id = (request_id or "").strip()
    if not request_id:
        raise MaterialsError("缺少任务标识（request_id）。")
    request = bridge.get_request(request_id)
    if request is not None:
        bridge.mark_canceled(request_id)
        stage_method_dir = Path(str((request.get("meta") or {}).get("stage_method_dir") or ""))
        stage_dir = stage_method_dir.parent
        allowed_root = (get_repo_root() / "06_工作区" / "MethodDistill").resolve()
        try:
            resolved = stage_dir.resolve()
            if resolved.parent == allowed_root and resolved.name.startswith(f"{request_id}_"):
                shutil.rmtree(resolved, ignore_errors=True)
        except (OSError, ValueError):
            pass
        audit.finish_file(request_id, audit.STATUS_CANCELED)
    bridge.cleanup_request(request_id)
    return {"request_id": request_id, "status": "canceled"}


# ---------------------------------------------------------------------------
# 4.8 作者面通用入口：prepare_material / distill_material（后端按类型分派）
# ---------------------------------------------------------------------------

def prepare_material(asset_id: str) -> dict[str, Any]:
    """作者面「提纯」：UI 只传素材 id，后端按 canonical 类型分派。

    REFERENCE_WORK → SourcePrepare；METHOD_SOURCE → MethodPrepare；
    其他类型保持保守行为（拒绝，不静默跑不匹配的提纯器）。
    """
    asset = _ledger_asset((asset_id or "").strip())
    if asset.get("type") == "METHOD_SOURCE":
        return run_method_prepare(asset_id)
    return run_source_prepare(asset_id)


def distill_material(asset_id: str) -> dict[str, Any]:
    """作者面「蒸馏」：UI 只传素材 id，后端按 canonical 类型分派。

    REFERENCE_WORK → BookDistill；METHOD_SOURCE → MethodDistill；其他类型保守拒绝。
    """
    asset_id = (asset_id or "").strip()
    asset = _ledger_asset(asset_id)
    # The in-process claim closes the scan-to-request race without holding the
    # settlement lock during preparation or Agent work. Persisted requests keep
    # the guard authoritative across Workbench reloads.
    with material_settlement.claim_active_asset(asset_id) as claimed:
        if not claimed:
            raise MaterialsError("该素材正在学习，请等待完成或取消当前任务。")
        from operations import qoder_bridge as bridge
        requests_dir = bridge.get_bridge_root() / "requests"
        if requests_dir.exists():
            for path in requests_dir.glob("*.json"):
                pending = bridge.get_request(path.stem)
                if pending and pending.get("state") == "pending" and (pending.get("meta") or {}).get("asset_id") == asset_id:
                    raise MaterialsError("该素材正在学习，请等待完成或取消当前任务。")
        if asset.get("type") == "METHOD_SOURCE":
            return run_method_distill(asset_id)
        return run_book_distill(asset_id)


def get_material_distill_request(request_id: str) -> dict[str, Any]:
    """通用蒸馏轮询：按桥请求 kind 分派到 BookDistill / MethodDistill。"""
    from operations import qoder_bridge as bridge
    request_id = (request_id or "").strip()
    if not request_id:
        raise MaterialsError("缺少任务标识（request_id）。")
    request = bridge.get_request(request_id)
    if request is None:
        return {"request_id": request_id, "status": "failed", "error": "任务已失效，请重新发起。"}
    if request.get("kind") == "method_distill_propose":
        return get_method_distill_request(request_id)
    return get_book_distill_request(request_id)


def cancel_material_distill_request(request_id: str) -> dict[str, Any]:
    """通用蒸馏取消：按桥请求 kind 分派。"""
    from operations import qoder_bridge as bridge
    request_id = (request_id or "").strip()
    if not request_id:
        raise MaterialsError("缺少任务标识（request_id）。")
    request = bridge.get_request(request_id)
    if request is not None and request.get("kind") == "method_distill_propose":
        return cancel_method_distill_request(request_id)
    return cancel_book_distill_request(request_id)


# ---------------------------------------------------------------------------
# 当前阶段文件夹（作者显式点击；调用方只能提供 canonical asset_id）
# ---------------------------------------------------------------------------

_FOLDER_ERROR = "找不到这份资料对应的文件夹，请刷新状态后重试。"


def _canonical_source_folder(asset: dict[str, Any]) -> Path | None:
    material_root = get_repo_root() / "01_原始素材"
    for entry in asset.get("files") or []:
        if not isinstance(entry, dict) or not entry.get("path"):
            continue
        source = material_root / str(entry["path"])
        if source.exists():
            return source.parent
    return None


def _current_material_folder(asset: dict[str, Any]) -> Path | None:
    stage = _classify_author_group(asset)["workflow_stage"]
    asset_id = str(asset.get("id") or "").strip()
    if stage in ("new", "other"):
        return _canonical_source_folder(asset)
    if stage == "purified":
        return _prepare_package_path(asset)
    if stage == "writing":
        knowledge_root = get_repo_root() / "02_素材知识库"
        return next((path for path in sorted(knowledge_root.glob(f"{asset_id}_*"))
                     if path.is_dir()), None)
    return None


def _launch_folder(path: Path) -> None:
    """Windows desktop launcher kept as one mockable boundary for tests."""
    os.startfile(str(path))  # type: ignore[attr-defined]


def open_material_folder(asset_id: str) -> dict[str, Any]:
    """Open the selected material's real current-stage folder without exposing paths."""
    asset = _ledger_asset((asset_id or "").strip())
    target = _current_material_folder(asset)
    try:
        root = get_repo_root().resolve(strict=True)
        resolved = target.resolve(strict=True) if target is not None else None
    except OSError as exc:
        raise MaterialsError(_FOLDER_ERROR) from exc
    if resolved is None or not resolved.is_dir() or not resolved.is_relative_to(root):
        raise MaterialsError(_FOLDER_ERROR)
    try:
        _launch_folder(resolved)
    except OSError as exc:
        raise MaterialsError(_FOLDER_ERROR) from exc
    return {"asset_id": str(asset.get("id") or ""), "opened": True}


# ---------------------------------------------------------------------------
# 素材详情语义（写作时能否调用 + 当前阶段 + 下一步；页面加载零模型）
# ---------------------------------------------------------------------------

def get_material_detail(asset_id: str) -> dict[str, Any]:
    """单素材作者详情：只投影既有知识，不泄露后台阶段。"""
    asset = _ledger_asset(asset_id)
    classified = _classify_author_group(asset)
    summary, sections = _learning_projection(asset) if classified["state"] == "ready" else (None, [])
    labels = {
        "pending_prepare": "待提纯", "pending_distill": "待学习",
        "needs_attention": "需要检查", "ready": "可用于写作",
    }
    return {
        "id": asset.get("id"),
        "name": asset.get("name") or "",
        "type": asset.get("type") or "",
        "type_label": _author_type_label(str(asset.get("type") or "")),
        "author": asset.get("author") or "",
        "source_formats": _source_formats(asset),
        "state": classified["state"],
        "state_label": labels[classified["state"]],
        "workflow_stage": classified["workflow_stage"],
        "writing_callable": classified["writing_callable"],
        "attention_message": classified.get("attention_message"),
        "prepared_available": classified.get("prepared_available", False),
        "prepared_format": classified.get("prepared_format"),
        "knowledge_package_kind": classified.get("knowledge_package_kind"),
        "learning_summary": summary,
        "learning_sections": sections,
    }
