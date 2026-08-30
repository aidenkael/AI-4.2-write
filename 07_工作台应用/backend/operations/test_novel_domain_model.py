# -*- coding: utf-8 -*-
"""Focused Go Write 2.0 Novel Domain Model closed-loop tests.

All semantic results are deterministic fixtures; no model/API call occurs.
"""
import hashlib
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
from operations import author_edit, change_settlement, project_model, project_snapshot  # noqa: E402


@pytest.fixture()
def projects_root(tmp_path, monkeypatch):
    root = tmp_path / "03_作品工程"
    root.mkdir()
    monkeypatch.setattr(project_workspace, "get_projects_root", lambda: root)
    return root


def _create(name: str):
    return project_workspace.create_project(name=name, author_intent={
        "work_direction": "人物在压力下作出选择",
        "reader_promise": "选择产生可追踪后果",
        "hard_constraints": [],
        "open_space": [],
    })


def _ref(model: dict) -> str:
    return model["change_history"][-1]["detail"]["ref"]


def test_profile_is_configuration_and_hiding_module_never_deletes_data(projects_root):
    project = _create("领域配置")
    profiled = project_model.set_story_bible_profile(
        project["project_id"], base_model_rev=0, genre_tags=["悬疑", "都市"],
        narrative_mode="第三人称限知", active_modules=["mystery_information"],
        field_config={"character": {"optional_fields": ["age_state"]}},
    )
    assert set(project_model.DEFAULT_DOMAIN_MODULES).issubset(
        profiled["story_bible_profile"]["active_modules"]
    )
    assert "mystery_information" in profiled["story_bible_profile"]["active_modules"]
    mystery = project_model.create_foundation_record(
        project["project_id"], base_model_rev=profiled["model_rev"],
        category="mystery_information", title="失踪者身份",
        data={"secret_fact": "身份尚未公开", "who_knows": ["调查者"]},
    )
    hidden = project_model.set_story_bible_profile(
        project["project_id"], base_model_rev=mystery["model_rev"], genre_tags=["悬疑"],
        narrative_mode=None, active_modules=[], field_config={},
    )
    mystery_ref = _ref(mystery)
    assert mystery_ref in hidden["objects"]
    assert hidden["objects"][mystery_ref]["tombstoned"] is False
    assert "mystery_information" not in hidden["story_bible_profile"]["active_modules"]


def test_character_core_optional_custom_fields_and_author_precedence(projects_root):
    project = _create("人物字段")
    created = project_model.create_foundation_record(
        project["project_id"], base_model_rev=0, category="character", title="林澈",
        data={
            "aliases": ["阿澈"], "one_line_intro": "谨慎的调查者",
            "role_identity": "主角", "current_state": "受伤",
            "power_rank": "普通人", "age_state": "二十多岁",
            "custom_lucky_token": "旧硬币",
        },
    )
    ref = _ref(created)
    patched = project_model.patch_object_data(
        project["project_id"], base_model_rev=created["model_rev"], ref=ref,
        patch={
            "one_line_intro": "AI 不得覆盖作者介绍",
            "current_state": "AI 不得覆盖作者状态",
            "speech_style": "短句，避免解释",
        },
    )
    data = patched["objects"][ref]["data"]
    assert data["one_line_intro"] == "谨慎的调查者"
    assert data["current_state"] == "受伤"
    assert data["speech_style"] == "短句，避免解释"
    detail = patched["change_history"][-1]["detail"]
    assert detail["applied_fields"] == ["speech_style"]
    assert detail["skipped_author_fields"] == ["current_state", "one_line_intro"]


def test_full_editor_payload_marks_only_changed_field_as_author(projects_root):
    project = _create("字段级权威")
    created = project_model.create_foundation_record(
        project["project_id"], base_model_rev=0, category="character", title="林澈",
        data={"one_line_intro": "调查者", "current_state": "平静", "speech_style": "短句"},
        field_authority="semantic",
    )
    ref = _ref(created)
    edited = project_model.update_object(
        project["project_id"], base_model_rev=created["model_rev"], ref=ref,
        data={"one_line_intro": "谨慎的调查者", "current_state": "平静", "speech_style": "短句"},
    )
    record = edited["objects"][ref]
    assert record["author_fields"] == ["one_line_intro"]
    assert record["field_authority"]["current_state"]["source"] == "semantic"
    changed = edited["change_history"][-1]["detail"]["changes"]["data"]["changed_fields"]
    assert changed == ["one_line_intro"]


