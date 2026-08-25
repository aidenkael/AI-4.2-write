# -*- coding: utf-8 -*-
"""作品资料 / 故事地图 只读投影 targeted tests：精确投影、零写、零模型、不编造。"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "05_Skills与自动化" / "01_Skills" / "ProjectWorkspace"))

import project_workspace  # noqa: E402

from operations import project_data as pd_ops  # noqa: E402


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    projects_root = tmp_path / "03_作品工程"
    projects_root.mkdir()
    monkeypatch.setattr(project_workspace, "get_projects_root", lambda: projects_root)
    return projects_root


@pytest.fixture()
def real_project(isolated):
    from project_workspace import create_project
    created = create_project(name="投影作品", author_intent={
        "work_direction": "方向",
        "reader_promise": "期待",
        "hard_constraints": [],
        "open_space": [],
    })
    project_dir = Path(created["project_dir"])
    project_id = created["project_id"]

    state_file = project_dir / "_工作台状态" / "story_state.json"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["character_state"] = [
        {"id": "c1", "name": "林砚", "note": "主角", "authority": "author_decision:test"},
        {"id": "c2", "name": "苏晚晴", "note": "协助者", "authority": "author_decision:test"},
    ]
    state["relationship_state"] = [
        {"id": "r1", "description": "林砚与苏晚晴是旧识", "targets": ["c1", "c2"], "authority": "author_decision:test"},
    ]
    state["canon_facts"] = [
        {"id": "f1", "fact": "故事发生在雾城", "authority": "author_decision:test"},
    ]
    state["occurred_events"] = [
        {"id": "e1", "description": "主角收到匿名照片", "authority": "author_decision:test"},
    ]
    state["open_threads"] = [
        {"id": "t1", "description": "照片背面的署名尚未解读", "authority": "author_decision:test"},
    ]
    state["approved_plan"] = [
        {"id": f"plan-{project_id}", "description": "故事发动机", "target_ref": "x",
         "authority": "author_decision:d", "occurred": False, "kind": "confirmed_direction"},
    ]
    state["state_rev"] = 2
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"project_id": project_id, "name": "投影作品", "project_dir": project_dir}


def test_projection_exact(real_project):
    data = pd_ops.get_project_data(real_project["project_id"])
    assert data["project_id"] == real_project["project_id"]
    assert data["name"] == "投影作品"
    sections = data["sections"]
    assert [e["label"] for e in sections["characters"]] == ["林砚", "苏晚晴"]
    assert [e["label"] for e in sections["relationships"]] == ["林砚与苏晚晴是旧识"]
    assert [e["label"] for e in sections["canon_facts"]] == ["故事发生在雾城"]
    assert [e["label"] for e in sections["occurred_events"]] == ["主角收到匿名照片"]
    assert [e["label"] for e in sections["open_threads"]] == ["照片背面的署名尚未解读"]
    assert [e["label"] for e in sections["approved_plan"]] == ["故事发动机"]


def test_zero_write(real_project):
    state_file = real_project["project_dir"] / "_工作台状态" / "story_state.json"
    before = state_file.read_bytes()
    pd_ops.get_project_data(real_project["project_id"])
    after = state_file.read_bytes()
    assert before == after, "只读投影不得写回 Story State"


def test_empty_state_ok(isolated):
    from project_workspace import create_project
    created = create_project(name="空作品", author_intent={
        "work_direction": "方向", "reader_promise": "期待",
        "hard_constraints": [], "open_space": [],
    })
    data = pd_ops.get_project_data(created["project_id"])
    for section in data["sections"].values():
        assert section == [], "空 State 各分区应为空，不编造条目"


def test_missing_project_rejected():
    with pytest.raises(pd_ops.ProjectDataError):
        pd_ops.get_project_data("")


def test_no_fabricated_entries(real_project):
    """投影只含真实条目，绝不从正文/凭空推断新人物或关系。"""
    data = pd_ops.get_project_data(real_project["project_id"])
    characters = data["sections"]["characters"]
    assert len(characters) == 2  # 只有 State 里真实存在的 2 个
    labels = {c["label"] for c in characters}
    assert labels == {"林砚", "苏晚晴"}
