# -*- coding: utf-8 -*-
"""Focused tests: explicit cross-domain relations stored in ProjectModel.dependencies.

所有断言均为确定性合同验证；零模型 / 零 Agent / 零真实作品。
"""
import json
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


def _create(name: str = "领域关系"):
    return project_workspace.create_project(name=name, author_intent={
        "work_direction": "测试方向", "reader_promise": "测试期待",
        "hard_constraints": [], "open_space": [],
    })


def _rev(project_id: str) -> int:
    return project_model.load_project_model(project_id)["model_rev"]


def _record(project_id: str, category: str, title: str, *, state: str = "current", data=None):
    model = project_model.create_foundation_record(
        project_id, base_model_rev=_rev(project_id), category=category, title=title,
        material_state=state, data=data or {},
    )
    return model["change_history"][-1]["detail"]["ref"]


def _system(project_id: str, title: str, *, state: str = "current"):
    model = project_model.create_system(
        project_id, base_model_rev=_rev(project_id), title=title,
        material_state=state, definition={"type": "custom"},
    )
    return model["change_history"][-1]["detail"]["ref"]


def _full_fixture(project_id: str) -> dict[str, str]:
    return {
        "character": _record(project_id, "character", "林渊"),
        "organization": _record(project_id, "organization_force", "玄天宗"),
        "system": _system(project_id, "玄灵境界"),
        "story_line": _record(project_id, "story_line", "主线一", state="future"),
        "location": _record(project_id, "location", "北境"),
        "world": _record(project_id, "world_setting", "灵气规则"),
        "foreshadow": _record(project_id, "promise_foreshadowing", "旧玉佩"),
        "mystery": _record(project_id, "mystery_information", "失踪真相"),
    }


def _active_edges(project_id: str) -> list[dict]:
    model = project_model.load_project_model(project_id)
    return [edge for edge in model["dependencies"].values() if not edge.get("tombstoned")]


def test_each_approved_relation_kind_accepts_valid_endpoints(projects_root):
    project = _create()
    pid = project["project_id"]
    fx = _full_fixture(pid)
    cases = [
        ("character_affiliated_with_organization", fx["character"], fx["organization"]),
        ("character_uses_system", fx["character"], fx["system"]),
        ("storyline_involves_character", fx["story_line"], fx["character"]),
        ("storyline_involves_organization", fx["story_line"], fx["organization"]),
        ("storyline_involves_location", fx["story_line"], fx["location"]),
        ("foreshadowing_related_to", fx["foreshadow"], fx["character"]),
        ("foreshadowing_related_to", fx["foreshadow"], fx["world"]),
        ("foreshadowing_related_to", fx["foreshadow"], fx["location"]),
        ("foreshadowing_related_to", fx["foreshadow"], fx["organization"]),
        ("foreshadowing_related_to", fx["foreshadow"], fx["system"]),
        ("foreshadowing_related_to", fx["foreshadow"], fx["story_line"]),
        ("mystery_information_related_to", fx["mystery"], fx["character"]),
        ("mystery_information_related_to", fx["mystery"], fx["system"]),
    ]
    for relation_kind, source, target in cases:
        project_model.add_domain_dependency(
            pid, base_model_rev=_rev(pid), source_ref=source, target_ref=target,
            relation_kind=relation_kind,
        )
    assert len(_active_edges(pid)) == len(cases)


def test_wrong_source_or_target_type_rejected(projects_root):
    project = _create()
    pid = project["project_id"]
    fx = _full_fixture(pid)
    with pytest.raises(project_model.ProjectModelError, match="起点类型"):
        project_model.add_domain_dependency(
            pid, base_model_rev=_rev(pid), source_ref=fx["organization"],
            target_ref=fx["character"], relation_kind="character_affiliated_with_organization",
        )
    with pytest.raises(project_model.ProjectModelError, match="终点类型"):
        project_model.add_domain_dependency(
            pid, base_model_rev=_rev(pid), source_ref=fx["character"],
            target_ref=fx["location"], relation_kind="character_affiliated_with_organization",
        )
    with pytest.raises(project_model.ProjectModelError, match="终点类型"):
        project_model.add_domain_dependency(
            pid, base_model_rev=_rev(pid), source_ref=fx["character"],
            target_ref=fx["organization"], relation_kind="character_uses_system",
        )
    with pytest.raises(project_model.ProjectModelError, match="不支持的领域关系类型"):
        project_model.add_domain_dependency(
            pid, base_model_rev=_rev(pid), source_ref=fx["character"],
            target_ref=fx["organization"], relation_kind="generic_free_form",
        )
    with pytest.raises(project_model.ProjectModelError, match="同一对象"):
        project_model.add_domain_dependency(
            pid, base_model_rev=_rev(pid), source_ref=fx["story_line"],
            target_ref=fx["story_line"], relation_kind="storyline_involves_character",
        )
    assert _active_edges(pid) == []