def test_explicit_author_clear_remains_protected_for_same_change(projects_root):
    project = _create("显式清空")
    created = project_model.create_foundation_record(
        project["project_id"], base_model_rev=0, category="character", title="林澈",
        data={"secrets": "旧秘密", "current_state": "平静"}, field_authority="semantic",
    )
    ref = _ref(created)
    edited = project_model.update_object(
        project["project_id"], base_model_rev=created["model_rev"], ref=ref,
        data={"current_state": "平静"},
    )
    assert "secrets" in edited["objects"][ref]["author_fields"]
    with pytest.raises(project_model.ProjectModelError, match="未产生变化"):
        project_model.patch_object_data(
            project["project_id"], base_model_rev=edited["model_rev"], ref=ref,
            patch={"secrets": "AI 又补回"}, protect_author_model_rev=edited["model_rev"],
        )


def test_later_prose_may_advance_dynamic_but_not_stable_author_field(projects_root):
    project = _create("动态字段时序")
    created = project_model.create_foundation_record(
        project["project_id"], base_model_rev=0, category="character", title="林澈",
        data={"current_state": "未受伤", "persona_core": "谨慎"},
    )
    ref = _ref(created)
    patched = project_model.patch_object_data(
        project["project_id"], base_model_rev=created["model_rev"], ref=ref,
        patch={"current_state": "腿部受伤", "persona_core": "鲁莽"},
        allow_dynamic_author_override=True,
    )
    assert patched["objects"][ref]["data"]["current_state"] == "腿部受伤"
    assert patched["objects"][ref]["data"]["persona_core"] == "谨慎"
    assert patched["objects"][ref]["author_fields"] == ["persona_core"]


def test_relationship_full_payload_preserves_unchanged_semantic_authority(projects_root):
    project = _create("关系字段级权威")
    one = project_model.create_foundation_record(
        project["project_id"], base_model_rev=0, category="character", title="甲",
    )
    two = project_model.create_foundation_record(
        project["project_id"], base_model_rev=one["model_rev"], category="character", title="乙",
    )
    relation = project_model.create_relationship(
        project["project_id"], base_model_rev=two["model_rev"],
        source_ref=_ref(one), target_ref=_ref(two), label="盟友",
        data={"current_state": "合作", "key_history": "共同调查"}, field_authority="semantic",
    )
    ref = _ref(relation)
    edited = project_model.update_dependency(
        project["project_id"], base_model_rev=relation["model_rev"], ref=ref,
        data={"current_state": "互相怀疑", "key_history": "共同调查"},
    )
    assert edited["dependencies"][ref]["author_fields"] == ["current_state"]
    assert edited["dependencies"][ref]["field_authority"]["key_history"]["source"] == "semantic"


def test_legacy_state_sentence_is_diagnostic_not_character_identity(projects_root):
    project = _create("旧状态归一")
    state_path = Path(project["project_dir"]) / "_工作台状态" / "story_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["character_state"] = [
        {"id": "c1", "name": "林澈", "authority": "accepted_text:s1"},
        {"character_id": "c1", "description": "林澈现在受伤", "authority": "accepted_text:s2"},
        {"description": "他已经决定离开", "authority": "accepted_text:s2"},
    ]
    state["state_rev"] = 2
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    snapshot = project_snapshot.get_project_snapshot(project["project_id"])
    assert [item["title"] for item in snapshot["current"]["characters"]] == ["林澈"]
    observations = snapshot["current"]["characters"][0]["record"]["state_observations"]
    assert observations[0]["description"] == "林澈现在受伤"
    diagnostic = snapshot["legacy_diagnostics"]["unresolved_character_observations"]
    assert len(diagnostic) == 1
    assert diagnostic[0]["observation"]["description"] == "他已经决定离开"


