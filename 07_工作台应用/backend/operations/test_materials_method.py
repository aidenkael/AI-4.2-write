# -*- coding: utf-8 -*-
"""METHOD_SOURCE 作者面操作测试：通用提纯/蒸馏入口的类型分派 + writing_callable 投影。

覆盖验收：
  - prepare_material / distill_material 只收素材 id，后端按 canonical 类型分派：
    REFERENCE_WORK → SourcePrepare/BookDistill；METHOD_SOURCE → MethodPrepare/MethodDistill；
  - 其他类型保守拒绝（不静默跑不匹配的处理器）；
  - 定稿方法知识包 → 素材列表投影 writing_callable=true（author_group=usable）。
"""
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from operations import materials  # noqa: E402
from operations import material_settlement  # noqa: E402


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    root = tmp_path / "root"
    (root / "01_原始素材").mkdir(parents=True)
    monkeypatch.setattr(materials, "get_repo_root", lambda: root)
    return root


def _asset(asset_id, asset_type, pur="未处理", know="未开始"):
    role_dir = "02_技巧类" if asset_type == "METHOD_SOURCE" else (
        "03_其他" if asset_type == "LOOSE_MATERIAL" else "01_原著")
    return {
        "id": asset_id, "name": f"素材{asset_id}", "type": asset_type,
        "author": "", "tags": [], "notes": "",
        "files": [{"path": f"{role_dir}/{asset_id}/x.txt", "sha256": "c" * 64, "primary": True}],
        "purification": {"status": pur, "evidence": None},
        "knowledge": {"status": know},
    }


def _write_method_source(root, asset_id, name=None):
    """在磁盘创建 METHOD_SOURCE 真实来源文件（§7 需要真实磁盘状态）。"""
    name = name or f"素材{asset_id}"
    src = root / "01_原始素材" / "02_技巧类" / asset_id / "x.txt"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(b"method-source")
    return src


def _write_mp_package(root, asset_id, name=None, sha="c" * 64, status="PASS", with_md=True):
    """创建真实 06 MethodPrepare PASS 包（full.md + sections/ + metadata.json）。"""
    name = name or f"素材{asset_id}"
    mp = root / "06_工作区" / "MethodPrepare" / f"{asset_id}_{name}"
    (mp / "sections").mkdir(parents=True, exist_ok=True)
    if with_md:
        (mp / "full.md").write_text("# full\n", encoding="utf-8")
    (mp / "metadata.json").write_text(json.dumps({
        "asset_id": asset_id, "status": status,
        "selected_source": {"format": ".txt", "sha256": sha},
    }, ensure_ascii=False), encoding="utf-8")
    return mp


def _write_ledger(root, assets):
    (root / "01_原始素材" / "素材资产.json").write_text(json.dumps(
        {"schema_version": "1.0", "assets": assets, "containers": []}, ensure_ascii=False),
        encoding="utf-8")


# ---------- 通用入口按类型分派 ----------

def test_prepare_material_dispatches_by_type(isolated, monkeypatch):
    _write_ledger(isolated, [_asset("book_0001", "REFERENCE_WORK"),
                             _asset("book_9101", "METHOD_SOURCE")])
    calls = []
    monkeypatch.setattr(materials, "run_source_prepare", lambda aid: calls.append(("sp", aid)) or {"ok": True})
    monkeypatch.setattr(materials, "run_method_prepare", lambda aid: calls.append(("mp", aid)) or {"ok": True})

    materials.prepare_material("book_0001")
    materials.prepare_material("book_9101")
    assert calls == [("sp", "book_0001"), ("mp", "book_9101")]


def test_distill_material_dispatches_by_type(isolated, monkeypatch):
    _write_ledger(isolated, [_asset("book_0001", "REFERENCE_WORK", pur="可用"),
                             _asset("book_9101", "METHOD_SOURCE", pur="可用")])
    calls = []
    monkeypatch.setattr(materials, "run_book_distill", lambda aid: calls.append(("bd", aid)) or {"ok": True})
    monkeypatch.setattr(materials, "run_method_distill", lambda aid: calls.append(("md", aid)) or {"ok": True})

    materials.distill_material("book_0001")
    materials.distill_material("book_9101")
    assert calls == [("bd", "book_0001"), ("md", "book_9101")]