def test_cross_project_unknown_and_tombstoned_endpoints_rejected(projects_root):
    project = _create()
    other = _create("另一部作品")
    pid = project["project_id"]
    fx = _full_fixture(pid)
    foreign_ref = _record(other["project_id"], "organization_force", "外部组织")
    with pytest.raises(project_model.ProjectModelError, match="跨项目"):
        project_model.add_domain_dependency(
            pid, base_model_rev=_rev(pid), source_ref=fx["character"],
            target_ref=foreign_ref, relation_kind="character_affiliated_with_organization",
        )
    with pytest.raises(project_model.ProjectModelError, match="跨项目"):
        project_model.add_domain_dependency(
            pid, base_model_rev=_rev(pid), source_ref="gw2_obj_unknown_00000001",
            target_ref=fx["organization"], relation_kind="character_affiliated_with_organization",
        )
    project_model.tombstone_object(pid, base_model_rev=_rev(pid), ref=fx["organization"])
    with pytest.raises(project_model.ProjectModelError, match="tombstone"):
        project_model.add_domain_dependency(
            pid, base_model_rev=_rev(pid), source_ref=fx["character"],
            target_ref=fx["organization"], relation_kind="character_affiliated_with_organization",
        )
    assert _active_edges(pid) == []


def test_duplicate_active_relation_rejected_and_restore_keeps_same_ref(projects_root):
    project = _create()
    pid = project["project_id"]
    fx = _full_fixture(pid)
    created = project_model.add_domain_dependency(
        pid, base_model_rev=_rev(pid), source_ref=fx["character"],
        target_ref=fx["organization"], relation_kind="character_affiliated_with_organization",
    )
    edge_ref = created["change_history"][-1]["detail"]["ref"]
    with pytest.raises(project_model.ProjectModelError, match="已存在"):
        project_model.add_domain_dependency(
            pid, base_model_rev=_rev(pid), source_ref=fx["character"],
            target_ref=fx["organization"], relation_kind="character_affiliated_with_organization",
        )
    project_model.tombstone_dependency(pid, base_model_rev=_rev(pid), ref=edge_ref)
    restored = project_model.restore_dependency(pid, base_model_rev=_rev(pid), ref=edge_ref)
    assert restored["dependencies"][edge_ref]["tombstoned"] is False
    assert len(_active_edges(pid)) == 1


def test_create_record_with_relations_in_one_model_rev(projects_root):
    project = _create()
    pid = project["project_id"]
    org_ref = _record(pid, "organization_force", "玄天宗")
    sys_ref = _system(pid, "玄灵境界")
    created = project_model.create_foundation_record(
        pid, base_model_rev=_rev(pid), category="character", title="林渊",
        data={"one_line_intro": "外门弟子"},
        relations=[
            {"relation_kind": "character_affiliated_with_organization", "target_ref": org_ref},
            {"relation_kind": "character_uses_system", "target_ref": sys_ref},
        ],
    )
    char_ref = created["change_history"][-1]["detail"]["ref"]
    detail = created["change_history"][-1]["detail"]
    assert len(detail["relations"]["created"]) == 2
    edges = {
        (edge["relation_kind"], edge["target_ref"]): edge
        for edge in created["dependencies"].values() if not edge.get("tombstoned")
    }
    assert ("character_affiliated_with_organization", org_ref) in edges
    assert ("character_uses_system", sys_ref) in edges
    assert all(edge["source_ref"] == char_ref for edge in edges.values())
    # 单一原子写：磁盘工件与返回模型一致，且对象+关系只产生最后一条 change_history
    artifact = Path(project["project_dir"]) / "_工作台状态" / project_model.ARTIFACT_NAME
    assert json.loads(artifact.read_text(encoding="utf-8")) == created
    assert created["change_history"][-1]["kind"] == "foundation.created"
    assert created["change_history"][-1]["detail"]["relations"]["created"]


def test_update_data_and_relations_in_one_rev_and_relations_only_update(projects_root):
    project = _create()
    pid = project["project_id"]
    fx = _full_fixture(pid)
    updated = project_model.update_object(
        pid, base_model_rev=_rev(pid), ref=fx["character"],
        data={"one_line_intro": "外门弟子"},
        relations=[{"relation_kind": "character_affiliated_with_organization", "target_ref": fx["organization"]}],
    )
    detail = updated["change_history"][-1]["detail"]
    assert set(detail["changes"]) == {"data", "relations"}
    # relations-only update（对象数据不变）仍是合法更新
    rel_only = project_model.update_object(
        pid, base_model_rev=_rev(pid), ref=fx["character"],
        relations=[
            {"relation_kind": "character_affiliated_with_organization", "target_ref": fx["organization"]},
            {"relation_kind": "character_uses_system", "target_ref": fx["system"]},
        ],
    )
    assert set(rel_only["change_history"][-1]["detail"]["changes"]) == {"relations"}
    assert len(_active_edges(pid)) == 2
    # 对象与关系都未变化 → 保留既有“无实际变化”错误
    with pytest.raises(project_model.ProjectModelError, match="未产生任何实际变化"):
        project_model.update_object(
            pid, base_model_rev=_rev(pid), ref=fx["character"],
            relations=[
                {"relation_kind": "character_affiliated_with_organization", "target_ref": fx["organization"]},
                {"relation_kind": "character_uses_system", "target_ref": fx["system"]},
            ],
        )