def test_relationship_system_storyline_foreshadow_event_and_time_contract(projects_root):
    project = _create("领域对象")
    one = project_model.create_foundation_record(
        project["project_id"], base_model_rev=0, category="character", title="甲",
        data={"system_ref": "待绑定", "current_level": "学徒"},
    )
    two = project_model.create_foundation_record(
        project["project_id"], base_model_rev=one["model_rev"], category="character", title="乙",
    )
    system = project_model.create_system(
        project["project_id"], base_model_rev=two["model_rev"], title="调查员职级",
        definition={
            "type": "career_rank", "purpose": "定义权限",
            "levels_stages": ["学徒", "调查员"], "limitations_costs": "需接受审查",
        },
    )
    relation = project_model.create_relationship(
        project["project_id"], base_model_rev=system["model_rev"],
        source_ref=_ref(one), target_ref=_ref(two), label="互相试探",
        data={
            "current_state": "合作但不信任", "relationship_phase": "初次合作",
            "key_history": "共同进入封锁区", "current_tension": "隐瞒线索",
        },
    )
    storyline = project_model.create_foundation_record(
        project["project_id"], base_model_rev=relation["model_rev"],
        category="story_line", title="追查失踪案",
        data={"goal_purpose": "查明真相", "stakes": "证人安全", "stage_progress": "调查中"},
    )
    foreshadow = project_model.create_foundation_record(
        project["project_id"], base_model_rev=storyline["model_rev"],
        category="promise_foreshadowing", title="旧硬币",
        data={
            "setup_trigger": "现场出现旧硬币", "reader_question_promise": "硬币属于谁",
            "state": "planted/open", "intended_payoff": "身份揭示",
        },
    )
    event = project_model.create_foundation_record(
        project["project_id"], base_model_rev=foreshadow["model_rev"],
        category="event", title="进入封锁区",
        data={
            "participants": [_ref(one), _ref(two)], "what_happened": "两人进入封锁区",
            "relative_time_movement": "三小时后", "narrative_chapter_order": 2,
        },
    )
    snapshot = project_snapshot.get_project_snapshot(project["project_id"])
    assert len(snapshot["current"]["relationships"]) == 1
    assert len(snapshot["current"]["systems"]) == 1
    assert len(snapshot["current"]["storylines"]) == 1
    assert len(snapshot["current"]["foreshadowing"]) == 1
    assert snapshot["current"]["events"][0]["record"]["relative_time_movement"] == "三小时后"
    assert event["objects"][_ref(event)]["data"].get("story_time_anchor") is None


def test_time_arithmetic_requires_explicit_base_and_structured_duration(projects_root):
    unresolved = project_model.apply_deterministic_time_arithmetic({"relative_duration": "三小时后"})
    assert "computed_story_time_anchor" not in unresolved

    computed = project_model.apply_deterministic_time_arithmetic({
        "base_story_time_anchor": "2026-08-30T09:00:00+08:00",
        "relative_duration": {"value": 3, "unit": "hours"},
    })
    assert computed["computed_story_time_anchor"] == "2026-08-30T12:00:00+08:00"


def test_confirmed_plan_projection_creates_future_domains_from_same_result(projects_root):
    project = _create("规划投影")
    existing = project_model.create_foundation_record(
        project["project_id"], base_model_rev=0, category="character", title="现有人物",
    )
    existing_ref = _ref(existing)
    projected = project_model.apply_planning_projection(
        project["project_id"], base_model_rev=existing["model_rev"],
        source_ref="decision:plan-1",
        projection={
            "domain_profile": {"genre_tags": ["幻想"], "active_modules": ["supernatural_rules"]},
            "characters": [{"key": "new", "title": "规划人物", "one_line_intro": "未来盟友"}],
            "relationships": [{
                "source_ref": existing_ref, "target_key": "new", "label": "将成为盟友",
                "relationship_phase": "planned",
            }],
            "settings": [{"key": "world", "title": "浮空城", "hard_rules": "能源有限"}],
            "systems": [{"key": "rank", "title": "航行许可", "type": "technology_access"}],
            "locations": [{"key": "dock", "title": "北港", "type": "港口"}],
            "organizations": [{"key": "guild", "title": "领航公会", "purpose": "管理航线"}],
            "storylines": [{"key": "line", "title": "争夺航线", "stakes": "城市存续"}],
            "events": [{"key": "event", "title": "计划启航", "relative_time_movement": "三日后"}],
            "foreshadowing": [{"key": "promise", "title": "失效罗盘", "state": "planned"}],
            "mystery_information": [],
            "chapter_changes": [{
                "title": "第2章", "chapter_number": 2, "min_words": 2500, "max_words": 3500,
                "task": "启航", "pov": "规划人物", "key_beats": ["进入北港"],
            }],
        },
    )
    snapshot = project_snapshot.get_project_snapshot(project["project_id"])
    assert {item["title"] for item in snapshot["future"]["characters"]} == {"规划人物"}
    assert {item["title"] for item in snapshot["future"]["systems"]} == {"航行许可"}
    assert {item["title"] for item in snapshot["future"]["locations"]} == {"北港"}
    assert {item["title"] for item in snapshot["future"]["organizations"]} == {"领航公会"}
    assert snapshot["future"]["relationships"][0]["record"]["source"] == existing_ref
    assert all(
        item["material_state"] == "future"
        for item in projected["objects"].values()
        if not item.get("tombstoned") and item.get("ref") != existing_ref
    )
    assert all(
        all(meta["source"] == "confirmed_plan" for meta in item["field_authority"].values())
        for item in projected["objects"].values()
        if not item.get("tombstoned") and item.get("ref") != existing_ref
    )
    assert all(
        all(meta["source"] == "confirmed_plan" for meta in edge["field_authority"].values())
        for edge in projected["dependencies"].values()
        if not edge.get("tombstoned")
    )


