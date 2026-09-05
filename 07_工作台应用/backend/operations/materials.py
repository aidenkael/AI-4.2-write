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
- production 尊重 MaterialIntake 自身的 safety/precheck/writeback 行为；
- 测试使用 temp roots 并绕过 git sync。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from operations import execution_audit as audit

_REPO_ROOT = Path(__file__).resolve().parents[3]

_MI_DIR = _REPO_ROOT / "05_Skills与自动化" / "01_Skills" / "MaterialIntake"

# 与 MaterialIntake/intake.py 的 INTAKE_ALLOWLIST 保持一致（最小允许进 Git 的面）
_INTAKE_ALLOWLIST = [
    "01_原始素材/素材资产.json",
    "01_原始素材/素材清单.csv",
    "01_原始素材/素材总索引.md",
]

# 允许从本地导入到 00_待入库 的素材后缀（MaterialIntake 支持的类型）
_SUPPORTED_IMPORT_SUFFIXES = {".epub", ".txt", ".pdf", ".zip", ".mobi", ".azw3"}
# 单文件导入上限（200 MB；防误选超大文件）
_MAX_IMPORT_BYTES = 200 * 1024 * 1024

# Agent 分类任务超时（一次分类 turn 的最大时长）
_CLASSIFY_TIMEOUT_SECONDS = 60 * 60


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


_AUTHOR_TYPE_LABELS = {
    "REFERENCE_WORK": "原著",
    "METHOD_SOURCE": "技巧书",
    "RESEARCH": "研究资料",
    "LOOSE_MATERIAL": "零散素材",
    "NEEDS_REVIEW": "待确认",
}


def _author_type_label(asset_type: str) -> str:
    return _AUTHOR_TYPE_LABELS.get(asset_type, "其他")


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
        return [asset_dir / "bkp" / "author_view.md", asset_dir / "bkp" / "model.md"]
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


def _classify_author_group(a: dict[str, Any]) -> dict[str, Any]:
    """把后端 catalog/type/status 机器事实映射为作者可读的分类。

    只回答作者真正关心的问题：
    - 写作时能否被调用（KnowledgeRetrieve 只使用已定稿可用知识）；
    - 当前为什么能/不能；
    - 下一步是什么。

    分组：
    - usable（可用于写作）：knowledge.status == "可用"（已提炼出可用知识包）；
    - needs_organization（待整理）：原著已标准化可用，但还没提炼出写作知识；
    - needs_update（需更新）：素材本身需要复核/更新。
    """
    pur = (a.get("purification") or {}).get("status") or "未处理"
    know = (a.get("knowledge") or {}).get("status") or "未开始"
    if know == "可用":
        view = _bkp_acceptance_view(a)
        if view != "review" and view != "pending" and _knowledge_is_discoverable(a):
            return {"author_group": "usable", "state": "ready", "writing_callable": True, "attention_message": None}
        return {"author_group": "needs_attention", "state": "needs_attention", "writing_callable": False,
                "attention_message": "资料还需要检查，确认完成后才能用于写作。"}
    if pur == "可用":
        return {"author_group": "pending", "state": "pending_distill", "writing_callable": False, "attention_message": None}
    if pur in ("需复核", "失败", "不适用") or a.get("type") == "NEEDS_REVIEW":
        formats = _source_formats(a)
        unsupported = {"ZIP", "MOBI", "AZW3"}.intersection(formats)
        message = ("当前格式不能直接提纯，请先转换为 EPUB、TXT 或带文字层的 PDF。"
                   if unsupported else "资料需要检查后才能继续整理。")
        return {"author_group": "needs_attention", "state": "needs_attention", "writing_callable": False,
                "attention_message": message}
    return {"author_group": "pending", "state": "pending_prepare", "writing_callable": False, "attention_message": None}


def list_materials() -> dict[str, Any]:
    """只读读取 canonical ledger，返回作者可读投影。

    绝不调用模型 / Agent / SourcePrepare / BookDistill；只读，无任何写副作用。
    只暴露真实字段：id / name / type / author / tags / notes / purification /
    knowledge /（files 数量）+ 作者面分类（author_group / writing_callable /
    why / next_step）。不返回 SHA 明细等机器事实（UI 用不到）。
    """
    catalog, _, _ = _load_materialintake()
    ledger = _load_ledger(catalog)
    materials = []
    for a in ledger.get("assets", []):
        classified = _classify_author_group(a)
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


# ---------------------------------------------------------------------------
# 显式动作（只有作者明确点击才执行）
# ---------------------------------------------------------------------------

def refresh_materials() -> dict[str, Any]:
    """显式触发 MaterialIntake catalog refresh（确定性、无模型）。

    成功返回资产/文件/容器计数；失败（MISSING_REGISTERED_FILE / 校验失败）
    抛 MaterialsError，绝不半写（MaterialIntake 保证原 ledger 不变）。
    """
    request_id = audit.new_request_id()
    audit.AuditRecorder(request_id, "material_refresh")
    audit.append_event(request_id, audit.EVENT_SKILL_STARTED, "material_intake", details={"skill": "MaterialIntake"})
    catalog, _, _ = _load_materialintake()
    rc = catalog.refresh_and_render(get_repo_root(), check_only=False)
    if rc != 0:
        audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "material_intake", details={"skill": "MaterialIntake"})
        audit.finish_file(request_id, audit.STATUS_FAILED, error="素材状态刷新失败")
        raise MaterialsError("素材状态刷新失败，请检查素材目录是否完整。")
    audit.append_event(request_id, audit.EVENT_SKILL_COMPLETED, "material_intake", details={"skill": "MaterialIntake"})
    audit.finish_file(request_id, audit.STATUS_COMPLETED)
    ledger = _load_ledger(catalog)
    return {
        "assets": len(ledger.get("assets", [])),
        "files": sum(len(a.get("files", [])) for a in ledger.get("assets", [])),
        "containers": len(ledger.get("containers", [])),
        "message": "素材状态已刷新",
    }


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
    files = intake.scan_inbox(mat_dir, ledger)
    audit.append_event(request_id, audit.EVENT_SKILL_COMPLETED, "material_intake", details={"skill": "MaterialIntake", "files": len(files)})
    audit.finish_file(request_id, audit.STATUS_COMPLETED)
    return {"inbox": "00_待入库", "files": files}