def test_invalid_relation_rolls_back_entire_object_and_relation_mutation(projects_root):
    project = _create()
    pid = project["project_id"]
    fx = _full_fixture(pid)
    before = project_model.load_project_model(pid)
    with pytest.raises(project_model.ProjectModelError, match="终点类型"):
        project_model.update_object(
            pid, base_model_rev=_rev(pid), ref=fx["character"],
            data={"one_line_intro": "不应写入"},
            relations=[{"relation_kind": "character_uses_system", "target_ref": fx["organization"]}],
        )
    after = project_model.load_project_model(pid)
    assert after == before
    with pytest.raises(project_model.ProjectModelError, match="终点类型"):
        project_model.create_foundation_record(
            pid, base_model_rev=_rev(pid), category="character", title="新人",
            relations=[{"relation_kind": "character_uses_system", "target_ref": fx["organization"]}],
        )
    assert project_model.load_project_model(pid) == before


def test_removing_selected_relation_tombstones_only_managed_edge(projects_root):
    project = _create()
    pid = project["project_id"]
    fx = _full_fixture(pid)
    seeded = project_model.update_object(
        pid, base_model_rev=_rev(pid), ref=fx["character"],
        relations=[
            {"relation_kind": "character_affiliated_with_organization", "target_ref": fx["organization"]},
            {"relation_kind": "character_uses_system", "target_ref": fx["system"]},
        ],
    )
    kept_edge_refs = {
        edge["relation_kind"]: edge["ref"]
        for edge in seeded["dependencies"].values() if not edge.get("tombstoned")
    }
    # 再编辑：仅保留组织关系 → 体系边被 tombstone，组织边保留同一 ref
    trimmed = project_model.update_object(
        pid, base_model_rev=_rev(pid), ref=fx["character"],
        relations=[{"relation_kind": "character_affiliated_with_organization", "target_ref": fx["organization"]}],
    )
    assert trimmed["dependencies"][kept_edge_refs["character_affiliated_with_organization"]]["tombstoned"] is False
    assert trimmed["dependencies"][kept_edge_refs["character_uses_system"]]["tombstoned"] is True
    # 保留的边 data 未被显式提供时保持原样（稳定 ref + data 保持）
    assert trimmed["dependencies"][kept_edge_refs["character_affiliated_with_organization"]]["ref"] == (
        kept_edge_refs["character_affiliated_with_organization"]
    )


def test_reconciliation_never_touches_character_relationship_or_foreign_edges(projects_root):
    project = _create()
    pid = project["project_id"]
    fx = _full_fixture(pid)
    other_char = _record(pid, "character", "苏二")
    relationship = project_model.create_relationship(
        pid, base_model_rev=_rev(pid), source_ref=fx["character"], target_ref=other_char,
        label="同门",
    )
    rel_ref = relationship["change_history"][-1]["detail"]["ref"]
    storyline_edge = project_model.add_dependency(
        pid, base_model_rev=_rev(pid), source_ref=fx["story_line"],
        target_ref=fx["character"], relation_kind="storyline_involves_character",
    )
    story_edge_ref = storyline_edge["change_history"][-1]["detail"]["ref"]
    # 人物上的关系对账绝不触碰 character_relationship 与故事线为起点的边
    project_model.update_object(
        pid, base_model_rev=_rev(pid), ref=fx["character"],
        relations=[{"relation_kind": "character_affiliated_with_organization", "target_ref": fx["organization"]}],
    )
    model = project_model.load_project_model(pid)
    assert model["dependencies"][rel_ref]["tombstoned"] is False
    assert model["dependencies"][story_edge_ref]["tombstoned"] is False
    # 故事线对账也不触碰人物为起点的边
    project_model.update_object(
        pid, base_model_rev=_rev(pid), ref=fx["story_line"], relations=[],
    )
    model = project_model.load_project_model(pid)
    assert model["dependencies"][story_edge_ref]["tombstoned"] is True
    assert model["dependencies"][rel_ref]["tombstoned"] is False
    assert any(
        edge["relation_kind"] == "character_affiliated_with_organization" and not edge.get("tombstoned")
        for edge in model["dependencies"].values()
    )


