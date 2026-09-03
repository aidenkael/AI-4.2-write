# -*- coding: utf-8 -*-
"""METHOD_SOURCE 作者面操作测试：通用提纯/蒸馏入口的类型分派 + writing_callable 投影。

覆盖验收：
  - prepare_material / distill_material 只收素材 id，后端按 canonical 类型分派：
    REFERENCE_WORK → SourcePrepare/BookDistill；METHOD_SOURCE → MethodPrepare/MethodDistill；
  - 其他类型保守拒绝（不静默跑不匹配的处理器）；
  - 定稿方法知识包 → 素材列表投影 writing_callable=true（author_group=usable）。
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from operations import materials  # noqa: E402


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    root = tmp_path / "root"
    (root / "01_原始素材").mkdir(parents=True)
    monkeypatch.setattr(materials, "get_repo_root", lambda: root)
    return root


def _asset(asset_id, asset_type, pur="未处理", know="未开始"):
    return {
        "id": asset_id, "name": f"素材{asset_id}", "type": asset_type,
        "author": "", "tags": [], "notes": "",
        "files": [{"path": f"02_研究资料/{asset_id}/x.txt", "sha256": "c" * 64, "primary": True}],
        "purification": {"status": pur, "evidence": None},
        "knowledge": {"status": know},
    }


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
    result = materials.list_materials()
    by_id = {m["id"]: m for m in result["materials"]}
    assert by_id["book_9101"]["writing_callable"] is True
    assert by_id["book_9101"]["author_group"] == "usable"
    assert by_id["book_9102"]["writing_callable"] is False
    assert by_id["book_9102"]["author_group"] == "pending"


def test_material_detail_stage_for_method_asset(isolated, monkeypatch):
    monkeypatch.setattr(materials, "_knowledge_is_discoverable", lambda asset: True)
    _write_ledger(isolated, [_asset("book_9101", "METHOD_SOURCE", pur="可用", know="可用")])
    detail = materials.get_material_detail("book_9101")
    assert detail["writing_callable"] is True
    assert detail["state"] == "ready"


# ---------- 分类决策允许 METHOD_SOURCE ----------

def test_classify_output_accepts_method_source(isolated):
    output = json.dumps({"items": [
        {"filename": "方法书.epub", "action": "NEW_ASSET", "name": "故事方法", "type": "METHOD_SOURCE"},
    ]}, ensure_ascii=False)
    scan = {"方法书.epub": {"filename": "方法书.epub"}}
    decisions = materials._parse_classify_output(output, scan, {"assets": []})
    assert decisions[0]["type"] == "METHOD_SOURCE"


def test_classify_output_rejects_unknown_type(isolated):
    output = json.dumps({"items": [
        {"filename": "x.epub", "action": "NEW_ASSET", "name": "x", "type": "METHOD"},
    ]}, ensure_ascii=False)
    scan = {"x.epub": {"filename": "x.epub"}}
    with pytest.raises(materials.MaterialsError):
        materials._parse_classify_output(output, scan, {"assets": []})


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