def test_prepare_material_rejects_other_types(isolated):
    _write_ledger(isolated, [_asset("book_0003", "LOOSE_MATERIAL"),
                             _asset("book_0004", "NEEDS_REVIEW")])
    with pytest.raises(materials.MaterialsError):
        materials.prepare_material("book_0003")
    with pytest.raises(materials.MaterialsError):
        materials.prepare_material("book_0004")


def test_distill_material_rejects_loose(isolated):
    _write_ledger(isolated, [_asset("book_0003", "LOOSE_MATERIAL")])
    with pytest.raises(materials.MaterialsError):
        materials.distill_material("book_0003")


def test_specific_runners_reject_method_source(isolated):
    """直接调用旧入口时保守拒绝方法素材（绝不静默跑不匹配的处理器）。"""
    _write_ledger(isolated, [_asset("book_9101", "METHOD_SOURCE")])
    with pytest.raises(materials.MaterialsError):
        materials.run_source_prepare("book_9101")
    with pytest.raises(materials.MaterialsError):
        materials.run_book_distill("book_9101")


def test_run_method_prepare_rejects_non_method(isolated):
    _write_ledger(isolated, [_asset("book_0001", "REFERENCE_WORK")])
    with pytest.raises(materials.MaterialsError):
        materials.run_method_prepare("book_0001")
    with pytest.raises(materials.MaterialsError):
        materials.run_method_distill("book_0001")


# ---------- writing_callable 投影 ----------

def test_finalized_method_package_is_writing_callable(isolated, monkeypatch):
    monkeypatch.setattr(materials, "_knowledge_is_discoverable", lambda asset: asset["id"] == "book_9101")
    _write_ledger(isolated, [
        _asset("book_9101", "METHOD_SOURCE", pur="可用", know="可用"),
        _asset("book_9102", "METHOD_SOURCE", pur="可用", know="未开始"),
    ])
    # book_9102 有真实当前 MethodPrepare MD → purified（§7）
    _write_method_source(isolated, "book_9102")
    _write_mp_package(isolated, "book_9102")
    result = materials.list_materials()
    by_id = {m["id"]: m for m in result["materials"]}
    assert by_id["book_9101"]["writing_callable"] is True
    assert by_id["book_9101"]["author_group"] == "usable"
    assert by_id["book_9101"]["knowledge_package_kind"] == "METHOD"
    assert by_id["book_9102"]["writing_callable"] is False
    assert by_id["book_9102"]["author_group"] == "pending"
    assert by_id["book_9102"]["workflow_stage"] == "purified"
    assert by_id["book_9102"]["prepared_format"] == "MD"


def test_material_detail_stage_for_method_asset(isolated, monkeypatch):
    monkeypatch.setattr(materials, "_knowledge_is_discoverable", lambda asset: True)
    _write_ledger(isolated, [_asset("book_9101", "METHOD_SOURCE", pur="可用", know="可用")])
    detail = materials.get_material_detail("book_9101")
    assert detail["writing_callable"] is True
    assert detail["state"] == "ready"


# ---------- validate_intake_plan 允许 METHOD_SOURCE ----------

def test_validate_intake_plan_accepts_method_source(isolated):
    plan = {"items": [{"action": "NEW_ASSET", "files": ["x.epub"], "name": "方法书",
                       "type": "METHOD_SOURCE"}]}
    assert materials.validate_intake_plan(plan) == []


# ---------- 通用蒸馏轮询按桥请求 kind 分派 ----------

def test_material_distill_request_dispatch_by_kind(isolated, monkeypatch):
    from operations import qoder_bridge as bridge
    calls = []
    monkeypatch.setattr(bridge, "get_bridge_root", lambda: isolated / ".bridge")
    monkeypatch.setattr(materials, "get_book_distill_request",
                        lambda rid: calls.append(("bd", rid)) or {"status": "pending"})
    monkeypatch.setattr(materials, "get_method_distill_request",
                        lambda rid: calls.append(("md", rid)) or {"status": "pending"})

    (isolated / ".bridge").mkdir(parents=True, exist_ok=True)
    rid_bk = bridge.create_request(task="t", kind="book_distill_propose", meta={})
    rid_md = bridge.create_request(task="t", kind="method_distill_propose", meta={})

    materials.get_material_distill_request(rid_bk)
    materials.get_material_distill_request(rid_md)
    assert calls == [("bd", rid_bk), ("md", rid_md)]