def test_prose_settlement_writes_actual_result_and_targeted_entities(projects_root):
    project = _create("章节结果")
    character = project_model.create_foundation_record(
        project["project_id"], base_model_rev=0, category="character", title="林澈",
        data={"current_state": "作者明确：未受伤"},
    )
    character_ref = _ref(character)
    planned = project_model.set_length_plan(
        project["project_id"], base_model_rev=character["model_rev"],
        chapter_targets=[{
            "title": "第1章", "chapter_number": 1, "min_words": 1000, "max_words": 2000,
            "task": "进入封锁区", "participating_characters": [character_ref],
        }],
    )
    author_edit.create_chapter(project["project_id"], chapter_number=1)
    saved = author_edit.save_formal_prose(
        project["project_id"], chapter_number=1,
        base_content_sha256=hashlib.sha256(b"").hexdigest(),
        content="林澈拖着伤腿进入封锁区，决定继续调查。",
    )
    result = change_settlement.apply_semantic_result(
        project["project_id"], saved["change"]["change_id"], {
            "summary": "同步受影响人物与章节现实",
            "consequences": [{
                "classification": "mechanically_certain", "kind": "character", "action": "update",
                "target_ref": character_ref, "title": "林澈",
                "data": {
                    "current_state": "腿部受伤",
                    "current_objective": "继续调查",
                    "behavior_anchors": ["负伤仍继续前进"],
                },
                "reason": "正文明确",
            }],
            "chapter_actual_result": {
                "summary": "林澈负伤进入封锁区继续调查。",
                "important_events": ["进入封锁区"],
                "characters_involved": [character_ref],
                "character_state_changes": ["林澈腿部受伤"],
                "final_chapter_state": "调查继续",
                "outline_divergence": "主角以负伤状态进入",
            },
            "planning_impact_candidate": {
                "summary": "后续行动需考虑林澈腿伤",
                "affected_refs": [character_ref],
            },
        },
    )
    assert result["status"] == "synchronized"
    model = project_model.load_project_model(project["project_id"])
    data = model["objects"][character_ref]["data"]
    assert data["current_state"] == "腿部受伤"
    assert data["current_objective"] == "继续调查"
    assert model["chapter_actual_results"]["1"]["summary"].startswith("林澈负伤")
    chapter_ref = model["length_plan"]["chapter_target_refs"][0]
    assert model["length_plan"]["actual_word_counts"][chapter_ref] == len("林澈拖着伤腿进入封锁区，决定继续调查。")
    assert model["planning_impact_candidates"][0]["status"] == "pending_author"
    snapshot = project_snapshot.get_project_snapshot(project["project_id"])
    assert snapshot["chapters"][0]["fine_outline"]["task"] == "进入封锁区"
    assert snapshot["chapters"][0]["actual_result"]["outline_divergence"] == "主角以负伤状态进入"
    assert planned["objects"][chapter_ref]["data"].get("actual_result") is None


def test_meaningful_foundation_edit_pending_display_edit_mechanical(projects_root):
    project = _create("地基结算")
    created = author_edit.create_foundation_record(
        project["project_id"], base_model_rev=0, category="character", title="林澈",
        material_state="current", data={"one_line_intro": "调查者"},
    )
    assert created["change"]["status"] == "pending"
    ref = _ref(created["model"])
    display = author_edit.update_foundation_record(
        project["project_id"], base_model_rev=created["model"]["model_rev"], ref=ref,
        data={"one_line_intro": "调查者", "display_order": 2},
    )
    assert display["change"]["status"] == "synchronized"
    semantic = author_edit.update_foundation_record(
        project["project_id"], base_model_rev=display["model"]["model_rev"], ref=ref,
        data={"one_line_intro": "谨慎的调查者", "display_order": 2},
    )
    assert semantic["change"]["status"] == "pending"


