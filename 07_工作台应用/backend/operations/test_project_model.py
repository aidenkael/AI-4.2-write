# -*- coding: utf-8 -*-
"""Focused contract tests for the isolated Go Write 2.0 project model."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
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


def test_length_plan_links_new_stage_and_chapter_in_one_save(project):
    planned = model_ops.set_length_plan(
        project["project_id"], base_model_rev=0,
        stages=[{"client_key": "stage-a", "title": "第一卷", "target_words": 50000, "kind": "volume"}],
        chapter_targets=[
            {"title": "第1章", "chapter_number": 1, "min_words": 2500, "max_words": 4000, "stage_key": "stage-a"},
        ],
    )
    stage_ref = planned["length_plan"]["stage_refs"][0]
    chapter_ref = planned["length_plan"]["chapter_target_refs"][0]
    assert planned["objects"][chapter_ref]["data"]["stage_ref"] == stage_ref
    assert "client_key" not in planned["objects"][stage_ref]["data"]
    assert "stage_key" not in planned["objects"][chapter_ref]["data"]
    assert "stage" not in planned["objects"][chapter_ref]["data"]


def test_length_plan_rejects_unknown_stage_key(project):
    with pytest.raises(model_ops.ProjectModelError, match="未知或非活动阶段"):
        model_ops.set_length_plan(
            project["project_id"], base_model_rev=0,
            stages=[{"client_key": "stage-a", "title": "第一卷", "target_words": 50000}],
            chapter_targets=[
                {"title": "第1章", "chapter_number": 1, "min_words": 2500, "max_words": 4000, "stage_key": "missing"},
            ],
        )


def test_length_plan_preserves_stage_ref_across_stage_rename(project):
    planned = model_ops.set_length_plan(
        project["project_id"], base_model_rev=0,
        stages=[{"client_key": "stage-a", "title": "第一卷", "target_words": 50000}],
        chapter_targets=[
            {"title": "第1章", "chapter_number": 1, "min_words": 2500, "max_words": 4000, "stage_key": "stage-a"},
        ],
    )
    stage_ref = planned["length_plan"]["stage_refs"][0]
    chapter_ref = planned["length_plan"]["chapter_target_refs"][0]
    renamed = model_ops.set_length_plan(
        project["project_id"], base_model_rev=planned["model_rev"],
        stages=[{"ref": stage_ref, "title": "第一部", "target_words": 52000}],
        chapter_targets=[{"ref": chapter_ref}],
    )
    assert renamed["objects"][chapter_ref]["data"]["stage_ref"] == stage_ref
    assert renamed["objects"][stage_ref]["title"] == "第一部"


def test_length_plan_stage_removal_requires_chapter_reassignment(project):
    planned = model_ops.set_length_plan(
        project["project_id"], base_model_rev=0,
        stages=[{"client_key": "stage-a", "title": "第一卷", "target_words": 50000}],
        chapter_targets=[
            {"title": "第1章", "chapter_number": 1, "min_words": 2500, "max_words": 4000, "stage_key": "stage-a"},
        ],
    )
    stage_ref = planned["length_plan"]["stage_refs"][0]
    chapter_ref = planned["length_plan"]["chapter_target_refs"][0]
    with pytest.raises(model_ops.ProjectModelError, match="不能删除仍被章节规划引用的阶段"):
        model_ops.set_length_plan(project["project_id"], base_model_rev=planned["model_rev"], stages=[])
    assert model_ops.load_project_model(project["project_id"])["objects"][stage_ref]["tombstoned"] is False

    reassigned = model_ops.set_length_plan(
        project["project_id"], base_model_rev=planned["model_rev"],
        stages=[],
        chapter_targets=[{"ref": chapter_ref, "stage_key": None}],
    )
    assert reassigned["objects"][stage_ref]["tombstoned"] is True
    assert "stage_ref" not in reassigned["objects"][chapter_ref]["data"]


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


def test_v2_authority_artifact_migrates_additively(project):
    written = _add_character(project, title="迁移人物")
    ref = written["change_history"][-1]["detail"]["ref"]
    artifact = Path(project["project_dir"]) / "_工作台状态" / model_ops.ARTIFACT_NAME
    legacy = json.loads(artifact.read_text(encoding="utf-8"))
    legacy["schema_version"] = "gowrite_project_model/v2"
    legacy["objects"][ref].pop("field_authority", None)
    artifact.write_text(json.dumps(legacy, ensure_ascii=False, indent=2), encoding="utf-8")
    migrated = model_ops.load_project_model(project["project_id"])
    assert migrated["schema_version"] == model_ops.SCHEMA_VERSION
    assert migrated["objects"][ref]["field_authority"]["note"] == {
        "source": "author", "scope": "stable", "updated_model_rev": migrated["model_rev"],
    }
    assert json.loads(artifact.read_text(encoding="utf-8"))["schema_version"] == model_ops.SCHEMA_VERSION


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


def _two_stage_two_chapter_plan(project):
    return model_ops.set_length_plan(
        project["project_id"], base_model_rev=model_ops.load_project_model(project["project_id"])["model_rev"],
        stages=[
            {"name": "第一幕", "target_words": 50000},
            {"name": "第二幕", "target_words": 60000},
        ],
        chapter_targets=[
            {"label": "第001章", "min_words": 2500, "max_words": 3500},
            {"label": "第002章", "min_words": 2800, "max_words": 3800},
        ],
    )


def test_length_plan_edits_and_reordering_preserve_existing_refs(project):
    planned = _two_stage_two_chapter_plan(project)
    stages = planned["length_plan"]["stage_refs"]
    chapters = planned["length_plan"]["chapter_target_refs"]
    edited = model_ops.set_length_plan(
        project["project_id"], base_model_rev=planned["model_rev"],
        stages=[{"ref": stages[1]}, {"ref": stages[0], "title": "开篇", "target_words": 52000}],
        chapter_targets=[
            {"ref": chapters[1]},
            {"ref": chapters[0], "min_words": 2600, "max_words": 3600},
        ],
    )
    assert edited["length_plan"]["stage_refs"] == [stages[1], stages[0]]
    assert edited["length_plan"]["chapter_target_refs"] == [chapters[1], chapters[0]]
    assert edited["objects"][stages[0]]["title"] == "开篇"
    assert edited["objects"][stages[0]]["data"]["target_words"] == 52000
    assert edited["objects"][chapters[0]]["data"] == {"min_words": 2600, "max_words": 3600}
    history = edited["change_history"][-1]["detail"]["changed"]
    stage_update = next(item for item in history["stages"]["objects"] if item["ref"] == stages[0])
    assert stage_update["changes"]["title"] == {"before": "第一幕", "after": "开篇"}
    assert stage_update["changes"]["data"]["before"]["target_words"] == 50000
    assert stage_update["changes"]["data"]["after"]["target_words"] == 52000


def test_length_plan_add_and_remove_tombstones_without_ref_reuse(project):
    planned = _two_stage_two_chapter_plan(project)
    old_stages = planned["length_plan"]["stage_refs"]
    updated = model_ops.set_length_plan(
        project["project_id"], base_model_rev=planned["model_rev"],
        stages=[{"ref": old_stages[0]}, {"name": "新增幕", "target_words": 30000}],
    )
    new_stages = updated["length_plan"]["stage_refs"]
    assert new_stages[0] == old_stages[0]
    assert new_stages[1] not in old_stages
    assert updated["objects"][old_stages[1]]["tombstoned"] is True
    later = model_ops.set_length_plan(
        project["project_id"], base_model_rev=updated["model_rev"],
        stages=[{"ref": new_stages[0]}, {"ref": new_stages[1]}, {"name": "再新增", "target_words": 20000}],
    )
    assert later["length_plan"]["stage_refs"][-1] not in {*old_stages, *new_stages}


def test_chapter_actual_counts_follow_active_chapter_refs(project):
    planned = _two_stage_two_chapter_plan(project)
    chapters = planned["length_plan"]["chapter_target_refs"]
    counted = model_ops.set_length_plan(
        project["project_id"], base_model_rev=planned["model_rev"],
        actual_word_counts={chapters[0]: 3000, chapters[1]: 3200},
    )
    removed = model_ops.set_length_plan(
        project["project_id"], base_model_rev=counted["model_rev"], chapter_targets=[{"ref": chapters[1]}],
    )
    assert removed["objects"][chapters[0]]["tombstoned"] is True
    assert removed["length_plan"]["actual_word_counts"] == {chapters[1]: 3200}
    assert model_ops.load_project_model(project["project_id"])["length_plan"]["actual_word_counts"] == {chapters[1]: 3200}
    with pytest.raises(model_ops.ProjectModelError, match="最终活动"):
        model_ops.set_length_plan(
            project["project_id"], base_model_rev=removed["model_rev"], actual_word_counts={chapters[0]: 3000},
        )


def test_failed_final_validation_preserves_artifact_bytes(project):
    planned = _two_stage_two_chapter_plan(project)
    stage_ref = planned["length_plan"]["stage_refs"][0]
    artifact = Path(project["project_dir"]) / "_工作台状态" / model_ops.ARTIFACT_NAME
    before = artifact.read_bytes()
    with pytest.raises(model_ops.ProjectModelError, match="阶段 ref"):
        model_ops.tombstone_object(project["project_id"], base_model_rev=planned["model_rev"], ref=stage_ref)
    assert artifact.read_bytes() == before
    assert model_ops.load_project_model(project["project_id"])["objects"][stage_ref]["tombstoned"] is False


def test_object_tombstone_retires_incident_dependency_edges(project):
    source = _add_character(project, title="人物")
    source_ref = source["change_history"][-1]["detail"]["ref"]
    target = model_ops.create_foundation_record(
        project["project_id"], base_model_rev=source["model_rev"], category="story_line", title="主线",
    )
    target_ref = target["change_history"][-1]["detail"]["ref"]
    edged = model_ops.add_dependency(
        project["project_id"], base_model_rev=target["model_rev"], source_ref=source_ref,
        target_ref=target_ref, relation_kind="motivates",
    )
    edge_ref = edged["change_history"][-1]["detail"]["ref"]
    retired = model_ops.tombstone_object(
        project["project_id"], base_model_rev=edged["model_rev"], ref=source_ref,
    )
    assert retired["dependencies"][edge_ref]["tombstoned"] is True
    assert retired["dependencies"][edge_ref]["tombstoned_at_rev"] == retired["model_rev"]
    assert retired["change_history"][-1]["detail"]["retired_dependency_refs"] == [edge_ref]
    assert model_ops.list_direct_dependencies(project["project_id"], target_ref) == []


def test_total_target_words_can_be_explicitly_cleared(project):
    planned = model_ops.set_length_plan(
        project["project_id"], base_model_rev=0, total_target_words=180000,
    )
    cleared = model_ops.set_length_plan(
        project["project_id"], base_model_rev=planned["model_rev"], total_target_words=None,
    )
    assert cleared["length_plan"]["total_target_words"] is None


# ---------------------------------------------------------------------------
# 规划投影 domain_relations 合同（future / confirmed_plan；不按标题猜；失败整体回滚）
# ---------------------------------------------------------------------------

def test_planning_projection_domain_relations_validator_contract(project):
    valid = model_ops.validate_planning_projection({
        "domain_relations": [
            {"relation_kind": "storyline_involves_character", "source_key": "line_1", "target_key": "char_1"},
            {"relation_kind": "character_uses_system", "source_ref": "gw2_ref_a", "target_ref": "gw2_ref_b"},
        ],
    })
    assert len(valid["domain_relations"]) == 2
    assert valid["domain_relations"][0]["source_key"] == "line_1"
    with pytest.raises(model_ops.ProjectModelError, match="不支持"):
        model_ops.validate_planning_projection({
            "domain_relations": [
                {"relation_kind": "freeform_link", "source_key": "a", "target_key": "b"},
            ],
        })
    with pytest.raises(model_ops.ProjectModelError, match="明确的 key 或 ref"):
        model_ops.validate_planning_projection({
            "domain_relations": [
                {"relation_kind": "storyline_involves_character", "source_key": "line_1", "target_title": "人名"},
            ],
        })
    with pytest.raises(model_ops.ProjectModelError, match="重复"):
        model_ops.validate_planning_projection({
            "domain_relations": [
                {"relation_kind": "storyline_involves_character", "source_key": "line_1", "target_key": "char_1"},
                {"relation_kind": "storyline_involves_character", "source_key": "line_1", "target_key": "char_1"},
            ],
        })


def test_apply_planning_projection_domain_relations_future_confirmed_plan(project):
    projected = model_ops.apply_planning_projection(
        project["project_id"], base_model_rev=0, source_ref="decision:plan-rel",
        projection={
            "characters": [{"key": "char_1", "title": "规划人物"}],
            "organizations": [{"key": "org_1", "title": "规划组织"}],
            "storylines": [{"key": "line_1", "title": "规划故事线"}],
            "domain_relations": [
                {"relation_kind": "character_affiliated_with_organization",
                 "source_key": "char_1", "target_key": "org_1"},
                {"relation_kind": "storyline_involves_character",
                 "source_key": "line_1", "target_key": "char_1"},
            ],
        },
    )
    edges = [edge for edge in projected["dependencies"].values() if not edge.get("tombstoned")]
    assert {edge["relation_kind"] for edge in edges} == {
        "character_affiliated_with_organization", "storyline_involves_character",
    }
    for edge in edges:
        # 规划关系永远是 future，不是当前 Canon；权威 = confirmed_plan；携带规划来源。
        assert edge["material_state"] == "future"
        assert edge["data"]["planning_source_ref"] == "decision:plan-rel"
        assert all(meta["source"] == "confirmed_plan" for meta in edge["field_authority"].values())
        assert edge["author_fields"] == []


def test_apply_planning_projection_invalid_relation_fails_whole_projection(project):
    base = model_ops.load_project_model(project["project_id"])
    with pytest.raises(model_ops.ProjectModelError, match="终点类型"):
        model_ops.apply_planning_projection(
            project["project_id"], base_model_rev=base["model_rev"], source_ref="decision:plan-bad",
            projection={
                "characters": [{"key": "char_1", "title": "规划人物"}],
                "locations": [{"key": "loc_1", "title": "规划地点"}],
                "domain_relations": [
                    {"relation_kind": "character_uses_system",
                     "source_key": "char_1", "target_key": "loc_1"},
                ],
            },
        )
    # 整体失败：对象与关系都未部分落盘（同一 _commit 原子写）。
    assert model_ops.load_project_model(project["project_id"]) == base
    # 未知投影键 / 外部 ref → 同样整体失败，不按标题猜。
    with pytest.raises(model_ops.ProjectModelError, match="本投影键或明确同项目 ref"):
        model_ops.apply_planning_projection(
            project["project_id"], base_model_rev=base["model_rev"], source_ref="decision:plan-bad2",
            projection={
                "characters": [{"key": "char_1", "title": "规划人物"}],
                "organizations": [{"key": "org_1", "title": "规划组织"}],
                "domain_relations": [
                    {"relation_kind": "character_affiliated_with_organization",
                     "source_key": "char_1", "target_key": "ghost_key"},
                ],
            },
        )
    with pytest.raises(model_ops.ProjectModelError, match="跨项目"):
        model_ops.apply_planning_projection(
            project["project_id"], base_model_rev=base["model_rev"], source_ref="decision:plan-bad3",
            projection={
                "characters": [{"key": "char_1", "title": "规划人物"}],
                "domain_relations": [
                    {"relation_kind": "character_affiliated_with_organization",
                     "source_key": "char_1", "target_ref": "gw2_obj_foreign_00000001"},
                ],
            },
        )
    assert model_ops.load_project_model(project["project_id"]) == base


def test_apply_planning_projection_duplicate_relation_fails_closed(project):
    first = model_ops.apply_planning_projection(
        project["project_id"], base_model_rev=0, source_ref="decision:plan-dup-1",
        projection={
            "characters": [{"key": "char_1", "title": "规划人物"}],
            "organizations": [{"key": "org_1", "title": "规划组织"}],
            "domain_relations": [
                {"relation_kind": "character_affiliated_with_organization",
                 "source_key": "char_1", "target_key": "org_1"},
            ],
        },
    )
    char_ref = next(ref for ref, obj in first["objects"].items() if obj["title"] == "规划人物")
    org_ref = next(ref for ref, obj in first["objects"].items() if obj["title"] == "规划组织")
    with pytest.raises(model_ops.ProjectModelError, match="重复"):
        model_ops.apply_planning_projection(
            project["project_id"], base_model_rev=first["model_rev"], source_ref="decision:plan-dup-2",
            projection={
                "domain_relations": [
                    {"relation_kind": "character_affiliated_with_organization",
                     "source_ref": char_ref, "target_ref": org_ref},
                ],
            },
        )
    edges = [e for e in model_ops.load_project_model(project["project_id"])["dependencies"].values()
             if not e.get("tombstoned")]
    assert len(edges) == 1