def test_material_distill_cancel_dispatch_by_kind(isolated, monkeypatch):
    from operations import qoder_bridge as bridge
    calls = []
    monkeypatch.setattr(bridge, "get_bridge_root", lambda: isolated / ".bridge")
    monkeypatch.setattr(materials, "cancel_book_distill_request",
                        lambda rid: calls.append(("bd", rid)) or {"status": "canceled"})
    monkeypatch.setattr(materials, "cancel_method_distill_request",
                        lambda rid: calls.append(("md", rid)) or {"status": "canceled"})

    (isolated / ".bridge").mkdir(parents=True, exist_ok=True)
    rid_md = bridge.create_request(task="t", kind="method_distill_propose", meta={})
    materials.cancel_material_distill_request(rid_md)
    assert calls == [("md", rid_md)]


@pytest.mark.parametrize(("bridge_kind", "getter"), [
    ("book_distill_propose", materials.get_book_distill_request),
    ("method_distill_propose", materials.get_method_distill_request),
])
def test_interactive_distill_pending_exposes_exact_execution_facts(isolated, monkeypatch, bridge_kind, getter):
    """BookDistill and MethodDistill pending paths preserve backend bridge truth."""
    from operations import execution_audit as audit
    from operations import qoder_bridge as bridge
    monkeypatch.setattr(bridge, "get_bridge_root", lambda: isolated / ".bridge")
    monkeypatch.setattr(audit, "finish_file", lambda *args, **kwargs: None)
    rid = bridge.create_request(
        task="internal-task", kind=bridge_kind,
        meta={
            "asset_id": "book_9001",
            "execution": {
                "execution_mode": "interactive_bridge",
                "agent_id": "qoder",
                "model": None,
            },
        },
        activate_for_gowrite=True,
    )

    waiting = getter(rid)
    assert waiting["status"] == "pending"
    assert waiting["execution_mode"] == "interactive_bridge"
    assert waiting["agent_id"] == "qoder"
    assert waiting["model"] is None
    assert waiting["agent_command"] == "/gowrite:1"
    assert waiting["execution_phase"] == "waiting_agent"
    assert "internal-task" not in json.dumps(waiting, ensure_ascii=False)

    assert bridge.claim_request_for_slot(1) is not None
    running = getter(rid)
    assert running["status"] == "pending"
    assert running["execution_phase"] == "running"
    assert running["agent_command"] == "/gowrite:1"
    bridge.cleanup_request(rid)


