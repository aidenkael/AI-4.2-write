# -*- coding: utf-8 -*-
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "05_Skills与自动化" / "01_Skills" / "ProjectWorkspace"))

import project_workspace  # noqa: E402
from operations import project_model, project_snapshot  # noqa: E402


@pytest.fixture()
def project(tmp_path, monkeypatch):
    root = tmp_path / "03_作品工程"
    root.mkdir()
    monkeypatch.setattr(project_workspace, "get_projects_root", lambda: root)
    return project_workspace.create_project(name="统一快照", author_intent={
        "work_direction": "方向", "reader_promise": "期待", "hard_constraints": [], "open_space": [],
    })


def test_snapshot_is_read_only_and_project_isolated(project):
    artifact = Path(project["project_dir"]) / "_工作台状态" / project_model.ARTIFACT_NAME
    assert not artifact.exists()
    snapshot = project_snapshot.get_project_snapshot(project["project_id"])
    assert snapshot["project_id"] == project["project_id"]
    assert snapshot["model_rev"] == 0
    assert not artifact.exists(), "read-only snapshot must not lazily create a project-model artifact"
    with pytest.raises(project_snapshot.ProjectSnapshotError):
        project_snapshot.get_project_snapshot("proj_foreign")


def test_current_future_and_confirmed_projection_remain_distinct(project):
    current = project_model.create_foundation_record(
        project["project_id"], base_model_rev=0, category="character", title="当前人物",
        material_state="current", data={"role": "主角"},
    )
    projected = project_model.apply_planning_projection(
        project["project_id"], base_model_rev=current["model_rev"], source_ref="decision:test",
        projection={
            "characters": [{"key": "future", "title": "规划人物", "role": "对手"}],
            "relationships": [], "settings": [], "storylines": [], "events": [],
            "foreshadowing": [], "chapter_changes": [{
                "title": "第2章", "chapter_number": 2, "min_words": 2500, "max_words": 3500,
                "task": "引出对手", "previous_recap": "上一章结束", "synopsis": "初次交锋",
                "new_characters": ["规划人物"], "key_events": ["会面"],
                "foreshadowing": ["旧信"], "notes": "保持克制",
            }],
        },
    )
    snapshot = project_snapshot.get_project_snapshot(project["project_id"])
    assert [item["title"] for item in snapshot["current"]["characters"]] == ["当前人物"]
    assert [item["title"] for item in snapshot["future"]["characters"]] == ["规划人物"]
    chapter = next(item for item in snapshot["chapters"] if item["chapter_number"] == 2)
    assert chapter["actual_words"] == 0
    assert chapter["fine_outline"]["task"] == "引出对手"
    assert projected["objects"][chapter["fine_outline_ref"]]["material_state"] == "future"


def test_overlay_supersedes_raw_story_state_without_deleting_history(project):
    state_path = Path(project["project_dir"]) / "_工作台状态" / "story_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["character_state"] = [{"id": "c1", "name": "旧名", "authority": "author_decision:old"}]
    state["state_rev"] = 2
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    raw_ref = "story_state:character_state:c1"
    project_model.create_foundation_record(
        project["project_id"], base_model_rev=0, category="character", title="新名",
        material_state="current", data={"supersedes_state_ref": raw_ref, "role": "主角"},
    )
    snapshot = project_snapshot.get_project_snapshot(project["project_id"])
    assert [item["title"] for item in snapshot["current"]["characters"]] == ["新名"]
    assert json.loads(state_path.read_text(encoding="utf-8"))["character_state"][0]["name"] == "旧名"
    context = project_snapshot.focused_task_context(project["project_id"])
    assert [item["title"] for item in context["current"]["characters"]] == ["新名"]
    assert all(item["title"] != "旧名" for item in context["current"]["characters"])


def test_relationship_contract_has_exact_endpoints_and_future_status(project):
    one = project_model.create_foundation_record(
        project["project_id"], base_model_rev=0, category="character", title="甲", material_state="future",
    )
    one_ref = one["change_history"][-1]["detail"]["ref"]
    two = project_model.create_foundation_record(
        project["project_id"], base_model_rev=one["model_rev"], category="character", title="乙", material_state="future",
    )
    two_ref = two["change_history"][-1]["detail"]["ref"]
    related = project_model.create_relationship(
        project["project_id"], base_model_rev=two["model_rev"], source_ref=one_ref,
        target_ref=two_ref, label="旧识", material_state="future", data={"description": "互不信任"},
    )
    edge_ref = related["change_history"][-1]["detail"]["ref"]
    snapshot = project_snapshot.get_project_snapshot(project["project_id"])
    relation = snapshot["future"]["relationships"][0]
    assert relation["ref"] == edge_ref
    assert relation["record"]["source"] == one_ref
    assert relation["record"]["target"] == two_ref
    updated = project_model.update_dependency(
        project["project_id"], base_model_rev=related["model_rev"], ref=edge_ref, title="盟友",
    )
    retired = project_model.tombstone_dependency(
        project["project_id"], base_model_rev=updated["model_rev"], ref=edge_ref,
    )
    assert retired["dependencies"][edge_ref]["tombstoned"] is True
