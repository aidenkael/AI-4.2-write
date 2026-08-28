# -*- coding: utf-8 -*-
"""Focused contract tests for the isolated Go Write 2.0 project model."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "05_Skills与自动化" / "01_Skills" / "ProjectWorkspace"))

import project_workspace  # noqa: E402
from operations import project_model as model_ops  # noqa: E402


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    root = tmp_path / "03_作品工程"
    root.mkdir()
    monkeypatch.setattr(project_workspace, "get_projects_root", lambda: root)
    return root


def _create(name: str):
    return project_workspace.create_project(name=name, author_intent={
        "work_direction": "测试方向", "reader_promise": "测试期待",
        "hard_constraints": [], "open_space": [],
    })


@pytest.fixture()
def project(isolated):
    return _create("数据地基")


def _add_character(project, *, title="旧名", state="current"):
    return model_ops.create_foundation_record(
        project["project_id"], base_model_rev=model_ops.load_project_model(project["project_id"])["model_rev"],
        category="character", title=title, material_state=state, data={"note": "作者明确录入"},
    )


def test_lazy_initialization_existing_project_isolated_from_story_state(project):
    project_dir = Path(project["project_dir"])
    state_file = project_dir / "_工作台状态" / "story_state.json"
    before = state_file.read_bytes()
    model = model_ops.load_project_model(project["project_id"])
    assert model["schema_version"] == model_ops.SCHEMA_VERSION
    assert model["project_id"] == project["project_id"]
    assert model["model_rev"] == 0
    assert state_file.read_bytes() == before
    assert (project_dir / "_工作台状态" / model_ops.ARTIFACT_NAME).exists()


def test_stable_ref_survives_rename_and_model_rev_increments(project):
    created = _add_character(project)
    ref = created["change_history"][-1]["detail"]["ref"]
    updated = model_ops.update_object(
        project["project_id"], base_model_rev=created["model_rev"], ref=ref, title="新名", data={"note": "编辑后"},
    )
    assert created["model_rev"] == 1 and updated["model_rev"] == 2
    assert updated["objects"][ref]["title"] == "新名"
    assert updated["objects"][ref]["ref"] == ref
    assert [h["kind"] for h in updated["change_history"]] == ["foundation.created", "object.updated"]


def test_stale_revision_rejected(project):
    created = _add_character(project)
    ref = created["change_history"][-1]["detail"]["ref"]
    with pytest.raises(model_ops.ProjectModelError, match="stale"):
        model_ops.update_object(project["project_id"], base_model_rev=0, ref=ref, title="过期写入")


def test_cross_project_ref_rejected(isolated, project):
    other = _create("另一部作品")
    ref = _add_character(other)["change_history"][-1]["detail"]["ref"]
    with pytest.raises(model_ops.ProjectModelError, match="跨项目"):
        model_ops.update_object(project["project_id"], base_model_rev=0, ref=ref, title="串书")


def test_tombstone_preserves_identity_and_ref_is_not_reused(project):
    first = _add_character(project)
    first_ref = first["change_history"][-1]["detail"]["ref"]
    retired = model_ops.tombstone_object(project["project_id"], base_model_rev=1, ref=first_ref)
    second = model_ops.create_foundation_record(
        project["project_id"], base_model_rev=retired["model_rev"], category="character", title="后来者",
    )
    second_ref = second["change_history"][-1]["detail"]["ref"]
    assert second_ref != first_ref
    assert second["objects"][first_ref]["tombstoned"] is True
    with pytest.raises(model_ops.ProjectModelError, match="tombstone"):
        model_ops.update_object(project["project_id"], base_model_rev=second["model_rev"], ref=first_ref, title="复活")


def test_custom_system_and_current_future_separation(project):
    custom = model_ops.create_foundation_record(
        project["project_id"], base_model_rev=0, category="custom", category_name="家族谱系",
        title="沈氏家谱", material_state="future", data={"generation": 3},
    )
    system = model_ops.create_system(
        project["project_id"], base_model_rev=custom["model_rev"], title="灵力兑换规则",
        material_state="current", definition={"units": ["灵砂", "灵玉"], "rate": "100:1"},
    )
    objects = system["objects"]
    custom_ref = custom["change_history"][-1]["detail"]["ref"]
    system_ref = system["change_history"][-1]["detail"]["ref"]
    assert objects[custom_ref]["category_name"] == "家族谱系"
    assert objects[custom_ref]["material_state"] == "future"
    assert objects[system_ref]["kind"] == "system"
    assert objects[system_ref]["data"]["units"] == ["灵砂", "灵玉"]


def test_length_planning_needs_no_volumes_and_never_infers_actual_counts(project):
    planned = model_ops.set_length_plan(
        project["project_id"], base_model_rev=0, total_target_words=180000,
        stages=[{"name": "第一幕", "target_words": 60000}],
        chapter_targets=[{"label": "开篇", "min_words": 2500, "max_words": 4000}],
    )
    plan = planned["length_plan"]
    assert plan["total_target_words"] == 180000
    assert len(plan["stage_refs"]) == 1
    assert planned["objects"][plan["stage_refs"][0]]["title"] == "第一幕"
    chapter_ref = plan["chapter_target_refs"][0]
    assert plan["actual_word_counts"] == {}
    counted = model_ops.set_length_plan(
        project["project_id"], base_model_rev=planned["model_rev"], actual_word_counts={chapter_ref: 3120},
    )
    assert counted["length_plan"]["actual_word_counts"] == {chapter_ref: 3120}
    no_volume = model_ops.set_length_plan(
        project["project_id"], base_model_rev=counted["model_rev"], stages=[],
    )
    assert no_volume["length_plan"]["stage_refs"] == []


def test_direct_dependency_requires_known_same_project_refs(project, isolated):
    one = _add_character(project, title="人物")
    one_ref = one["change_history"][-1]["detail"]["ref"]
    two = model_ops.create_foundation_record(
        project["project_id"], base_model_rev=one["model_rev"], category="story_line", title="主线",
    )
    two_ref = two["change_history"][-1]["detail"]["ref"]
    edged = model_ops.add_dependency(
        project["project_id"], base_model_rev=two["model_rev"], source_ref=one_ref, target_ref=two_ref,
        relation_kind="motivates",
    )
    edges = model_ops.list_direct_dependencies(project["project_id"], one_ref)
    assert len(edges) == 1 and edges[0]["target_ref"] == two_ref

    other = _create("边依赖跨项目")
    other_ref = _add_character(other)["change_history"][-1]["detail"]["ref"]
    with pytest.raises(model_ops.ProjectModelError, match="跨项目"):
        model_ops.add_dependency(
            project["project_id"], base_model_rev=edged["model_rev"], source_ref=one_ref,
            target_ref=other_ref, relation_kind="invalid",
        )


def test_atomic_persisted_reload(project):
    written = _add_character(project, title="可重载")
    artifact = Path(project["project_dir"]) / "_工作台状态" / model_ops.ARTIFACT_NAME
    on_disk = json.loads(artifact.read_text(encoding="utf-8"))
    reloaded = model_ops.load_project_model(project["project_id"])
    assert on_disk == reloaded == written
    assert not list(artifact.parent.glob(".gowrite-project-model-*"))


def test_malformed_or_cross_project_artifact_is_rejected(project, isolated):
    model_ops.load_project_model(project["project_id"])
    artifact = Path(project["project_dir"]) / "_工作台状态" / model_ops.ARTIFACT_NAME
    model = json.loads(artifact.read_text(encoding="utf-8"))
    model["objects"]["gw2_obj_foreign_00000001"] = {
        "ref": "gw2_obj_foreign_00000001", "kind": "foundation",
        "material_state": "current", "tombstoned": False,
    }
    artifact.write_text(json.dumps(model, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(model_ops.ProjectModelError, match="跨项目"):
        model_ops.load_project_model(project["project_id"])
