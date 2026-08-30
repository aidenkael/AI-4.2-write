# -*- coding: utf-8 -*-
"""Focused regression tests: retire/restore + retired projection.

All deterministic; zero model/API/Agent calls.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[3] / "05_Skills与自动化" / "01_Skills" / "ProjectWorkspace"),
)

import project_workspace  # noqa: E402
from operations import author_edit, project_model, project_snapshot  # noqa: E402


@pytest.fixture()
def projects_root(tmp_path, monkeypatch):
    root = tmp_path / "03_作品工程"
    root.mkdir()
    monkeypatch.setattr(project_workspace, "get_projects_root", lambda: root)
    return root


def _create(name: str):
    return project_workspace.create_project(name=name, author_intent={
        "work_direction": "测试退役与恢复",
        "reader_promise": "同一记录可安全退役与恢复",
        "hard_constraints": [],
        "open_space": [],
    })


def _last_ref(model: dict) -> str:
    return model["change_history"][-1]["detail"]["ref"]


def _snapshot_refs(snapshot: dict, bucket: str, section: str) -> set:
    return {item["ref"] for item in snapshot[bucket].get(section, [])}


def test_retire_makes_record_inactive_and_restore_returns_same_ref(projects_root):
    project = _create("退役恢复")
    created = author_edit.create_foundation_record(
        project["project_id"], base_model_rev=0, category="character",
        title="林砚", material_state="current", data={"one_line_intro": "调查员"},
    )
    ref = _last_ref(created["model"])
    retired = author_edit.retire_foundation_record(
        project["project_id"], base_model_rev=created["model"]["model_rev"], ref=ref,
    )
    snapshot = project_snapshot.get_project_snapshot(project["project_id"])
    assert ref not in _snapshot_refs(snapshot, "current", "characters")
    assert ref not in _snapshot_refs(snapshot, "future", "characters")

    restored = author_edit.restore_foundation_record(
        project["project_id"], base_model_rev=retired["model"]["model_rev"], ref=ref,
    )
    assert restored["change"]["source_kind"] == "foundation_restore"
    snapshot = project_snapshot.get_project_snapshot(project["project_id"])
    assert ref in _snapshot_refs(snapshot, "current", "characters")


def test_restore_preserves_data_history_and_authority_metadata(projects_root):
    project = _create("恢复保真")
    created = author_edit.create_foundation_record(
        project["project_id"], base_model_rev=0, category="character",
        title="苏晚", material_state="current",
        data={"one_line_intro": "助手", "current_state": "在城中"},
    )
    ref = _last_ref(created["model"])
    retired = author_edit.retire_foundation_record(
        project["project_id"], base_model_rev=created["model"]["model_rev"], ref=ref,
    )
    restored_model = author_edit.restore_foundation_record(
        project["project_id"], base_model_rev=retired["model"]["model_rev"], ref=ref,
    )["model"]
    item = restored_model["objects"][ref]
    assert item["tombstoned"] is False
    assert item["data"]["one_line_intro"] == "助手"
    assert item["data"]["current_state"] == "在城中"
    assert item["author_fields"] and "one_line_intro" in item["author_fields"]
    assert isinstance(item.get("restored_at_rev"), int)
    # The record is restored in place: creation, retirement and restoration are
    # all visible in the same change history (normal model revision entries).
    kinds = [entry["kind"] for entry in restored_model["change_history"]]
    assert kinds.count("foundation.created") == 1
    assert kinds.count("object.tombstoned") == 1
    assert kinds.count("object.restored") == 1
    assert len(restored_model["objects"]) == len(created["model"]["objects"])


def test_stale_restore_is_rejected(projects_root):
    project = _create("过期恢复")
    created = author_edit.create_foundation_record(
        project["project_id"], base_model_rev=0, category="character",
        title="陈默", material_state="current", data={},
    )
    ref = _last_ref(created["model"])
    retired = author_edit.retire_foundation_record(
        project["project_id"], base_model_rev=created["model"]["model_rev"], ref=ref,
    )
    with pytest.raises(author_edit.AuthorEditError):
        author_edit.restore_foundation_record(
            project["project_id"], base_model_rev=0, ref=ref,  # stale baseline
        )
    # Still retired after the rejected attempt.
    snapshot = project_snapshot.get_project_snapshot(project["project_id"])
    assert ref not in _snapshot_refs(snapshot, "current", "characters")
    assert retired["model"]["objects"][ref]["tombstoned"] is True


def test_relationship_restore_preserves_endpoints(projects_root):
    project = _create("关系恢复")
    first = author_edit.create_foundation_record(
        project["project_id"], base_model_rev=0, category="character",
        title="甲", material_state="current", data={},
    )
    ref_a = _last_ref(first["model"])
    second = author_edit.create_foundation_record(
        project["project_id"], base_model_rev=first["model"]["model_rev"],
        category="character", title="乙", material_state="current", data={},
    )
    ref_b = _last_ref(second["model"])
    relation = author_edit.create_relationship(
        project["project_id"], base_model_rev=second["model"]["model_rev"],
        source_ref=ref_a, target_ref=ref_b, label="旧识", material_state="current", data={},
    )
    edge_ref = _last_ref(relation["model"])
    # Retiring the character retires the incident relationship with it.
    retired = author_edit.retire_foundation_record(
        project["project_id"], base_model_rev=relation["model"]["model_rev"], ref=ref_a,
    )
    snapshot = project_snapshot.get_project_snapshot(project["project_id"])
    assert edge_ref not in _snapshot_refs(snapshot, "current", "relationships")
    assert ref_a in {item["ref"] for item in snapshot["retired"]["foundation"]}
    assert edge_ref in {item["ref"] for item in snapshot["retired"]["relationships"]}

    author_edit.restore_foundation_record(
        project["project_id"], base_model_rev=retired["model"]["model_rev"], ref=ref_a,
    )
    snapshot = project_snapshot.get_project_snapshot(project["project_id"])
    # Same edge ref is active again with the same endpoints.
    active_edges = [
        item for item in snapshot["current"]["relationships"] if item["ref"] == edge_ref
    ]
    assert len(active_edges) == 1
    record = active_edges[0]["record"]
    assert record["source"] == ref_a and record["target"] == ref_b


def test_direct_relationship_retire_and_restore(projects_root):
    project = _create("关系直退")
    first = author_edit.create_foundation_record(
        project["project_id"], base_model_rev=0, category="character",
        title="丙", material_state="current", data={},
    )
    ref_a = _last_ref(first["model"])
    second = author_edit.create_foundation_record(
        project["project_id"], base_model_rev=first["model"]["model_rev"],
        category="character", title="丁", material_state="current", data={},
    )
    ref_b = _last_ref(second["model"])
    relation = author_edit.create_relationship(
        project["project_id"], base_model_rev=second["model"]["model_rev"],
        source_ref=ref_a, target_ref=ref_b, label="师徒", material_state="current", data={},
    )
    edge_ref = _last_ref(relation["model"])
    retired = author_edit.retire_relationship(
        project["project_id"], base_model_rev=relation["model"]["model_rev"], ref=edge_ref,
    )
    snapshot = project_snapshot.get_project_snapshot(project["project_id"])
    assert edge_ref in {item["ref"] for item in snapshot["retired"]["relationships"]}

    author_edit.restore_relationship(
        project["project_id"], base_model_rev=retired["model"]["model_rev"], ref=edge_ref,
    )
    snapshot = project_snapshot.get_project_snapshot(project["project_id"])
    assert edge_ref in _snapshot_refs(snapshot, "current", "relationships")


def test_retired_records_never_mix_into_current_or_future(projects_root):
    project = _create("分区投影")
    created = author_edit.create_foundation_record(
        project["project_id"], base_model_rev=0, category="character",
        title="退役者", material_state="current", data={},
    )
    ref = _last_ref(created["model"])
    author_edit.retire_foundation_record(
        project["project_id"], base_model_rev=created["model"]["model_rev"], ref=ref,
    )
    snapshot = project_snapshot.get_project_snapshot(project["project_id"])
    for bucket in ("current", "future"):
        for _section, items in snapshot[bucket].items():
            assert all(item["ref"] != ref for item in items)
    retired_refs = {item["ref"] for item in snapshot["retired"]["foundation"]}
    assert ref in retired_refs


def test_restore_is_deterministic_and_invokes_no_ai(projects_root, monkeypatch):
    from ai import runner as semantic_ai

    def _forbidden(*args, **kwargs):
        raise AssertionError("恢复操作绝不调用 AI/Agent")

    monkeypatch.setattr(semantic_ai, "run_text", _forbidden)
    monkeypatch.setattr(
        semantic_ai, "require_semantic_ai",
        lambda: (_ for _ in ()).throw(AssertionError("恢复操作绝不读取日常 AI 配置")),
    )
    project = _create("无AI恢复")
    created = author_edit.create_foundation_record(
        project["project_id"], base_model_rev=0, category="character",
        title="静默", material_state="current", data={},
    )
    ref = _last_ref(created["model"])
    retired = author_edit.retire_foundation_record(
        project["project_id"], base_model_rev=created["model"]["model_rev"], ref=ref,
    )
    restored = author_edit.restore_foundation_record(
        project["project_id"], base_model_rev=retired["model"]["model_rev"], ref=ref,
    )
    # Restoration is mechanical by contract: no semantic settlement is queued.
    assert restored["change"]["requires_semantic"] is False
    assert restored["change"]["status"] == "synchronized"
