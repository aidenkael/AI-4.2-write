# -*- coding: utf-8 -*-
"""Focused tests: bounded one-hop explicit-relation consumption in task context.

覆盖：直接种子解析（ref / 唯一精确标题 / 歧义不猜）、一跳扩展（不递归、
排序、封顶）、explicit_relations 形状、语义刷新 pending 时新关系仍可见、
规划 focus_text 行为、项目隔离，以及 Planning / Writing / Review 三个
消费者收到扩展上下文的最小集成断言。零真实模型调用。
"""
import hashlib
import json
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[3] / "05_Skills与自动化" / "01_Skills" / "ProjectWorkspace"),
)

import project_workspace  # noqa: E402
from operations import agent_runner  # noqa: E402
from operations import author_edit, project_data, project_model, project_snapshot  # noqa: E402
from operations import qoder_bridge as bridge  # noqa: E402
from operations import review as rv_ops  # noqa: E402
from operations import story_planning as sp_ops  # noqa: E402
from operations import story_writing as sw_ops  # noqa: E402
from agents.base import AgentRequest, AgentResult  # noqa: E402
from config.settings import AppSettings, SettingsStore  # noqa: E402


@pytest.fixture()
def projects_root(tmp_path, monkeypatch):
    root = tmp_path / "03_作品工程"
    root.mkdir()
    monkeypatch.setattr(project_workspace, "get_projects_root", lambda: root)
    return root


def _create(name: str = "上下文作品"):
    return project_workspace.create_project(name=name, author_intent={
        "work_direction": "测试方向", "reader_promise": "测试期待",
        "hard_constraints": [], "open_space": [],
    })


def _rev(pid: str) -> int:
    return project_model.load_project_model(pid)["model_rev"]


def _record(pid: str, category: str, title: str, *, state: str = "current"):
    model = project_model.create_foundation_record(
        pid, base_model_rev=_rev(pid), category=category, title=title, material_state=state,
    )
    return model["change_history"][-1]["detail"]["ref"]


def _chapter(pid: str, *, outline: dict):
    target = {"title": "第1章", "chapter_number": 1, "min_words": 100, "max_words": 200}
    target.update(outline)
    project_model.set_length_plan(pid, base_model_rev=_rev(pid), chapter_targets=[target])


def _titles(context: dict, bucket: str, section: str) -> list[str]:
    return [item["title"] for item in context[bucket].get(section, [])]


# ---------------------------------------------------------------------------
# 直接种子解析
# ---------------------------------------------------------------------------

def test_direct_ref_and_unique_title_select_exactly_one(projects_root):
    project = _create()
    pid = project["project_id"]
    lin = _record(pid, "character", "林渊")
    _record(pid, "character", "无关人物")
    _record(pid, "character", "同名")
    _record(pid, "character", "同名")
    _chapter(pid, outline={
        "participating_characters": [lin, "苏二", "同名"],
    })
    su = _record(pid, "character", "苏二")
    # 重新保存细纲（苏二在细纲之后创建，但标题唯一精确匹配仍应命中）
    _chapter(pid, outline={"participating_characters": [lin, "苏二", "同名"]})
    context = project_snapshot.focused_task_context(pid, chapter_number=1)
    assert set(_titles(context, "current", "characters")) == {"林渊", "苏二"}
    # 歧义标题不选任何记录（细纲原文仍属章节上下文，不参与记录选择）
    for bucket in ("current", "future"):
        assert all(item["title"] != "同名" for item in context[bucket]["characters"])


def test_ambiguous_title_is_not_guessed(projects_root):
    project = _create()
    pid = project["project_id"]
    _record(pid, "character", "同名")
    _record(pid, "character", "同名")
    _chapter(pid, outline={"participating_characters": ["同名"]})
    context = project_snapshot.focused_task_context(pid, chapter_number=1)
    assert _titles(context, "current", "characters") == []
    assert context["explicit_relations"] == []


def test_chapter_without_direct_entities_never_falls_back_to_state(projects_root):
    project = _create()
    pid = project["project_id"]
    _record(pid, "character", "无关人物甲")
    _record(pid, "character", "无关人物乙")
    _record(pid, "organization_force", "无关组织")
    _chapter(pid, outline={"task": "没有点名任何对象"})
    context = project_snapshot.focused_task_context(pid, chapter_number=1)
    assert _titles(context, "current", "characters") == []
    assert _titles(context, "current", "organizations") == []
    assert context["explicit_relations"] == []