def apply_material_intake(plan: dict[str, Any]) -> dict[str, Any]:
    """作者显式选择的入库决策：走 MaterialIntake 确定性 intake 事务。

    生产路径尊重 MaterialIntake 自身的 safety/precheck/writeback：
      1. post_action.precheck（git repo / main / clean / HEAD==origin）→ 失败 STOP_BEFORE_MOVE；
      2. intake.apply_plan（health check + 三份 metadata snapshot + move journal +
         rollback + ledger mutation + catalog settlement）；
      3. settlement 成功后 post_action.safe_commit_push（失败不回滚已完成 intake）。
    测试通过 monkeypatch post_action 函数 + temp root 绕过 git sync。
    """
    request_id = audit.new_request_id()
    audit.AuditRecorder(request_id, "material_intake")
    catalog, intake, post_action = _load_materialintake()
    root = get_repo_root()
    mat_dir = root / "01_原始素材"
    ledger_path = mat_dir / "素材资产.json"
    try:
        ledger = catalog.load_ledger(ledger_path)
    except (FileNotFoundError, RuntimeError) as exc:
        audit.finish_file(request_id, audit.STATUS_FAILED, error=str(exc))
        raise MaterialsError(str(exc)) from exc

    # 1) precheck（尊重 MaterialIntake 自身 safety；失败 → STOP，不开始 intake）
    ok, reason = post_action.precheck(root)
    if not ok:
        audit.finish_file(request_id, audit.STATUS_FAILED, error=f"前置检查未通过：{reason}")
        raise MaterialsError(f"素材入库前置检查未通过（{reason}），已停止，未做任何改动。")

    # 2) 确定性 intake 事务（绝不绕过其 transaction/rollback）
    audit.append_event(request_id, audit.EVENT_SKILL_STARTED, "material_intake", details={"skill": "MaterialIntake"})
    report = intake.apply_plan(plan, ledger, root)
    if not report.get("ok"):
        errors = "; ".join(report.get("errors") or ["素材入库失败"])
        audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "material_intake", details={"skill": "MaterialIntake"})
        audit.finish_file(request_id, audit.STATUS_FAILED, error=errors)
        raise MaterialsError(f"素材入库失败：{errors}")
    audit.append_event(
        request_id, audit.EVENT_SKILL_COMPLETED, "material_intake",
        details={"skill": "MaterialIntake", "new_ids": report.get("new_ids") or [], "attached": report.get("attached") or []},
    )

    # 3) 写回（git 失败不回滚已完成的 intake，仅作为 warning 返回）
    outcome = post_action.safe_commit_push(root, _INTAKE_ALLOWLIST, "chore: intake new materials")
    git_warning: str | None = None
    if outcome.startswith("STOP_"):
        git_warning = f"素材已入库，但同步到 Git 未完成（{outcome}），请手动处理。"
    audit.finish_file(
        request_id, audit.STATUS_COMPLETED if not git_warning else audit.STATUS_FAILED,
        error=git_warning,
    )

    return {
        "ok": True,
        "new_ids": report.get("new_ids") or [],
        "attached": report.get("attached") or [],
        "duplicates_removed": report.get("duplicates_removed") or [],
        "reviews": report.get("reviews") or [],
        "moves": report.get("moves") or [],
        "git_outcome": outcome,
        "git_warning": git_warning,
        "message": "素材入库已完成" if not git_warning else "素材入库已完成（Git 同步待处理）",
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
            "REFERENCE_WORK", "RESEARCH", "LOOSE_MATERIAL", "METHOD_SOURCE",
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
            file_types=("素材文件 (*.epub;*.txt;*.pdf;*.zip;*.mobi;*.azw3)", "所有文件 (*.*)"),
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
# 4.2 Agent 辅助入库（确定性事实优先；仅在无法定论时才调 Agent 一次）
# ---------------------------------------------------------------------------

_CLASSIFY_TASK_TEMPLATE = """你是 Go Write 的素材入库分类执行器。下面给出了 00_待入库 中每个文件的确定性事实，以及当前正式素材台账（canonical ledger）的摘要。请只对**仍需要分类**的文件做判断。

每个文件只能输出 MaterialIntake 允许的一种决策：
- NEW_ASSET：这是一个新素材（需给出 name 与 type）
- ATTACH_EXISTING：应并入已有素材（需给出 asset_id，且必须是下方台账中真实存在的 id）
- REVIEW：无法确定，需要人工确认（reason 说明原因）

规则：
- 绝不编造台账中不存在的 asset_id；
- 类型只允许 REFERENCE_WORK / RESEARCH / LOOSE_MATERIAL / METHOD_SOURCE；
  其中 METHOD_SOURCE = 主要目的是教授/解释写作、编剧、导演、剪辑、戏剧、表演、
  叙事技巧、读者体验等可迁移创作方法的非虚构资料（方法书/教程/讲义/访谈谈艺录等）；
  虚构参考作品一律 REFERENCE_WORK；拿不准宁可 REVIEW；
- 严禁移动文件、严禁修改台账 —— 你只输出决策，入库事务由 Go Write 执行。

台账素材：
{ledger_summary}

待分类文件：
{files_summary}

最终回复必须只有合法 JSON 对象，结构如下：
{{
  "items": [
    {{
      "filename": "文件原名",
      "action": "NEW_ASSET",
      "name": "素材名称",
      "type": "REFERENCE_WORK",
      "reason": "判断依据（可选）"
    }}
  ]
}}

未出现的文件不要输出。"""


def _ledger_summary(ledger: dict[str, Any]) -> str:
    assets = ledger.get("assets") or []
    if not assets:
        return "（当前台账无素材）"
    return "\n".join(
        f"- {a.get('id')}：{a.get('name')}（{a.get('type')}）" for a in assets
    )


def _files_summary(files: list[dict[str, Any]]) -> str:
    if not files:
        return "（无待分类文件）"
    return "\n".join(
        f"- {f.get('filename')}（sha256={f.get('sha256', '')[:12]}…，"
        f"类型={f.get('suffix') or '?'}）"
        for f in files
    )


def _parse_classify_output(
    output: str,
    scan_by_filename: dict[str, dict],
    ledger: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """解析分类 Agent 输出并逐项校验（只接受 MaterialIntake 允许的决策）。

    校验目标：扫描事实（文件必须真实存在）+ canonical ledger（ATTACH_EXISTING
    的 asset_id 必须真实存在）。Agent 绝不能绕过 MaterialIntake 决策面。
    """
    known_ids = {a.get("id") for a in (ledger or {}).get("assets", [])}
    text = (output or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise MaterialsError(f"分类 Agent 输出不是合法 JSON：{exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise MaterialsError("分类 Agent 输出缺少 items 列表。")
    decisions: list[dict[str, Any]] = []
    for item in data["items"]:
        if not isinstance(item, dict):
            raise MaterialsError("分类 Agent 输出项不是对象。")
        filename = str(item.get("filename") or "").strip()
        if not filename or filename not in scan_by_filename:
            raise MaterialsError(f"分类 Agent 输出了扫描中不存在的文件：{filename}")
        action = item.get("action")
        if action not in ("NEW_ASSET", "ATTACH_EXISTING", "REVIEW"):
            raise MaterialsError(f"{filename} 的决策非法（只允许 NEW_ASSET / ATTACH_EXISTING / REVIEW）。")
        decision = {"filename": filename, "action": action, "reason": str(item.get("reason") or "")}
        if action == "NEW_ASSET":
            name = str(item.get("name") or "").strip()
            mtype = item.get("type")
            if not name:
                raise MaterialsError(f"{filename}：NEW_ASSET 必须提供 name。")
            if mtype not in ("REFERENCE_WORK", "RESEARCH", "LOOSE_MATERIAL", "METHOD_SOURCE"):
                raise MaterialsError(f"{filename}：NEW_ASSET 类型非法。")
            decision["name"] = name
            decision["type"] = mtype
        elif action == "ATTACH_EXISTING":
            asset_id = str(item.get("asset_id") or "").strip()
            if not asset_id:
                raise MaterialsError(f"{filename}：ATTACH_EXISTING 必须提供 asset_id。")
            if asset_id not in known_ids:
                raise MaterialsError(f"{filename}：ATTACH_EXISTING 指向台账中不存在的素材 {asset_id}。")
            decision["asset_id"] = asset_id
        decisions.append(decision)
    return decisions


def classify_material_inbox() -> dict[str, Any]:
    """Agent 辅助入库：scan → 确定性事实 → 仅对无法定论文件调一次 Agent。

    - exact duplicate → ATTACH_EXISTING（确定性，不调 Agent）；
    - unsupported → REVIEW（确定性）；
    - 其余文件 → 一次 Agent 分类 turn（Direct 同步执行；Interactive 创建
      /gowrite 请求，由 get_material_classify_request 轮询）。
    Agent 输出只含允许决策，逐项校验后才组装 plan；入库仍走 MaterialIntake
    transactional apply（本函数绝不动文件/台账）。
    """
    catalog, intake, _ = _load_materialintake()
    mat_dir = get_repo_root() / "01_原始素材"
    ledger_path = mat_dir / "素材资产.json"
    ledger = None
    if ledger_path.exists():
        ledger = catalog.load_ledger(ledger_path)
    files = intake.scan_inbox(mat_dir, ledger)
    scan_by_filename = {f["filename"]: f for f in files}

    request_id = audit.new_request_id()
    audit.AuditRecorder(request_id, "material_classify")
    audit.append_event(request_id, audit.EVENT_SKILL_STARTED, "material_intake", details={"skill": "MaterialIntake"})

    # 确定性事实优先
    plan_items: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    for f in files:
        if f["unsupported"]:
            plan_items.append({"action": "REVIEW", "files": [f["filename"]], "reason": "不支持的类型，需人工确认"})
        elif f["exact_duplicate_matches"]:
            match = f["exact_duplicate_matches"][0]
            asset_id = match.split("(")[0] if "(" in match else match
            plan_items.append({"action": "ATTACH_EXISTING", "files": [f["filename"]], "asset_id": asset_id})
        else:
            ambiguous.append(f)
    audit.append_event(
        request_id, audit.EVENT_SKILL_COMPLETED, "material_intake",
        details={"skill": "MaterialIntake", "deterministic": len(plan_items), "ambiguous": len(ambiguous)},
    )

    agent_used = False
    if ambiguous:
        from operations import agent_runner as runner
        from config.settings import EXECUTION_MODE_DIRECT, SettingsStore
        settings = SettingsStore().load()
        if settings.default_execution_mode != EXECUTION_MODE_DIRECT:
            # Interactive：一次 /gowrite 分类 turn（同一请求生命周期）
            from operations import qoder_bridge as bridge
            from operations import execution_tasks as exec_tasks
            task = _CLASSIFY_TASK_TEMPLATE.format(
                ledger_summary=_ledger_summary(ledger or {}),
                files_summary=_files_summary(ambiguous),
            )
            try:
                bridge.create_request(
                    task=task,
                    kind="material_classify_propose",
                    meta={
                        "request_id": request_id,
                        "execution": {
                            "execution_mode": "interactive_bridge",
                            "agent_id": settings.interactive_agent,
                            "model": None,
                        },
                    },
                    request_id=request_id,
                    timeout_seconds=_CLASSIFY_TIMEOUT_SECONDS,
                    activate_for_gowrite=True,  # Interactive：显式激活 /gowrite
                )
            except bridge.BridgeBusyError as exc:
                # 已有等待 /gowrite 的交互任务：绝不清除/覆盖它
                audit.finish_file(request_id, audit.STATUS_FAILED, error=str(exc))
                raise MaterialsError(str(exc)) from exc
            audit.append_event(request_id, audit.EVENT_BRIDGE_WAITING, component="material_classify")
            return {
                "status": "pending",
                "request_id": request_id,
                "plan": {"items": plan_items},
                "ambiguous": [f["filename"] for f in ambiguous],
                "agent_required": True,
                "message": "等待 Qoder /gowrite：正在分类待入库素材",
            }
        # Direct：一次 Agent turn（同步；单个分类 turn 可接受）
        try:
            adapter, agent_request = runner._build_adapter()
        except Exception as exc:  # noqa: BLE001
            audit.finish_file(request_id, audit.STATUS_FAILED, error=str(exc))
            raise MaterialsError(f"分类执行配置不可用：{exc}") from exc
        task = _CLASSIFY_TASK_TEMPLATE.format(
            ledger_summary=_ledger_summary(ledger or {}),
            files_summary=_files_summary(ambiguous),
        )
        agent_request.task = task
        agent_request.cwd = str(get_repo_root())
        audit.append_event(
            request_id, audit.EVENT_AGENT_DIRECT_PROCESS_STARTED, "material_classify",
            details={"agent": adapter.name},
        )
        try:
            result = adapter.run(agent_request)
        except Exception as exc:  # noqa: BLE001
            audit.append_event(request_id, audit.EVENT_AGENT_FAILED, "material_classify", details={"error": str(exc)[:200]})
            audit.finish_file(request_id, audit.STATUS_FAILED, error=f"分类执行失败：{exc}")
            raise MaterialsError(f"分类执行失败：{exc}") from exc
        if result.status != "completed":
            audit.append_event(request_id, audit.EVENT_AGENT_FAILED, "material_classify", details={"error": (result.error or "")[:200]})
            audit.finish_file(request_id, audit.STATUS_FAILED, error=result.error or "分类未完成")
            raise MaterialsError(result.error or "分类未完成，请重试。")
        audit.append_event(request_id, audit.EVENT_AGENT_COMPLETED, "material_classify")
        try:
            decisions = _parse_classify_output(result.output, scan_by_filename, ledger)
        except MaterialsError as exc:
            audit.finish_file(request_id, audit.STATUS_FAILED, error=str(exc))
            raise
        agent_used = True
        for decision in decisions:
            plan_items.append({
                "action": decision["action"],
                "files": [decision["filename"]],
                **({"name": decision.get("name"), "type": decision.get("type")} if decision.get("action") == "NEW_ASSET" else {}),
                **({"asset_id": decision.get("asset_id")} if decision.get("action") == "ATTACH_EXISTING" else {}),
                **({"reason": decision.get("reason") or "Agent 判定"} if decision.get("action") == "REVIEW" else {}),
            })

    audit.finish_file(request_id, audit.STATUS_COMPLETED)
    return {
        "status": "ready",
        "plan": {"items": plan_items},
        "ambiguous": [f["filename"] for f in ambiguous],
        "agent_required": bool(ambiguous),
        "agent_used": agent_used,
        "message": "入库建议已生成（需你确认后才会执行）" if plan_items else "没有需要入库的文件",
    }


def get_material_classify_request(request_id: str) -> dict[str, Any]:
    """轮询交互式分类结果：pending / completed（含 plan）/ failed / canceled。"""
    from operations import qoder_bridge as bridge
    request_id = (request_id or "").strip()
    if not request_id:
        raise MaterialsError("缺少任务标识（request_id）。")
    request = bridge.get_request(request_id)
    if request is None:
        audit.finish_file(request_id, audit.STATUS_FAILED, error="任务已失效，请重新发起。")
        return {"request_id": request_id, "status": "failed", "error": "任务已失效，请重新发起。"}
    state = request.get("state")
    if state == "canceled":
        bridge.cleanup_request(request_id)
        audit.finish_file(request_id, audit.STATUS_CANCELED)
        return {"request_id": request_id, "status": "canceled"}
    if state == "failed":
        bridge.cleanup_request(request_id)
        audit.finish_file(request_id, audit.STATUS_FAILED, error=request.get("error") or "分类失败")
        return {"request_id": request_id, "status": "failed", "error": request.get("error") or "分类失败"}
    if bridge.is_expired(request):
        bridge.cleanup_request(request_id)
        audit.finish_file(request_id, audit.STATUS_FAILED, error="任务已超时")
        return {"request_id": request_id, "status": "expired", "error": "任务已超时，请重新发起。"}
    response = bridge.read_response(request_id)
    if response is None:
        return {"request_id": request_id, "status": "pending", "message": "等待 Qoder /gowrite：正在分类待入库素材"}
    if response.get("request_id") != request_id:
        bridge.cleanup_request(request_id)
        return {"request_id": request_id, "status": "failed", "error": "返回结果与任务不匹配，已丢弃。"}
    audit.append_event(request_id, audit.EVENT_BRIDGE_RESPONSE_RECEIVED, "material_classify")
    if response.get("status") != "completed":
        error = response.get("error") or "分类结果无效"
        bridge.cleanup_request(request_id)
        audit.finish_file(request_id, audit.STATUS_FAILED, error=error)
        return {"request_id": request_id, "status": "failed", "error": error}
    # 结构化 result 优先；纯文本 output 兜底（output 为对象等畸形信封已被桥拒绝）
    try:
        output = bridge.response_result_text(response)
    except bridge.BridgeProtocolError as exc:
        error = f"分类结果无效：{exc}"
        bridge.cleanup_request(request_id)
        audit.finish_file(request_id, audit.STATUS_FAILED, error=error)
        return {"request_id": request_id, "status": "failed", "error": error}
    catalog, intake, _ = _load_materialintake()
    mat_dir = get_repo_root() / "01_原始素材"
    ledger_path = mat_dir / "素材资产.json"
    ledger = None
    if ledger_path.exists():
        ledger = catalog.load_ledger(ledger_path)
    scan_by_filename = {f["filename"]: f for f in intake.scan_inbox(mat_dir, ledger)}
    try:
        decisions = _parse_classify_output(output, scan_by_filename, ledger)
    except MaterialsError as exc:
        bridge.cleanup_request(request_id)
        audit.finish_file(request_id, audit.STATUS_FAILED, error=str(exc))
        return {"request_id": request_id, "status": "failed", "error": str(exc)}
    plan_items = []
    for decision in decisions:
        plan_items.append({
            "action": decision["action"],
            "files": [decision["filename"]],
            **({"name": decision.get("name"), "type": decision.get("type")} if decision.get("action") == "NEW_ASSET" else {}),
            **({"asset_id": decision.get("asset_id")} if decision.get("action") == "ATTACH_EXISTING" else {}),
            **({"reason": decision.get("reason") or "Agent 判定"} if decision.get("action") == "REVIEW" else {}),
        })
    bridge.cleanup_request(request_id)
    audit.finish_file(request_id, audit.STATUS_COMPLETED)
    return {
        "request_id": request_id,
        "status": "completed",
        "plan": {"items": plan_items},
        "message": "入库建议已生成（需你确认后才会执行）",
    }


def cancel_material_classify_request(request_id: str) -> dict[str, Any]:
    from operations import qoder_bridge as bridge
    request_id = (request_id or "").strip()
    if not request_id:
        raise MaterialsError("缺少任务标识（request_id）。")
    request = bridge.get_request(request_id)
    if request is not None:
        bridge.mark_canceled(request_id)
        bridge.clear_active_if(request_id)
        audit.finish_file(request_id, audit.STATUS_CANCELED)
    bridge.cleanup_request(request_id)
    return {"request_id": request_id, "status": "canceled"}


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
        raise MaterialsError("零散素材不适用提纯（SourcePrepare）。")
    if mtype == "NEEDS_REVIEW":
        raise MaterialsError("该素材待人工确认，暂不能提纯。")
    if mtype == "METHOD_SOURCE":
        raise MaterialsError("方法/技巧资料请走通用入口（后端会自动改用 MethodPrepare）。")

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
    ]
    audit.append_event(
        request_id, audit.EVENT_AGENT_DIRECT_PROCESS_STARTED, "source_prepare",
        details={"asset_id": asset_id, "command": "source_prepare.py --book " + asset_id},
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
        audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "source_prepare", details={"skill": "SourcePrepare"})
        audit.finish_file(request_id, audit.STATUS_FAILED, error=(proc.stderr or proc.stdout or "")[:400])
        raise MaterialsError(f"提纯失败（SourcePrepare 退出码 {proc.returncode}）。\n{(proc.stderr or proc.stdout or '')[:600]}")
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

_DISTILL_TASK_TEMPLATE = """你是 Go Write 的原著蒸馏执行器（BookDistill Base Scan + 收敛阶段）。

输入：
- SourcePrepare PASS 包：{sp_dir}
- 蒸馏输出目录：{bd_dir}
（validate 与 prepare 已由 Go Write 完成，模板已生成。）

你的任务（按顺序）：
1. 逐章阅读 {sp_dir}/chapters/ 下的正文章节（NNNN.md；0000_*.md 是卷首，不蒸馏）。
2. 在 {bd_dir}/evidence/ch_NNNN.md 中填写 MAP 与 FACT / INFERENCE / OBSERVATION /
   MECHANISM / BOUNDARY 条目：每条必须带原文引用（chapters/NNNN.md#L起-L止），
   置信度 高/中/低；一条结论一句话 + 行号引用，不大量复制原文。
3. 完成至少两个互补观察 Pass：长篇运行/读者动力 与 Reader/Page Craft。
4. 跨章收敛：从充分支撑的 Observation / MECHANISM 中合并同质、降级单章小技巧，
   产出 {bd_dir}/mechanisms.md（10–20 条高价值可迁移机制，附反证/边界）。
5. 生成 {bd_dir}/evidence.md（精选支撑最终结论的证据）与 {bd_dir}/model.md
   （作者第一阅读入口）。
6. 完成 {bd_dir}/bd_report.md：来源身份 + 覆盖范围与置信度 + 边界与不确定性。
7. 运行 BookDistill 的 assemble 与 profile 命令后，依据 {bd_dir}/book_profile.md、全部
   evidence、model.md、mechanisms.md 和 BKP_protocol.md，创建完整 {bd_dir}/bkp_prototype/：
   identity.json、README.md、profile.md、work_map.md、author_view.md、knowledge/cards.md 以及
   协议要求的 curated 文件。cards 必须是可追溯的 canonical 知识卡，author_view 必须是可读投影。
8. 在 {bd_dir}/BKP_ACCEPTANCE_REPORT.md 写入全书综合验收报告，必须含
   BKP_protocol.md §5 所要求的 acceptance_data JSON 块。只针对当前冻结来源范围下结论；
   连载、节选或未完结不是 blocking gap，不能假称尚未出现的终局或完整人物弧。

纪律：
- 原著始终是最高事实源；不经过二手摘要逐层压缩；
- coverage 不是价值判断；发现阶段可以宽，BKP 必须克制；
- 不做原作者风格模仿器；不随意外推；反证与边界不省略。

全部写入完成后，在最终回复中输出一行 JSON：{{"status": "completed", "evidence_files": <填写数量>, "mechanisms_count": <填写数量>}}
不要修改 {sp_dir} 中的任何文件。"""


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
        raise MaterialsError("BKP 身份文件缺失，无法完成蒸馏。") from exc
    identity["acceptance"] = {
        "schema": "gowrite_bkp_acceptance/v1", "required": True, "status": "PENDING",
        "report": "BKP_ACCEPTANCE_REPORT.md",
    }
    identity["bkp_protocol_version"] = "0.3"
    identity_path.write_text(json.dumps(identity, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _run_reference_acceptance(request_id: str, asset: dict[str, Any], bd_dir: Path) -> None:
    """验收与统一 loader discovery 是原著蒸馏的完成门，不是作者动作。"""
    _mark_reference_acceptance_pending(bd_dir)
    if not _ACCEPTANCE_GATE_SCRIPT.is_file():
        raise MaterialsError("原著学习检查工具缺失。")
    try:
        proc = subprocess.run(
            [sys.executable, str(_ACCEPTANCE_GATE_SCRIPT), str(bd_dir), "--repo-root", str(get_repo_root()), "--write-identity"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10 * 60,
        )
    except subprocess.TimeoutExpired as exc:
        raise MaterialsError("原著学习检查超时，请重试。") from exc
    if proc.returncode != 0:
        raise MaterialsError("原著学习检查未通过，请检查蒸馏结果。")
    if not _knowledge_is_discoverable(asset):
        raise MaterialsError("原著学习结果暂不能用于写作，请检查资料状态。")


def _finalize_reference_distill(request_id: str, asset: dict[str, Any], sp_dir: Path, bd_dir: Path) -> None:
    """重新执行所有确定性边界；Agent 输出从不直接构成完成信任。"""
    for sub_args, label in (
        (["assemble", "--input", str(sp_dir), "--output", str(bd_dir)], "蒸馏校验"),
        (["profile", "--output", str(bd_dir)], "资料整理"),
        (["bkp", "--output", str(bd_dir)], "学习资料整理"),
    ):
        try:
            proc = _run_bd_cli(sub_args, request_id)
        except subprocess.TimeoutExpired as exc:
            raise MaterialsError(f"{label}超时，请重试。") from exc
        if proc.returncode != 0:
            raise MaterialsError(f"{label}失败。")
    _run_reference_acceptance(request_id, asset, bd_dir)


def run_book_distill(asset_id: str) -> dict[str, Any]:
    """对 SourcePrepare PASS 素材显式运行真实 BookDistill。

    阶段：validate（确定性）→ prepare（确定性）→ Agent 阅读/收敛 turn
    （持久化 Settings 路由；Direct 同步 / Interactive /gowrite）→ assemble +
    profile + bkp（确定性 finalize）→ 素材状态刷新（knowledge=可用 只可能来自
    FINALIZED BKP 证据）。
    """
    asset_id = (asset_id or "").strip()
    if not asset_id:
        raise MaterialsError("缺少素材标识（asset_id）。")
    asset = _ledger_asset(asset_id)
    if asset.get("type") == "LOOSE_MATERIAL":
        raise MaterialsError("零散素材不适用蒸馏（BookDistill）。")
    if asset.get("type") == "METHOD_SOURCE":
        raise MaterialsError("方法/技巧资料请走通用入口（后端会自动改用 MethodDistill）。")

    request_id = audit.new_request_id()
    audit.AuditRecorder(request_id, "book_distill")
    audit.append_event(request_id, audit.EVENT_SKILL_STARTED, "book_distill", details={"skill": "BookDistill", "asset_id": asset_id})

    # 1) 定位 SP PASS 包
    sp_dir = _find_sp_dir(asset_id, asset.get("name") or "")
    try:
        proc = _run_bd_cli(["validate", "--input", str(sp_dir)], request_id)
    except subprocess.TimeoutExpired:
        audit.finish_file(request_id, audit.STATUS_FAILED, error="蒸馏校验超时")
        raise MaterialsError("蒸馏校验超时，请重试。")
    if proc.returncode != 0:
        audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "book_distill", details={"skill": "BookDistill"})
        audit.finish_file(request_id, audit.STATUS_FAILED, error="SourcePrepare 输入未通过蒸馏校验")
        raise MaterialsError(f"SourcePrepare 输入未通过 BookDistill 校验（请先确认提纯为 PASS）。\n{(proc.stderr or proc.stdout or '')[:400]}")

    # 2) prepare（确定性脚手架）
    bd_dir = get_repo_root() / "02_素材知识库" / sp_dir.name
    if not bd_dir.exists():
        bd_dir.mkdir(parents=True)
    try:
        proc = _run_bd_cli(["prepare", "--input", str(sp_dir), "--output", str(bd_dir)], request_id)
    except subprocess.TimeoutExpired:
        audit.finish_file(request_id, audit.STATUS_FAILED, error="蒸馏准备超时")
        raise MaterialsError("蒸馏准备超时，请重试。")
    if proc.returncode != 0:
        audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "book_distill", details={"skill": "BookDistill"})
        audit.finish_file(request_id, audit.STATUS_FAILED, error="蒸馏准备失败")
        raise MaterialsError(f"蒸馏准备失败。\n{(proc.stderr or proc.stdout or '')[:400]}")

    # 3) Agent 阅读/收敛 turn（持久化 Settings 路由）
    try:
        _run_distill_agent_stage(request_id, asset_id, sp_dir, bd_dir)
    except _PendingDistill as pending:
        return {
            "asset_id": asset_id,
            "status": "pending",
            "request_id": pending.request_id,
            "message": "等待 Qoder /gowrite：正在蒸馏（Base Scan + 收敛），完成后将自动封装 BKP",
        }

    # 4) 确定性完成门：BKP → acceptance PASS → KnowledgeRetrieve discovery。
    try:
        _finalize_reference_distill(request_id, asset, sp_dir, bd_dir)
    except MaterialsError as exc:
        audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "book_distill", details={"skill": "BookDistill"})
        audit.finish_file(request_id, audit.STATUS_FAILED, error=str(exc))
        raise

    # 5) 刷新素材状态（knowledge 只可能由 FINALIZED BKP 证据推导为可用）
    catalog, _, _ = _load_materialintake()
    rc = catalog.refresh_and_render(get_repo_root(), check_only=False)
    if rc != 0:
        audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "book_distill", details={"skill": "BookDistill"})
        audit.finish_file(request_id, audit.STATUS_FAILED, error="素材状态刷新失败")
        raise MaterialsError("蒸馏完成，但素材状态刷新失败，请手动刷新素材页。")
    audit.append_event(request_id, audit.EVENT_SKILL_COMPLETED, "book_distill", details={"skill": "BookDistill", "asset_id": asset_id})
    audit.finish_file(request_id, audit.STATUS_COMPLETED)
    return {
        "asset_id": asset_id,
        "status": "completed",
        "output_dir": str(bd_dir),
        "message": "蒸馏完成（已生成 BKP 知识包并刷新素材状态）",
    }


def _run_distill_agent_stage(request_id: str, asset_id: str, sp_dir: Path, bd_dir: Path) -> None:
    """蒸馏的 Agent 阅读/收敛阶段：走持久化 Settings 执行路由（一次 turn）。

    - Direct：adapter 同步执行（长任务可接受；这是显式离线处理操作）；
    - Interactive：创建 /gowrite 请求，由 get_book_distill_request 轮询后接续
      assemble/profile/bkp。
    本函数只负责 Direct 与 Interactive 请求创建；Interactive 的 finalize 由
    get_book_distill_request 调用 _finalize_distill 完成。
    """
    from config.settings import EXECUTION_MODE_DIRECT, SettingsStore
    settings = SettingsStore().load()
    task = _DISTILL_TASK_TEMPLATE.format(sp_dir=str(sp_dir), bd_dir=str(bd_dir))

    if settings.default_execution_mode != EXECUTION_MODE_DIRECT:
        from operations import qoder_bridge as bridge
        try:
            bridge.create_request(
                task=task,
                kind="book_distill_propose",
                meta={
                    "request_id": request_id,
                    "asset_id": asset_id,
                    "sp_dir": str(sp_dir),
                    "bd_dir": str(bd_dir),
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
        raise MaterialsError(f"蒸馏执行配置不可用：{exc}") from exc
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
        raise MaterialsError(f"蒸馏执行失败：{exc}") from exc
    if result.status != "completed":
        audit.append_event(request_id, audit.EVENT_AGENT_FAILED, "book_distill", details={"error": (result.error or "")[:200]})
        audit.finish_file(request_id, audit.STATUS_FAILED, error=result.error or "蒸馏未完成")
        raise MaterialsError(result.error or "蒸馏未完成，请重试。")
    audit.append_event(request_id, audit.EVENT_AGENT_COMPLETED, "book_distill")


class _PendingDistill(Exception):
    """Interactive 蒸馏等待第二次 /gowrite（内部控制流）。"""

    def __init__(self, request_id: str) -> None:
        super().__init__(request_id)
        self.request_id = request_id


def _finalize_distill(request_id: str, asset_id: str, sp_dir: Path, bd_dir: Path) -> dict[str, Any]:
    """Interactive 蒸馏的确定性完成门；与 Direct 路径严格一致。"""
    from operations import qoder_bridge as bridge
    try:
        _finalize_reference_distill(request_id, _ledger_asset(asset_id), sp_dir, bd_dir)
    except MaterialsError as exc:
        audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "book_distill", details={"skill": "BookDistill"})
        audit.finish_file(request_id, audit.STATUS_FAILED, error=str(exc))
        bridge.cleanup_request(request_id)
        raise
    catalog, _, _ = _load_materialintake()
    rc = catalog.refresh_and_render(get_repo_root(), check_only=False)
    bridge.cleanup_request(request_id)
    if rc != 0:
        audit.finish_file(request_id, audit.STATUS_FAILED, error="素材状态刷新失败")
        raise MaterialsError("蒸馏完成，但素材状态刷新失败，请手动刷新素材页。")
    audit.append_event(request_id, audit.EVENT_SKILL_COMPLETED, "book_distill", details={"skill": "BookDistill"})
    audit.finish_file(request_id, audit.STATUS_COMPLETED)
    return {
        "asset_id": None,
        "status": "completed",
        "output_dir": str(bd_dir),
        "message": "蒸馏完成（已生成 BKP 知识包并刷新素材状态）",
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
        return {"request_id": request_id, "status": "pending", "message": "等待 Qoder /gowrite：正在蒸馏（Base Scan + 收敛），完成后将自动封装 BKP"}
    if response.get("request_id") != request_id:
        bridge.cleanup_request(request_id)
        return {"request_id": request_id, "status": "failed", "error": "返回结果与任务不匹配，已丢弃。"}
    if response.get("status") != "completed":
        error = response.get("error") or "蒸馏执行失败"
        bridge.cleanup_request(request_id)
        audit.finish_file(request_id, audit.STATUS_FAILED, error=error)
        return {"request_id": request_id, "status": "failed", "error": error}
    audit.append_event(request_id, audit.EVENT_BRIDGE_RESPONSE_RECEIVED, "book_distill")
    asset_id = meta.get("asset_id")
    if not isinstance(asset_id, str) or not asset_id.strip():
        bridge.cleanup_request(request_id)
        audit.finish_file(request_id, audit.STATUS_FAILED, error="蒸馏任务缺少素材标识")
        return {"request_id": request_id, "status": "failed", "error": "蒸馏任务缺少素材标识，请重新发起。"}
    try:
        result = _finalize_distill(
            request_id, asset_id.strip(), Path(meta["sp_dir"]), Path(meta["bd_dir"]),
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
        bridge.clear_active_if(request_id)
        audit.finish_file(request_id, audit.STATUS_CANCELED)
    bridge.cleanup_request(request_id)
    return {"request_id": request_id, "status": "canceled"}


# ---------------------------------------------------------------------------
# 4.6 MethodPrepare 显式提纯（方法/技巧资料；确定性，无模型）
# ---------------------------------------------------------------------------

_MP_SCRIPT = _REPO_ROOT / "05_Skills与自动化" / "01_Skills" / "MethodPrepare" / "scripts" / "method_prepare.py"
_MD_SCRIPT = _REPO_ROOT / "05_Skills与自动化" / "01_Skills" / "MethodDistill" / "method_distill.py"


def _post_settlement_sync(request_id: str, allowlist: list[str], message: str,
                          component: str) -> tuple[str, str | None]:
    """settlement 成功后的安全 Git 同步（复用 MaterialIntake post_action）。

    Git 失败不回滚已完成的业务动作，仅作为 warning 返回。
    """
    _, _, post_action = _load_materialintake()
    root = get_repo_root()
    try:
        outcome = post_action.safe_commit_push(root, allowlist, message)
    except Exception as exc:  # noqa: BLE001 — git helper 异常同样不阻断业务
        outcome = f"STOP_POST_ACTION_ERROR:{exc}"
    if outcome.startswith("STOP_"):
        audit.append_event(
            request_id, audit.EVENT_SKILL_FAILED, component,
            details={"git_outcome": outcome},
        )
        return outcome, f"知识包已结算，但同步到 Git 未完成（{outcome}），请手动处理。"
    return outcome, None


def _refresh_catalog_or_fail(request_id: str, component: str) -> None:
    """结算后刷新素材状态；失败抛稳定错误（不阻断已完成的产物）。"""
    catalog, _, _ = _load_materialintake()
    rc = catalog.refresh_and_render(get_repo_root(), check_only=False)
    if rc != 0:
        audit.append_event(request_id, audit.EVENT_SKILL_FAILED, component, details={"step": "catalog_refresh"})
        raise MaterialsError("处理完成，但素材状态刷新失败，请手动刷新素材页。")


def run_method_prepare(asset_id: str) -> dict[str, Any]:
    """对 METHOD_SOURCE 素材显式运行 MethodPrepare（确定性、无模型）。

    输出落 06_工作区/MethodPrepare/<asset_id>_<名称>/（Local Only，不进 Git）；
    成功后刷新三份 material state files 并经 post_action 安全同步。
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
        audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "method_prepare", details={"skill": "MethodPrepare"})
        audit.finish_file(request_id, audit.STATUS_FAILED, error=(proc.stderr or proc.stdout or "")[:400])
        raise MaterialsError(f"方法提纯失败。\n{(proc.stderr or proc.stdout or '')[:600]}")

    # settlement：刷新三份 material state files → post_action 安全同步（仅三份文件）
    _refresh_catalog_or_fail(request_id, "method_prepare")
    _, _, post_action = _load_materialintake()
    try:
        ok, reason = post_action.precheck(get_repo_root())
    except Exception:  # noqa: BLE001
        ok, reason = False, "POST_ACTION_ERROR"
    if ok:
        outcome, git_warning = _post_settlement_sync(
            request_id, _INTAKE_ALLOWLIST, "chore: method prepare settlement", "method_prepare")
    else:
        outcome, git_warning = f"SKIP_PRECHECK:{reason}", None
    audit.append_event(request_id, audit.EVENT_SKILL_COMPLETED, "method_prepare",
                       details={"skill": "MethodPrepare", "asset_id": asset_id, "git_outcome": outcome})
    audit.finish_file(request_id, audit.STATUS_COMPLETED if not git_warning else audit.STATUS_FAILED,
                      error=git_warning)
    return {
        "asset_id": asset_id,
        "status": "completed",
        "git_outcome": outcome,
        "git_warning": git_warning,
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
    → knowledge 可用 → post_action 只提交当前资产的 method/ 子树 + 三份文件。
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

    # 1) 定位 MethodPrepare PASS 包并 validate
    mp_dir = _find_mp_dir(asset_id)
    try:
        proc = _run_md_cli(["validate", "--input", str(mp_dir)], request_id)
    except subprocess.TimeoutExpired:
        audit.finish_file(request_id, audit.STATUS_FAILED, error="方法蒸馏校验超时")
        raise MaterialsError("方法蒸馏校验超时，请重试。")
    if proc.returncode != 0:
        audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "method_distill", details={"skill": "MethodDistill"})
        audit.finish_file(request_id, audit.STATUS_FAILED, error="MethodPrepare 输入未通过蒸馏校验")
        raise MaterialsError(f"MethodPrepare 输入未通过 MethodDistill 校验（请先确认提纯为 PASS）。\n{(proc.stderr or proc.stdout or '')[:400]}")

    # 2) prepare（确定性脚手架；与 SP→BD 同名目录约定：<asset_id>_<名称>/method）
    method_dir = get_repo_root() / "02_素材知识库" / mp_dir.name / "method"
    try:
        proc = _run_md_cli(["prepare", "--input", str(mp_dir), "--output", str(method_dir)], request_id)
    except subprocess.TimeoutExpired:
        audit.finish_file(request_id, audit.STATUS_FAILED, error="方法蒸馏准备超时")
        raise MaterialsError("方法蒸馏准备超时，请重试。")
    if proc.returncode != 0:
        audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "method_distill", details={"skill": "MethodDistill"})
        audit.finish_file(request_id, audit.STATUS_FAILED, error="方法蒸馏准备失败")
        raise MaterialsError(f"方法蒸馏准备失败。\n{(proc.stderr or proc.stdout or '')[:400]}")

    # 3) Agent 语义抽取 turn（持久化 Settings 路由）
    try:
        _run_method_distill_agent_stage(request_id, asset_id, mp_dir, method_dir)
    except _PendingMethodDistill as pending:
        return {
            "asset_id": asset_id,
            "status": "pending",
            "request_id": pending.request_id,
            "message": "等待 Qoder /gowrite：正在蒸馏方法知识，完成后将自动定稿",
        }

    # 4) 确定性 finalize + settlement
    return _finalize_method_distill(request_id, asset_id, mp_dir, method_dir)


def _finalize_method_distill(request_id: str, asset_id: str,
                             mp_dir: Path, method_dir: Path) -> dict[str, Any]:
    """确定性 finalize：定稿校验 → 素材状态刷新 → post_action 安全同步。"""
    from operations import qoder_bridge as bridge
    try:
        proc = _run_md_cli(["finalize", "--input", str(mp_dir), "--output", str(method_dir)], request_id)
    except subprocess.TimeoutExpired:
        audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "method_distill", details={"skill": "MethodDistill"})
        audit.finish_file(request_id, audit.STATUS_FAILED, error="方法知识定稿超时")
        bridge.cleanup_request(request_id)
        raise MaterialsError("方法知识定稿超时，请重试。")
    if proc.returncode != 0:
        audit.append_event(request_id, audit.EVENT_SKILL_FAILED, "method_distill", details={"skill": "MethodDistill"})
        audit.finish_file(request_id, audit.STATUS_FAILED, error="方法知识定稿失败")
        bridge.cleanup_request(request_id)
        raise MaterialsError(f"方法知识定稿失败。\n{(proc.stderr or proc.stdout or '')[:400]}")

    _refresh_catalog_or_fail(request_id, "method_distill")
    # MethodDistill 只提交当前资产的 method/ 子树 + 三份 material state files
    method_rel = method_dir.relative_to(get_repo_root()).as_posix()
    allowlist = list(_INTAKE_ALLOWLIST) + [method_rel]
    _, git_warning = _post_settlement_sync(
        request_id, allowlist, f"feat: finalize method knowledge for {asset_id}", "method_distill")
    bridge.cleanup_request(request_id)
    audit.append_event(request_id, audit.EVENT_SKILL_COMPLETED, "method_distill",
                       details={"skill": "MethodDistill", "asset_id": asset_id})
    audit.finish_file(request_id, audit.STATUS_COMPLETED if not git_warning else audit.STATUS_FAILED,
                      error=git_warning)
    return {
        "asset_id": asset_id,
        "status": "completed",
        "output_dir": str(method_dir),
        "git_warning": git_warning,
        "message": "方法知识蒸馏完成（已定稿并可被知识检索调用）",
    }


class _PendingMethodDistill(Exception):
    """Interactive 方法蒸馏等待 /gowrite（内部控制流）。"""

    def __init__(self, request_id: str) -> None:
        super().__init__(request_id)
        self.request_id = request_id


def _run_method_distill_agent_stage(request_id: str, asset_id: str,
                                    mp_dir: Path, method_dir: Path) -> None:
    """方法蒸馏 Agent 抽取阶段：复用持久化 Settings 执行路由（一次 turn）。"""
    from config.settings import EXECUTION_MODE_DIRECT, SettingsStore
    settings = SettingsStore().load()
    task = _METHOD_DISTILL_TASK_TEMPLATE.format(mp_dir=str(mp_dir), method_dir=str(method_dir))

    if settings.default_execution_mode != EXECUTION_MODE_DIRECT:
        from operations import qoder_bridge as bridge
        try:
            bridge.create_request(
                task=task,
                kind="method_distill_propose",
                meta={
                    "request_id": request_id,
                    "asset_id": asset_id,
                    "mp_dir": str(mp_dir),
                    "method_dir": str(method_dir),
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
        raise MaterialsError(f"方法蒸馏执行配置不可用：{exc}") from exc
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
        raise MaterialsError(f"方法蒸馏执行失败：{exc}") from exc
    if result.status != "completed":
        audit.append_event(request_id, audit.EVENT_AGENT_FAILED, "method_distill", details={"error": (result.error or "")[:200]})
        audit.finish_file(request_id, audit.STATUS_FAILED, error=result.error or "方法蒸馏未完成")
        raise MaterialsError(result.error or "方法蒸馏未完成，请重试。")
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
        return {"request_id": request_id, "status": "pending",
                "message": "等待 Qoder /gowrite：正在蒸馏方法知识，完成后将自动定稿"}
    if response.get("request_id") != request_id:
        bridge.cleanup_request(request_id)
        return {"request_id": request_id, "status": "failed", "error": "返回结果与任务不匹配，已丢弃。"}
    if response.get("status") != "completed":
        error = response.get("error") or "方法蒸馏执行失败"
        bridge.cleanup_request(request_id)
        audit.finish_file(request_id, audit.STATUS_FAILED, error=error)
        return {"request_id": request_id, "status": "failed", "error": error}
    audit.append_event(request_id, audit.EVENT_BRIDGE_RESPONSE_RECEIVED, "method_distill")
    try:
        result = _finalize_method_distill(
            request_id, str(meta.get("asset_id") or ""),
            Path(meta["mp_dir"]), Path(meta["method_dir"]),
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
        bridge.clear_active_if(request_id)
        audit.finish_file(request_id, audit.STATUS_CANCELED)
    bridge.cleanup_request(request_id)
    return {"request_id": request_id, "status": "canceled"}


# ---------------------------------------------------------------------------
# 4.8 作者面通用入口：prepare_material / distill_material（后端按类型分派）
# ---------------------------------------------------------------------------

def prepare_material(asset_id: str) -> dict[str, Any]:
    """作者面「提纯」：UI 只传素材 id，后端按 canonical 类型分派。

    REFERENCE_WORK / RESEARCH → SourcePrepare；METHOD_SOURCE → MethodPrepare；
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
    asset = _ledger_asset((asset_id or "").strip())
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
# 素材详情语义（写作时能否调用 + 当前阶段 + 下一步；页面加载零模型）
# ---------------------------------------------------------------------------

def get_material_detail(asset_id: str) -> dict[str, Any]:
    """单素材作者详情：只投影既有知识，不泄露后台阶段。"""
    asset = _ledger_asset(asset_id)
    classified = _classify_author_group(asset)
    summary, sections = _learning_projection(asset) if classified["state"] == "ready" else (None, [])
    labels = {
        "pending_prepare": "待提纯", "pending_distill": "待蒸馏",
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
        "writing_callable": classified["writing_callable"],
        "attention_message": classified.get("attention_message"),
        "learning_summary": summary,
        "learning_sections": sections,
    }