def test_retiring_object_still_tombstones_all_incident_generic_dependencies(projects_root):
    project = _create()
    pid = project["project_id"]
    fx = _full_fixture(pid)
    project_model.update_object(
        pid, base_model_rev=_rev(pid), ref=fx["character"],
        relations=[{"relation_kind": "character_affiliated_with_organization", "target_ref": fx["organization"]}],
    )
    retired = project_model.tombstone_object(pid, base_model_rev=_rev(pid), ref=fx["character"])
    assert all(
        edge.get("tombstoned")
        for edge in retired["dependencies"].values()
        if edge["source_ref"] == fx["character"] or edge["target_ref"] == fx["character"]
    )
    assert retired["change_history"][-1]["detail"]["retired_dependency_refs"]


def test_snapshot_explicit_dependencies_projection(projects_root):
    project = _create()
    pid = project["project_id"]
    fx = _full_fixture(pid)
    project_model.update_object(
        pid, base_model_rev=_rev(pid), ref=fx["character"],
        relations=[
            {"relation_kind": "character_affiliated_with_organization", "target_ref": fx["organization"]},
            {"relation_kind": "character_uses_system", "target_ref": fx["system"]},
        ],
    )
    snapshot = project_snapshot.get_project_snapshot(pid)
    kinds = {(item["relation_kind"], item["source_title"], item["target_title"])
             for item in snapshot["explicit_dependencies"]}
    assert ("character_affiliated_with_organization", "林渊", "玄天宗") in kinds
    system_edge = next(
        item for item in snapshot["explicit_dependencies"]
        if item["relation_kind"] == "character_uses_system"
    )
    assert system_edge["target_category"] == "system"
    assert system_edge["source_category"] == "character"
    # tombstoned 边不出现
    edge_ref = next(
        edge["ref"] for edge in project_model.load_project_model(pid)["dependencies"].values()
        if edge["relation_kind"] == "character_uses_system"
    )
    model = project_model.load_project_model(pid)
    project_model.update_object(
        pid, base_model_rev=model["model_rev"], ref=fx["character"],
        relations=[{"relation_kind": "character_affiliated_with_organization", "target_ref": fx["organization"]}],
    )
    snapshot = project_snapshot.get_project_snapshot(pid)
    assert all(item["ref"] != edge_ref for item in snapshot["explicit_dependencies"])


def test_author_edit_relations_durable_ledger_and_zero_ai(projects_root, monkeypatch):
    project = _create()
    pid = project["project_id"]
    fx = _full_fixture(pid)
    created = author_edit.create_foundation_record(
        pid, base_model_rev=_rev(pid), category="character", title="沈决",
        material_state="current", data={},
        relations=[{"relation_kind": "character_affiliated_with_organization", "target_ref": fx["organization"]}],
    )
    assert created["change"]["status"] == "pending"
    assert created["change"]["requires_semantic"] is True
    char_ref = created["model"]["change_history"][-1]["detail"]["ref"]
    updated = author_edit.update_foundation_record(
        pid, base_model_rev=created["model"]["model_rev"], ref=char_ref,
        relations=[
            {"relation_kind": "character_affiliated_with_organization", "target_ref": fx["organization"]},
            {"relation_kind": "character_uses_system", "target_ref": fx["system"]},
        ],
    )
    assert updated["change"]["status"] == "pending"
    added = author_edit.create_domain_dependency(
        pid, base_model_rev=updated["model"]["model_rev"],
        source_ref=fx["story_line"], target_ref=char_ref,
        relation_kind="storyline_involves_character",
    )
    assert added["change"]["source_kind"] == "domain_relation_edit"
    assert added["change"]["status"] == "pending"
    # 零 AI / 零 Agent：账本变化全部由 Code 完成，未触发任何语义执行
    ledger = author_edit.get_change_ledger(pid)
    assert all(not item.get("settlement_started") for item in ledger["changes"])
    snapshot = project_snapshot.get_project_snapshot(pid)
    assert len(snapshot["explicit_dependencies"]) == 3


def test_author_edit_rejects_stale_rev_and_system_relations(projects_root):
    project = _create()
    pid = project["project_id"]
    fx = _full_fixture(pid)
    with pytest.raises(author_edit.AuthorEditError):
        author_edit.update_foundation_record(
            pid, base_model_rev=_rev(pid) + 5, ref=fx["character"],
            relations=[{"relation_kind": "character_uses_system", "target_ref": fx["system"]}],
        )
    with pytest.raises(author_edit.AuthorEditError, match="体系记录"):
        author_edit.update_foundation_record(
            pid, base_model_rev=_rev(pid), ref=fx["system"],
            relations=[{"relation_kind": "character_uses_system", "target_ref": fx["system"]}],
        )