@pytest.mark.parametrize(("asset_type", "runner", "stage_name", "pending_type", "bridge_kind"), [
    ("REFERENCE_WORK", materials.run_book_distill, "_run_distill_agent_stage", materials._PendingDistill, "book_distill_propose"),
    ("METHOD_SOURCE", materials.run_method_distill, "_run_method_distill_agent_stage", materials._PendingMethodDistill, "method_distill_propose"),
])
def test_interactive_distill_start_result_includes_execution_facts(
        isolated, monkeypatch, asset_type, runner, stage_name, pending_type, bridge_kind):
    """The immediate pending result used by AuthorTaskCoordinator is complete for both distillers."""
    from operations import execution_audit as audit
    from operations import qoder_bridge as bridge
    asset_id = "book_9002"
    _write_ledger(isolated, [_asset(asset_id, asset_type, pur="可用")])
    monkeypatch.setattr(bridge, "get_bridge_root", lambda: isolated / ".bridge")
    monkeypatch.setattr(audit, "AuditRecorder", lambda *args, **kwargs: None)
    monkeypatch.setattr(audit, "append_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(audit, "finish_file", lambda *args, **kwargs: None)
    monkeypatch.setattr(materials, "_prepare_package_current", lambda asset: {"available": True})
    monkeypatch.setattr(materials, "_find_sp_dir", lambda *args: isolated / "prepared-book")
    monkeypatch.setattr(materials, "_find_mp_dir", lambda *args: isolated / "prepared-method")
    completed = subprocess.CompletedProcess([], 0, "", "")
    monkeypatch.setattr(materials, "_run_bd_cli", lambda *args, **kwargs: completed)
    monkeypatch.setattr(materials, "_run_md_cli", lambda *args, **kwargs: completed)

    def wait_for_agent(request_id, *args):
        bridge.create_request(
            task="internal-task", kind=bridge_kind, request_id=request_id,
            meta={
                "asset_id": asset_id,
                "execution": {
                    "execution_mode": "interactive_bridge",
                    "agent_id": "qoder",
                    "model": None,
                },
            },
            activate_for_gowrite=True,
        )
        raise pending_type(request_id)

    monkeypatch.setattr(materials, stage_name, wait_for_agent)
    result = runner(asset_id)
    assert result["status"] == "pending"
    assert result["execution_mode"] == "interactive_bridge"
    assert result["agent_id"] == "qoder"
    assert result["agent_command"] == "/gowrite:1"
    assert result["execution_phase"] == "waiting_agent"
    bridge.cleanup_request(result["request_id"])


def test_cancel_method_distill_removes_request_slot_response_and_staging(isolated, monkeypatch):
    from operations import execution_audit as audit
    from operations import qoder_bridge as bridge
    monkeypatch.setattr(bridge, "get_bridge_root", lambda: isolated / ".bridge")
    monkeypatch.setattr(audit, "finish_file", lambda *args, **kwargs: None)
    rid = "method-cancel-1"
    stage = isolated / "06_工作区" / "MethodDistill" / f"{rid}_sample"
    method_dir = stage / "method"
    method_dir.mkdir(parents=True)
    (method_dir / "partial.md").write_text("partial", encoding="utf-8")
    bridge.create_request(
        task="t", kind="method_distill_propose", request_id=rid,
        meta={"stage_method_dir": str(method_dir)}, activate_for_gowrite=True,
    )
    bridge.write_response(rid, output="late")

    result = materials.cancel_method_distill_request(rid)

    assert result["status"] == "canceled"
    assert not stage.exists()
    assert bridge.get_request(rid) is None
    assert not bridge.response_path(rid).exists()
    assert not (bridge.get_bridge_root() / "slots" / "1.json").exists()


def _method_finalize_fixture(isolated):
    asset_id = "book_9101"
    _write_ledger(isolated, [_asset(asset_id, "METHOD_SOURCE")])
    mp_dir = isolated / "06_工作区" / "MethodPrepare" / f"{asset_id}_素材{asset_id}"
    mp_dir.mkdir(parents=True)
    stage_method = isolated / "06_工作区" / "MethodDistill" / "req" / "method"
    stage_method.mkdir(parents=True)
    (stage_method / "new.marker").write_text("new\n", encoding="utf-8")
    return asset_id, mp_dir, stage_method


def test_direct_method_finalize_requires_no_bridge_request(isolated, monkeypatch):
    """Direct 核心定稿不读 qoder_bridge request。"""
    from operations import qoder_bridge as bridge
    asset_id, mp_dir, stage_method = _method_finalize_fixture(isolated)
    monkeypatch.setattr(bridge, "get_request",
                        lambda rid: (_ for _ in ()).throw(AssertionError("bridge must not be read")))
    monkeypatch.setattr(materials, "_run_md_cli",
                        lambda *a, **k: subprocess.CompletedProcess([], 0))
    monkeypatch.setattr(materials, "_knowledge_is_discoverable", lambda asset: True)
    catalog, _, _ = materials._load_materialintake()
    monkeypatch.setattr(catalog, "refresh_and_render", lambda *a, **k: 0)

    result = materials._finalize_method_distill_core(
        "direct-no-request", asset_id, mp_dir, stage_method)

    assert Path(result["output_dir"]).joinpath("new.marker").is_file()


@pytest.mark.parametrize("failure", ["discovery", "catalog"])
def test_method_publish_restores_previous_package_on_verification_failure(
        isolated, monkeypatch, failure):
    asset_id, mp_dir, stage_method = _method_finalize_fixture(isolated)
    dest = isolated / "02_素材知识库" / mp_dir.name / "method"
    dest.mkdir(parents=True)
    (dest / "old.marker").write_text("old\n", encoding="utf-8")
    ledger_path = isolated / "01_原始素材" / "素材资产.json"
    ledger_before = ledger_path.read_bytes()
    monkeypatch.setattr(materials, "_run_md_cli",
                        lambda *a, **k: subprocess.CompletedProcess([], 0))
    monkeypatch.setattr(materials, "_knowledge_is_discoverable",
                        lambda asset: failure != "discovery")
    catalog, _, _ = materials._load_materialintake()
    def refresh(*args, **kwargs):
        if failure == "catalog":
            ledger_path.write_bytes(b"partial\n")
            return 1
        return 0
    monkeypatch.setattr(catalog, "refresh_and_render", refresh)

    with pytest.raises(materials.MaterialsError, match="已保留原知识包"):
        materials._finalize_method_distill_core("req", asset_id, mp_dir, stage_method)

    assert (dest / "old.marker").read_text(encoding="utf-8") == "old\n"
    assert not (dest / "new.marker").exists()
    assert (stage_method / "new.marker").read_text(encoding="utf-8") == "new\n"
    assert ledger_path.read_bytes() == ledger_before


def test_interactive_method_canceled_before_response_never_publishes(isolated, monkeypatch):
    from operations import qoder_bridge as bridge
    monkeypatch.setattr(bridge, "get_bridge_root", lambda: isolated / ".bridge")
    (isolated / ".bridge").mkdir(parents=True)
    dest = isolated / "02_素材知识库" / "book_9101_素材" / "method"
    dest.mkdir(parents=True)
    (dest / "old.marker").write_text("old\n", encoding="utf-8")
    rid = bridge.create_request(
        task="t", kind="method_distill_propose",
        meta={"asset_id": "book_9101", "mp_dir": "x", "stage_method_dir": "y"})
    bridge.mark_canceled(rid)
    bridge.write_response(rid, result={"status": "completed"})
    finalized = []
    monkeypatch.setattr(materials, "_finalize_method_distill_interactive",
                        lambda *a: finalized.append(a))

    result = materials.get_method_distill_request(rid)

    assert result["status"] == "canceled" and finalized == []
    assert (dest / "old.marker").is_file()


def test_interactive_method_missing_request_rejects_late_response(isolated, monkeypatch):
    from operations import qoder_bridge as bridge
    monkeypatch.setattr(bridge, "get_bridge_root", lambda: isolated / ".bridge")
    (isolated / ".bridge").mkdir(parents=True)
    dest = isolated / "02_素材知识库" / "book_9101_素材" / "method"
    dest.mkdir(parents=True)
    (dest / "old.marker").write_text("old\n", encoding="utf-8")
    rid = bridge.create_request(
        task="t", kind="method_distill_propose",
        meta={"asset_id": "book_9101", "mp_dir": "x", "stage_method_dir": "y"})
    bridge.cleanup_request(rid)
    bridge.write_response(rid, result={"status": "completed"})
    finalized = []
    monkeypatch.setattr(materials, "_finalize_method_distill_interactive",
                        lambda *a: finalized.append(a))

    result = materials.get_method_distill_request(rid)

    assert result["status"] == "failed" and finalized == []
    assert (dest / "old.marker").is_file()


def test_interactive_method_wrapper_rechecks_cancellation_before_core(isolated, monkeypatch):
    """Outer poll 后若发生取消，Interactive wrapper 的 TOCTOU 检查仍阻止发布。"""
    from operations import qoder_bridge as bridge
    monkeypatch.setattr(bridge, "get_request", lambda rid: {
        "request_id": rid, "kind": "method_distill_propose", "state": "canceled"})
    monkeypatch.setattr(bridge, "cleanup_request", lambda rid: None)
    finalized = []
    monkeypatch.setattr(materials, "_finalize_method_distill_core",
                        lambda *a: finalized.append(a))

    with pytest.raises(materials.MaterialsError, match="已取消"):
        materials._finalize_method_distill_interactive(
            "req", "book_9101", Path("x"), Path("y"))

    assert finalized == []


def test_different_assets_can_enter_long_distill_stage_concurrently(isolated, monkeypatch):
    _write_ledger(isolated, [_asset("book_0001", "REFERENCE_WORK"), _asset("book_0002", "REFERENCE_WORK")])
    entered = []
    both = threading.Event()
    release = threading.Event()

    def run(asset_id):
        entered.append(asset_id)
        if len(entered) == 2:
            both.set()
        assert release.wait(2)
        return {"asset_id": asset_id, "status": "pending", "request_id": asset_id}

    monkeypatch.setattr(materials, "run_book_distill", run)
    results = []
    threads = [threading.Thread(target=lambda aid=aid: results.append(materials.distill_material(aid)))
               for aid in ("book_0001", "book_0002")]
    for thread in threads:
        thread.start()
    assert both.wait(1), "different asset claims must not serialize long work"
    release.set()
    for thread in threads:
        thread.join(2)
    assert {item["asset_id"] for item in results} == {"book_0001", "book_0002"}


def test_same_asset_duplicate_is_rejected_during_long_stage(isolated, monkeypatch):
    _write_ledger(isolated, [_asset("book_0001", "REFERENCE_WORK")])
    entered = threading.Event()
    release = threading.Event()

    def run(asset_id):
        entered.set()
        assert release.wait(2)
        return {"asset_id": asset_id, "status": "pending", "request_id": "r1"}

    monkeypatch.setattr(materials, "run_book_distill", run)
    first = threading.Thread(target=lambda: materials.distill_material("book_0001"))
    first.start()
    assert entered.wait(1)
    with pytest.raises(materials.MaterialsError, match="正在学习"):
        materials.distill_material("book_0001")
    release.set()
    first.join(2)


def test_material_final_settlements_are_serialized(isolated, monkeypatch):
    _write_ledger(isolated, [_asset("book_9101", "METHOD_SOURCE"), _asset("book_9102", "METHOD_SOURCE")])
    packages = []
    for asset_id in ("book_9101", "book_9102"):
        mp = isolated / "06_工作区" / "MethodPrepare" / f"{asset_id}_素材{asset_id}"
        stage = isolated / "06_工作区" / "MethodDistill" / asset_id / "method"
        mp.mkdir(parents=True)
        stage.mkdir(parents=True)
        (stage / "new.marker").write_text("new\n", encoding="utf-8")
        packages.append((asset_id, mp, stage))
    monkeypatch.setattr(materials, "_run_md_cli", lambda *a, **k: subprocess.CompletedProcess([], 0))
    monkeypatch.setattr(materials, "_knowledge_is_discoverable", lambda asset: True)
    catalog, _, _ = materials._load_materialintake()
    state = {"inside": 0, "max": 0}
    counter_lock = threading.Lock()

    def refresh(*args, **kwargs):
        with counter_lock:
            state["inside"] += 1
            state["max"] = max(state["max"], state["inside"])
        time.sleep(0.08)
        with counter_lock:
            state["inside"] -= 1
        return 0

    monkeypatch.setattr(catalog, "refresh_and_render", refresh)
    errors = []
    def settle(args):
        try:
            materials._finalize_method_distill_core(f"req-{args[0]}", *args)
        except Exception as exc:  # pragma: no cover - asserted below
            errors.append(exc)
    threads = [threading.Thread(target=settle, args=(args,)) for args in packages]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(3)
    assert errors == []
    assert state["max"] == 1


def test_material_lock_is_not_held_during_agent_stage(isolated, monkeypatch):
    asset_id = "book_9101"
    _write_ledger(isolated, [_asset(asset_id, "METHOD_SOURCE")])
    mp = isolated / "06_工作区" / "MethodPrepare" / f"{asset_id}_素材{asset_id}"
    mp.mkdir(parents=True)
    monkeypatch.setattr(materials, "_prepare_package_current", lambda asset: {"available": True})
    monkeypatch.setattr(materials, "_find_mp_dir", lambda aid: mp)
    monkeypatch.setattr(materials, "_run_md_cli", lambda *a, **k: subprocess.CompletedProcess([], 0))
    acquired = threading.Event()

    def agent_stage(request_id, aid, mp_dir, stage_dir):
        def probe():
            with material_settlement.serialized():
                acquired.set()
        thread = threading.Thread(target=probe)
        thread.start()
        thread.join(1)
        assert acquired.is_set(), "Agent stage must stay outside the material settlement lock"
        raise materials._PendingMethodDistill(request_id)

    monkeypatch.setattr(materials, "_run_method_distill_agent_stage", agent_stage)
    result = materials.run_method_distill(asset_id)
    assert result["status"] == "pending"