# ---------------------------------------------------------------------------
# 一跳扩展
# ---------------------------------------------------------------------------

def _one_hop_fixture(pid: str) -> dict[str, str]:
    fx = {
        "lin": _record(pid, "character", "林渊"),
        "org": _record(pid, "organization_force", "玄天宗"),
        "line": _record(pid, "story_line", "主线一", state="future"),
        "loc": _record(pid, "location", "北境"),
    }
    project_model.update_object(
        pid, base_model_rev=_rev(pid), ref=fx["lin"],
        relations=[{"relation_kind": "character_affiliated_with_organization", "target_ref": fx["org"]}],
    )
    project_model.update_object(
        pid, base_model_rev=_rev(pid), ref=fx["line"],
        relations=[{"relation_kind": "storyline_involves_location", "target_ref": fx["loc"]}],
    )
    return fx


def test_one_hop_includes_opposite_endpoint_but_never_recurses(projects_root):
    project = _create()
    pid = project["project_id"]
    fx = _one_hop_fixture(pid)
    _chapter(pid, outline={"participating_characters": [fx["lin"]]})
    context = project_snapshot.focused_task_context(pid, chapter_number=1)
    assert "林渊" in _titles(context, "current", "characters")
    assert "玄天宗" in _titles(context, "current", "organizations")
    # 主线一 → 北境 与原始种子无关（林渊不是该边端点）→ 绝不扩展
    assert "北境" not in json.dumps(context, ensure_ascii=False)
    assert "主线一" not in json.dumps(context, ensure_ascii=False)
    kinds = {(item["relation_kind"], item["source_title"], item["target_title"])
             for item in context["explicit_relations"]}
    assert kinds == {("character_affiliated_with_organization", "林渊", "玄天宗")}


def test_two_seed_edge_ranks_before_incidental_edge(projects_root, monkeypatch):
    monkeypatch.setattr(project_snapshot, "_MAX_TASK_RELATION_EDGES", 1)
    project = _create()
    pid = project["project_id"]
    fx = _one_hop_fixture(pid)
    su = _record(pid, "character", "苏二")
    project_model.create_relationship(
        pid, base_model_rev=_rev(pid), source_ref=fx["lin"], target_ref=su, label="同门",
    )
    # 两个种子：林渊 + 苏二 → character_relationship 双端点种子优先
    _chapter(pid, outline={"participating_characters": [fx["lin"], su]})
    context = project_snapshot.focused_task_context(pid, chapter_number=1)
    assert len(context["explicit_relations"]) == 1
    assert context["explicit_relations"][0]["relation_kind"] == "character_relationship"
    # 选中的人物关系进入既有 relationships 分区
    assert "同门" in _titles(context, "current", "relationships")


def test_edge_cap_and_related_object_cap_are_enforced(projects_root, monkeypatch):
    project = _create()
    pid = project["project_id"]
    lin = _record(pid, "character", "林渊")
    org_refs = [
        _record(pid, "organization_force", f"组织{index}") for index in range(1, 5)
    ]
    project_model.update_object(
        pid, base_model_rev=_rev(pid), ref=lin,
        relations=[
            {"relation_kind": "character_affiliated_with_organization", "target_ref": ref}
            for ref in org_refs
        ],
    )
    _chapter(pid, outline={"participating_characters": [lin]})

    monkeypatch.setattr(project_snapshot, "_MAX_TASK_RELATION_EDGES", 2)
    context = project_snapshot.focused_task_context(pid, chapter_number=1)
    assert len(context["explicit_relations"]) == 2

    monkeypatch.setattr(project_snapshot, "_MAX_TASK_RELATION_EDGES", 16)
    monkeypatch.setattr(project_snapshot, "_MAX_TASK_RELATED_OBJECTS", 2)
    context = project_snapshot.focused_task_context(pid, chapter_number=1)
    assert len(context["explicit_relations"]) == 4
    assert len(_titles(context, "current", "organizations")) == 2