def test_planning_stage_semantics_settle_but_word_budget_stays_mechanical(projects_root):
    project = _create("阶段结算")
    created = author_edit.set_length_plan(
        project["project_id"], base_model_rev=0, total_target_words=100_000,
        stages=[{"title": "第一卷", "target_words": 40_000, "kind": "调查"}],
        chapter_targets=[],
    )
    assert created["change"]["status"] == "pending"
    stage_ref = created["model"]["length_plan"]["stage_refs"][0]
    budget_only = author_edit.set_length_plan(
        project["project_id"], base_model_rev=created["model"]["model_rev"],
        total_target_words=120_000,
        stages=[{"ref": stage_ref, "title": "第一卷", "target_words": 50_000, "kind": "调查"}],
        chapter_targets=[],
    )
    assert budget_only["change"]["status"] == "synchronized"


def test_existing_system_edit_and_retire_require_semantic_settlement(projects_root):
    project = _create("系统结算")
    created = author_edit.create_foundation_record(
        project["project_id"], base_model_rev=0, category="system", title="航行许可",
        material_state="current", data={"type": "technology_access"},
    )
    ref = _ref(created["model"])
    edited = author_edit.update_foundation_record(
        project["project_id"], base_model_rev=created["model"]["model_rev"], ref=ref,
        data={"type": "technology_access", "limitations_costs": "燃料有限"},
    )
    assert edited["change"]["status"] == "pending"
    display = author_edit.update_foundation_record(
        project["project_id"], base_model_rev=edited["model"]["model_rev"], ref=ref,
        data={"type": "technology_access", "limitations_costs": "燃料有限", "display_order": 2},
    )
    assert display["change"]["status"] == "synchronized"
    retired = author_edit.retire_foundation_record(
        project["project_id"], base_model_rev=display["model"]["model_rev"], ref=ref,
    )
    assert retired["change"]["status"] == "pending"


def test_writing_context_uses_outline_previous_digest_and_relevant_state_only(projects_root):
    project = _create("长篇上下文")
    relevant = project_model.create_foundation_record(
        project["project_id"], base_model_rev=0, category="character", title="相关人物",
    )
    relevant_ref = _ref(relevant)
    unrelated = project_model.create_foundation_record(
        project["project_id"], base_model_rev=relevant["model_rev"],
        category="character", title="无关人物",
    )
    plan = project_model.set_length_plan(
        project["project_id"], base_model_rev=unrelated["model_rev"],
        chapter_targets=[
            {"title": "第1章", "chapter_number": 1, "min_words": 100, "max_words": 200},
            {
                "title": "第2章", "chapter_number": 2, "min_words": 100, "max_words": 200,
                "task": "相关人物作出选择", "participating_characters": [relevant_ref],
            },
        ],
    )
    model = project_model.set_chapter_actual_result(
        project["project_id"], base_model_rev=plan["model_rev"], chapter_number=1,
        result={"summary": "上一章实际发生了冲突。"},
        content_sha256=hashlib.sha256(b"chapter one").hexdigest(),
        source_change_id="change-test", actual_word_count=11,
    )
    context = project_snapshot.focused_task_context(project["project_id"], chapter_number=2)
    assert context["chapter"]["fine_outline"]["task"] == "相关人物作出选择"
    assert context["chapter"]["previous_actual_result"]["summary"] == "上一章实际发生了冲突。"
    assert [item["title"] for item in context["current"]["characters"]] == ["相关人物"]
    assert "无关人物" not in json.dumps(context, ensure_ascii=False)
    assert model["project_id"] == project["project_id"]


def test_domain_model_project_isolation(projects_root):
    first = _create("甲项目")
    second = _create("乙项目")
    first_model = project_model.create_system(
        first["project_id"], base_model_rev=0, title="甲系统",
        definition={"type": "custom"},
    )
    foreign_ref = _ref(first_model)
    with pytest.raises(project_model.ProjectModelError, match="跨项目"):
        project_model.update_object(
            second["project_id"], base_model_rev=0, ref=foreign_ref,
            data={"notes": "不得串项目"},
        )
    assert project_snapshot.get_project_snapshot(second["project_id"])["current"]["systems"] == []
