# -*- coding: utf-8 -*-
"""Focused contracts for deterministic Go Write 2.0 direct-impact reports."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "05_Skills与自动化" / "01_Skills" / "ProjectWorkspace"))

import project_workspace  # noqa: E402
from operations import project_impact as impact_ops  # noqa: E402
from operations import project_model as model_ops  # noqa: E402


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    root = tmp_path / "03_作品工程"
    root.mkdir()
    monkeypatch.setattr(project_workspace, "get_projects_root", lambda: root)
    return root


@pytest.fixture()
def project(isolated):
    return project_workspace.create_project(name="影响报告", author_intent={
        "work_direction": "测试方向", "reader_promise": "测试期待",
        "hard_constraints": [], "open_space": [],
    })


def _create(project, title):
    return model_ops.create_foundation_record(
        project["project_id"], base_model_rev=model_ops.load_project_model(project["project_id"])["model_rev"],
        category="character", title=title,
    )


def _ref(model):
    return model["change_history"][-1]["detail"]["ref"]


def _project_file_bytes(project):
    root = Path(project["project_dir"])
    return {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def test_missing_project_model_is_a_read_only_failure(project):
    artifact = Path(project["project_dir"]) / "_工作台状态" / model_ops.ARTIFACT_NAME
    assert not artifact.exists()
    with pytest.raises(impact_ops.ProjectImpactError, match="尚未建立"):
        impact_ops.build_direct_impact_report(project["project_id"], 1)
    assert not artifact.exists()


def test_malformed_project_model_is_not_rewritten(project):
    model_ops.load_project_model(project["project_id"])
    artifact = Path(project["project_dir"]) / "_工作台状态" / model_ops.ARTIFACT_NAME
    artifact.write_text("{not-json", encoding="utf-8")
    before = artifact.read_bytes()
    with pytest.raises(impact_ops.ProjectImpactError, match="读取或校验"):
        impact_ops.build_direct_impact_report(project["project_id"], 1)
    assert artifact.read_bytes() == before


def test_latest_object_edit_keeps_concrete_raw_change_and_snapshot(project):
    created = _create(project, "旧名")
    ref = _ref(created)
    updated = model_ops.update_object(
        project["project_id"], base_model_rev=created["model_rev"], ref=ref,
        title="新名", data={"note": "明确修改"},
    )
    before = _project_file_bytes(project)
    report = impact_ops.build_direct_impact_report(project["project_id"], updated["model_rev"])
    assert _project_file_bytes(project) == before
    assert report["changed_object_refs"] == [ref]
    assert report["change"]["detail"]["changes"]["title"] == {"before": "旧名", "after": "新名"}
    assert report["object_snapshots"][ref]["title"] == "新名"


def test_outgoing_and_incoming_candidates_are_deterministic(project):
    first = _create(project, "甲")
    first_ref = _ref(first)
    second = _create(project, "乙")
    second_ref = _ref(second)
    edge = model_ops.add_dependency(
        project["project_id"], base_model_rev=second["model_rev"], source_ref=first_ref,
        target_ref=second_ref, relation_kind="supports",
    )
    created_report = impact_ops.build_direct_impact_report(project["project_id"], edge["model_rev"])
    assert created_report["changed_object_refs"] == []
    assert created_report["changed_dependency_refs"] == [_ref(edge)]
    assert created_report["object_snapshots"] == {
        first_ref: edge["objects"][first_ref], second_ref: edge["objects"][second_ref],
    }
    outgoing = model_ops.update_object(
        project["project_id"], base_model_rev=edge["model_rev"], ref=first_ref, title="甲改名",
    )
    report = impact_ops.build_direct_impact_report(project["project_id"], outgoing["model_rev"])
    assert report["direct_dependency_candidates"] == [{
        "edge_ref": _ref(edge), "changed_ref": first_ref, "other_ref": second_ref,
        "direction": "outgoing", "relation_kind": "supports", "edge_state": "active",
    }]
    incoming = model_ops.update_object(
        project["project_id"], base_model_rev=outgoing["model_rev"], ref=second_ref, title="乙改名",
    )
    report = impact_ops.build_direct_impact_report(project["project_id"], incoming["model_rev"])
    assert report["direct_dependency_candidates"][0]["direction"] == "incoming"
    assert report["direct_dependency_candidates"][0]["other_ref"] == first_ref


def test_tombstone_retirement_evidence_includes_only_same_revision_edge(project):
    first = _create(project, "甲")
    first_ref = _ref(first)
    second = _create(project, "乙")
    second_ref = _ref(second)
    edged = model_ops.add_dependency(
        project["project_id"], base_model_rev=second["model_rev"], source_ref=first_ref,
        target_ref=second_ref, relation_kind="supports",
    )
    edge_ref = _ref(edged)
    retired = model_ops.tombstone_object(
        project["project_id"], base_model_rev=edged["model_rev"], ref=first_ref,
    )
    report = impact_ops.build_direct_impact_report(project["project_id"], retired["model_rev"])
    assert report["changed_dependency_refs"] == [edge_ref]
    assert report["direct_dependency_candidates"][0]["edge_state"] == "retired_in_source_change"
    assert report["direct_dependency_candidates"][0]["other_ref"] == second_ref

    third = _create(project, "丙")
    follow_up = model_ops.update_object(
        project["project_id"], base_model_rev=third["model_rev"], ref=_ref(third), title="丙改名",
    )
    later = impact_ops.build_direct_impact_report(project["project_id"], follow_up["model_rev"])
    assert later["direct_dependency_candidates"] == []


def test_length_plan_refs_actual_counts_and_total_scope(project):
    planned = model_ops.set_length_plan(
        project["project_id"], base_model_rev=0, total_target_words=120000,
        stages=[{"name": "第一幕", "target_words": 40000}],
        chapter_targets=[
            {"label": "第001章", "min_words": 2000, "max_words": 3000},
            {"label": "第002章", "min_words": 2500, "max_words": 3500},
        ],
    )
    report = impact_ops.build_direct_impact_report(project["project_id"], planned["model_rev"])
    stage_ref = planned["length_plan"]["stage_refs"][0]
    chapters = planned["length_plan"]["chapter_target_refs"]
    assert report["changed_object_refs"] == sorted([stage_ref, *chapters])
    assert report["changed_scopes"] == ["length_plan.total_target_words"]

    counts = model_ops.set_length_plan(
        project["project_id"], base_model_rev=planned["model_rev"],
        actual_word_counts={chapters[0]: 2200, chapters[1]: 2800},
    )
    count_report = impact_ops.build_direct_impact_report(project["project_id"], counts["model_rev"])
    assert count_report["changed_object_refs"] == sorted(chapters)
    changed = model_ops.set_length_plan(
        project["project_id"], base_model_rev=counts["model_rev"],
        actual_word_counts={chapters[0]: 2400, chapters[1]: 2800},
    )
    changed_report = impact_ops.build_direct_impact_report(project["project_id"], changed["model_rev"])
    assert changed_report["changed_object_refs"] == [chapters[0]]


def test_stale_and_missing_revision_rejected_and_report_is_read_only(project, monkeypatch):
    created = _create(project, "甲")
    ref = _ref(created)
    current = model_ops.update_object(
        project["project_id"], base_model_rev=created["model_rev"], ref=ref, title="甲改名",
    )
    artifact = Path(project["project_dir"]) / "_工作台状态" / model_ops.ARTIFACT_NAME
    before = artifact.read_bytes()
    report = impact_ops.build_direct_impact_report(project["project_id"], current["model_rev"])
    assert artifact.read_bytes() == before
    with pytest.raises(impact_ops.ProjectImpactError, match="当前 model_rev"):
        impact_ops.build_direct_impact_report(project["project_id"], created["model_rev"])

    missing = dict(model_ops.load_project_model(project["project_id"]))
    missing["change_history"] = []
    monkeypatch.setattr(impact_ops, "_load_read_only_project_model", lambda _project_id: missing)
    with pytest.raises(impact_ops.ProjectImpactError, match="恰好"):
        impact_ops.build_direct_impact_report(project["project_id"], current["model_rev"])