def test_future_material_state_preserved_and_pending_relation_visible(projects_root):
    project = _create()
    pid = project["project_id"]
    lin = _record(pid, "character", "林渊")
    future_org = _record(pid, "organization_force", "未来宗门", state="future")
    updated = author_edit.update_foundation_record(
        pid, base_model_rev=_rev(pid), ref=lin,
        relations=[{"relation_kind": "character_affiliated_with_organization", "target_ref": future_org}],
    )
    assert updated["change"]["status"] == "pending"  # 语义刷新待执行
    _chapter(pid, outline={"participating_characters": [lin]})
    # 即使语义刷新仍 pending，新作者关系立即可见
    context = project_snapshot.focused_task_context(pid, chapter_number=1)
    assert "未来宗门" in _titles(context, "future", "organizations")
    edge = context["explicit_relations"][0]
    assert edge["material_state"] == "future"
    assert edge["source_title"] == "林渊" and edge["target_title"] == "未来宗门"
    assert edge["source_category"] == "character" and edge["target_category"] == "organization_force"


def test_character_relationship_one_hop_keeps_authority_untouched(projects_root):
    project = _create()
    pid = project["project_id"]
    lin = _record(pid, "character", "林渊")
    su = _record(pid, "character", "苏二")
    created = project_model.create_relationship(
        pid, base_model_rev=_rev(pid), source_ref=lin, target_ref=su, label="旧识",
    )
    edge_ref = created["change_history"][-1]["detail"]["ref"]
    authority_before = created["dependencies"][edge_ref]["field_authority"]
    _chapter(pid, outline={"participating_characters": [lin]})
    context = project_snapshot.focused_task_context(pid, chapter_number=1)
    assert "苏二" in _titles(context, "current", "characters")
    assert "旧识" in _titles(context, "current", "relationships")
    model = project_model.load_project_model(pid)
    assert model["dependencies"][edge_ref]["field_authority"] == authority_before


def test_project_isolation_for_relation_context(projects_root):
    first = _create("甲作品")
    second = _create("乙作品")
    fx = _one_hop_fixture(first["project_id"])
    _chapter(first["project_id"], outline={"participating_characters": [fx["lin"]]})
    other_lin = _record(second["project_id"], "character", "林渊")
    _chapter(second["project_id"], outline={"participating_characters": [other_lin]})
    context = project_snapshot.focused_task_context(second["project_id"], chapter_number=1)
    assert context["explicit_relations"] == []
    assert "玄天宗" not in json.dumps(context, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 规划 focus_text
# ---------------------------------------------------------------------------

def test_planning_focus_text_unique_title_triggers_one_hop(projects_root):
    project = _create()
    pid = project["project_id"]
    fx = _one_hop_fixture(pid)
    context = project_snapshot.focused_task_context(pid, focus_text="林渊接下来该怎么走？")
    assert "玄天宗" in _titles(context, "current", "organizations")
    assert context["explicit_relations"]
    assert fx["org"] in {item["target_ref"] for item in context["explicit_relations"]}


def test_sparse_author_fields_system_level_and_stable_refs_reach_context(projects_root):
    """Core-only author data stays sparse while typed refs reach the task Context."""
    project = _create("稀疏地基闭环")
    pid = project["project_id"]

    organization = author_edit.create_foundation_record(
        pid, base_model_rev=_rev(pid), category="organization_force", title="巡护队",
        material_state="current", data={"purpose": "守护旧城"},
    )
    organization_ref = organization["model"]["change_history"][-1]["detail"]["ref"]
    system = author_edit.create_foundation_record(
        pid, base_model_rev=_rev(pid), category="system", title="巡护职级",
        material_state="current", data={"levels_stages": ["见习", "正式"]},
    )
    system_ref = system["model"]["change_history"][-1]["detail"]["ref"]
    core = {
        "one_line_intro": "守门人与线索保管者",
        "role_identity": "主角",
        "goal_desire": "找回失踪名册",
        "current_level": "见习",
    }
    created = author_edit.create_foundation_record(
        pid, base_model_rev=_rev(pid), category="character", title="林渊",
        material_state="current", data=core,
        relations=[
            {"relation_kind": "character_affiliated_with_organization", "target_ref": organization_ref},
            {"relation_kind": "character_uses_system", "target_ref": system_ref},
        ],
    )
    character_ref = created["model"]["change_history"][-1]["detail"]["ref"]
    assert created["change"]["status"] == "pending"

    updated_core = {**core, "current_level": "正式"}
    updated = author_edit.update_foundation_record(
        pid, base_model_rev=_rev(pid), ref=character_ref, data=updated_core,
    )
    assert updated["change"]["status"] == "pending"
    character = updated["model"]["objects"][character_ref]
    assert character["data"] == updated_core
    assert set(character["author_fields"]) == set(updated_core)
    assert all(meta["source"] == "author" for meta in character["field_authority"].values())
    assert "notes" not in character["data"] and "aliases" not in character["data"]

    data = project_data.get_project_data(pid)
    projected = next(item for item in data["sections"]["characters"] if item["source_ref"] == character_ref)
    assert projected["record"]["current_level"] == "正式"
    dependencies = {
        (item["relation_kind"], item["source_ref"], item["target_ref"])
        for item in data["explicit_dependencies"]
    }
    assert dependencies == {
        ("character_affiliated_with_organization", character_ref, organization_ref),
        ("character_uses_system", character_ref, system_ref),
    }

    context = project_snapshot.focused_task_context(pid, focus_text="林渊下一步如何行动？")
    context_character = next(item for item in context["current"]["characters"] if item["ref"] == character_ref)
    assert context_character["record"]["current_level"] == "正式"
    assert "notes" not in context_character["record"] and "aliases" not in context_character["record"]
    assert "巡护职级" in _titles(context, "current", "systems")
    assert "巡护队" in _titles(context, "current", "organizations")
    assert {item["relation_kind"] for item in context["explicit_relations"]} == {
        "character_affiliated_with_organization", "character_uses_system",
    }


def test_planning_without_matching_title_keeps_bounded_summary(projects_root):
    project = _create()
    pid = project["project_id"]
    for index in range(15):
        _record(pid, "character", f"人物{index}")
    _one_hop_fixture(pid)
    context = project_snapshot.focused_task_context(pid, focus_text="完全无关的问题")
    assert context["explicit_relations"] == []
    # 既有有界规划摘要：每分区截断，且不是空（不是全书 fallback，也不是全空）
    assert len(context["current"]["characters"]) == project_snapshot._MAX_TASK_RECORDS_PER_SECTION


def test_planning_duplicate_title_mention_is_not_seeded(projects_root):
    project = _create()
    pid = project["project_id"]
    lin = _record(pid, "character", "林渊")
    org = _record(pid, "organization_force", "玄天宗")
    project_model.update_object(
        pid, base_model_rev=_rev(pid), ref=lin,
        relations=[{"relation_kind": "character_affiliated_with_organization", "target_ref": org}],
    )
    _record(pid, "character", "同名")
    _record(pid, "character", "同名")
    # 歧义标题不成为种子 → 不触发一跳关系扩展（回到既有有界摘要行为）
    context = project_snapshot.focused_task_context(pid, focus_text="同名接下来怎么走")
    assert context["explicit_relations"] == []


# ---------------------------------------------------------------------------
# 消费者最小集成：Planning / Writing / Review 均收到扩展上下文
# ---------------------------------------------------------------------------

def _planning_project(tmp_path, monkeypatch):
    """带 confirmed_direction 的作品 + 隔离临时工作区（复用既有桥协议）。"""
    project = _create("规划集成")
    pid = project["project_id"]
    state_file = Path(project["project_dir"]) / "_工作台状态" / "story_state.json"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["approved_plan"].append({
        "id": f"plan-{pid}",
        "description": "故事发动机。",
        "target_ref": f"design-{pid}",
        "authority": f"author_decision:decision-{pid}",
        "occurred": False,
        "kind": "confirmed_direction",
    })
    state["state_rev"] = 2
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    monkeypatch.setattr(sp_ops, "get_planning_root", lambda: tmp_path / ".planning")
    monkeypatch.setattr(bridge, "get_bridge_root", lambda: tmp_path / ".bridge")
    monkeypatch.setattr(bridge, "focus_qoder_window", lambda: False)
    return project


def test_story_plan_task_receives_one_hop_relation_context(projects_root, tmp_path, monkeypatch):
    project = _planning_project(tmp_path, monkeypatch)
    pid = project["project_id"]
    fx = _one_hop_fixture(pid)
    prepared = sp_ops.prepare_story_plan(pid, "林渊的组织关系怎么发展？")
    request = bridge.get_request(prepared["request_id"])
    task = request["task"]
    assert "玄天宗" in task
    assert '"explicit_relations"' in task
    assert fx["org"] in task
    sp_ops.cancel_story_plan_request(prepared["request_id"])


def test_story_write_task_receives_one_hop_relation_context(projects_root, tmp_path, monkeypatch):
    project = _create("写作集成")
    pid = project["project_id"]
    monkeypatch.setattr(sw_ops, "get_writing_root", lambda: tmp_path / ".writing")
    monkeypatch.setattr(bridge, "get_bridge_root", lambda: tmp_path / ".bridge")
    monkeypatch.setattr(bridge, "focus_qoder_window", lambda: False)
    fx = _one_hop_fixture(pid)
    _chapter(pid, outline={"participating_characters": [fx["lin"]]})
    SettingsStore(config_dir=tmp_path / "cfg").save(
        AppSettings(default_execution_mode="interactive_bridge", interactive_agent="qoder"),
    )
    monkeypatch.setenv("AI_WRITE_CONFIG_DIR", str(tmp_path / "cfg"))
    prepared = sw_ops.prepare_story_write(project_id=pid, author_input="写第1章", chapter_number=1)
    request = bridge.get_request(prepared["request_id"])
    task = request["task"]
    assert "玄天宗" in task
    assert '"explicit_relations"' in task
    sw_ops.cancel_story_write_request(prepared["request_id"])


class _ReviewAdapter:
    name = "fake_review_agent_ctx"

    def __init__(self):
        self.calls = []
        self.done = threading.Event()

    def run(self, request):
        self.calls.append(request)
        output = json.dumps({
            "semantic_interpretation": {
                "objective": "检查。", "knowledge_needs": [], "selected_knowledge_refs": [],
                "package_ref": "", "assumptions": [],
            },
            "review": {"summary": "连贯。", "issues": [], "strengths": []},
        }, ensure_ascii=False)
        self.done.set()
        return AgentResult(status="completed", output=output, agent=self.name)

    def cancel(self):
        return True


def test_review_task_receives_one_hop_relation_context(projects_root, tmp_path, monkeypatch):
    from operations import execution_tasks

    project = _create("检查集成")
    pid = project["project_id"]
    monkeypatch.setattr(rv_ops, "get_review_root", lambda: tmp_path / ".review")
    monkeypatch.setattr(bridge, "get_bridge_root", lambda: tmp_path / ".bridge")
    monkeypatch.setattr(rv_ops, "_exec_task_manager", execution_tasks.ExecutionTaskManager())
    monkeypatch.setenv("AI_WRITE_CONFIG_DIR", str(tmp_path / "cfg"))

    # 已接受正文（review 只检查已接受章节）
    chapter_text = "林渊进入玄天宗山门。"
    (Path(project["project_dir"]) / "03_正文").mkdir(exist_ok=True)
    (Path(project["project_dir"]) / "03_正文" / "第001章.md").write_text(chapter_text, encoding="utf-8")
    index_path = Path(project["project_dir"]) / "_工作台状态" / "accepted_text_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["entries"].append({
        "chapter_number": 1, "chapter_path": "03_正文/第001章.md", "scene_ref": "scene-1",
        "sequence": 1, "start_char": 0, "end_char": len(chapter_text),
        "content_sha256": hashlib.sha256(chapter_text.encode("utf-8")).hexdigest(),
    })
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    fx = _one_hop_fixture(pid)
    _chapter(pid, outline={"participating_characters": [fx["lin"]]})

    adapter = _ReviewAdapter()
    SettingsStore().save(AppSettings(
        default_execution_mode="direct", interactive_agent="qoder",
        direct_agent=adapter.name, direct_model="native-model-1", direct_custom_model=None,
    ))
    monkeypatch.setattr(
        agent_runner, "_build_adapter",
        lambda: (adapter, AgentRequest(task="", model="native-model-1", custom_model=None)),
    )
    prepared = rv_ops.prepare_review(pid, chapter_number=1)
    rv_ops._exec_task_manager.join(prepared["request_id"], 5.0)
    assert adapter.calls, "Review 应执行一次检查任务"
    task = adapter.calls[0].task
    assert "玄天宗" in task
    assert '"explicit_relations"' in task
