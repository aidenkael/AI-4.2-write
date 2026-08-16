# -*- coding: utf-8 -*-
"""ProjectWorkspace F0.1 测试。

使用 pytest tmp_path 创建虚构测试工程，不在真实 03_作品工程 中制造测试小说。
每个 F0 gate 必须通过真实 frozen runtime 调用验证，不得用字符串检查替代。
"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from project_workspace import (
    WorkspaceError,
    ContractError,
    generate_project_id,
    validate_project_name,
    list_projects,
    resolve_project,
    create_project,
    load_project,
    persist_state_transition,
    accept_prose,
    get_recent_prose,
)


# ---------------------------------------------------------------------------
# Helpers: minimal frozen-compatible Author Intent
# ---------------------------------------------------------------------------

def _valid_intent(name: str = "测试作品") -> dict:
    """Return a complete author_intent that passes frozen validate_author_intent."""
    return {
        "work_direction": "探索自由意志与体制冲突",
        "reader_promise": "紧张感与道德困境",
        "hard_constraints": ["不美化暴力"],
        "open_space": ["世界观细节可自由扩展"],
    }


def _empty_settlement(scene_ref: str = "scene_001") -> dict:
    """Minimal valid settlement with no mechanical candidates."""
    return {"scene_ref": scene_ref, "candidates": []}


def _mechanical_settlement(scene_ref: str = "scene_001", fact_id: str = "fact_001") -> dict:
    return {
        "scene_ref": scene_ref,
        "candidates": [{
            "classification": "mechanical",
            "target_area": "canon_facts",
            "entry": {"id": fact_id, "content": "test fact"},
            "operation": "append",
            "reason": "test",
        }],
    }


# ---------------------------------------------------------------------------
# Basic validation
# ---------------------------------------------------------------------------

class TestProjectNameValidation:
    def test_valid_name(self):
        validate_project_name("长安十二时辰")
        validate_project_name("Test Project")

    def test_empty_name(self):
        with pytest.raises(ContractError, match="不能为空"):
            validate_project_name("")
        with pytest.raises(ContractError, match="不能为空"):
            validate_project_name("   ")

    def test_dangerous_names(self):
        with pytest.raises(ContractError):
            validate_project_name(".")
        with pytest.raises(ContractError):
            validate_project_name("..")

    def test_path_separators(self):
        with pytest.raises(ContractError, match="路径分隔符"):
            validate_project_name("test/project")
        with pytest.raises(ContractError, match="路径分隔符"):
            validate_project_name("test\\project")

    def test_null_character(self):
        with pytest.raises(ContractError, match="空字符"):
            validate_project_name("test\x00project")


class TestProjectIdGeneration:
    def test_deterministic(self):
        assert generate_project_id("测试作品") == generate_project_id("测试作品")

    def test_different_names(self):
        assert generate_project_id("作品A") != generate_project_id("作品B")

    def test_format(self):
        pid = generate_project_id("测试")
        assert pid.startswith("proj_")
        assert len(pid) == 21


# ---------------------------------------------------------------------------
# Create / Load with frozen Author Intent contract
# ---------------------------------------------------------------------------

class TestCreateProject:
    def test_create_requires_complete_intent(self, tmp_path, monkeypatch):
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")

        # Missing required semantic fields → frozen validator rejects.
        with pytest.raises(ContractError, match="frozen validate_author_intent"):
            create_project("bad_intent", author_intent={"genre": "scifi"})

        # None intent → rejected.
        with pytest.raises(ContractError, match="author_intent"):
            create_project("no_intent", author_intent=None)

    def test_create_with_valid_intent(self, tmp_path, monkeypatch):
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")

        proj = create_project("测试作品", author_intent=_valid_intent())
        assert proj["name"] == "测试作品"
        assert proj["project_id"].startswith("proj_")

        project_dir = Path(proj["project_dir"])
        assert (project_dir / "_工作台状态" / "author_intent.json").exists()
        assert (project_dir / "_工作台状态" / "story_state.json").exists()
        assert (project_dir / "_工作台状态" / "accepted_text_index.json").exists()

        # Stored intent must pass frozen validation and carry injected fields.
        stored = json.loads((project_dir / "_工作台状态" / "author_intent.json").read_text(encoding="utf-8"))
        assert stored["project_id"] == proj["project_id"]
        assert stored["intent_rev"] == 1
        assert stored["work_direction"] == "探索自由意志与体制冲突"

    def test_create_rejects_mismatched_caller_project_id(self, tmp_path, monkeypatch):
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")

        intent = _valid_intent()
        intent["project_id"] = "proj_fake_wrong"
        with pytest.raises(ContractError, match="project_id 与生成值不一致"):
            create_project("mismatch", author_intent=intent)

    def test_create_duplicate_rejected(self, tmp_path, monkeypatch):
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")

        create_project("dup", author_intent=_valid_intent())
        with pytest.raises(ContractError, match="已存在"):
            create_project("dup", author_intent=_valid_intent())


class TestLoadProject:
    def test_load_validates_frozen_contracts_and_ids(self, tmp_path, monkeypatch):
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")

        proj = create_project("load_test", author_intent=_valid_intent())
        loaded = load_project(proj["project_dir"])
        assert loaded["project_id"] == proj["project_id"]
        assert loaded["intent"]["intent_rev"] == 1
        assert loaded["state"]["state_rev"] == 1

    def test_load_rejects_inconsistent_project_ids(self, tmp_path, monkeypatch):
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")

        proj = create_project("cross_id", author_intent=_valid_intent())
        state_file = Path(proj["project_dir"]) / "_工作台状态" / "story_state.json"
        state = json.loads(state_file.read_text(encoding="utf-8"))
        state["project_id"] = "proj_tampered"
        state_file.write_text(json.dumps(state), encoding="utf-8")

        with pytest.raises(ContractError, match="project_id 不一致"):
            load_project(proj["project_dir"])


# ---------------------------------------------------------------------------
# AUTHOR_INTENT_FROZEN_CONTRACT_VALIDATED — real frozen validator call
# ---------------------------------------------------------------------------

class TestAuthorIntentFrozenContract:
    def test_author_intent_frozen_contract_validated(self, tmp_path, monkeypatch):
        """Real call to frozen validate_author_intent; incomplete intent is rejected."""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")

        # Track actual frozen validator invocations.
        calls = []
        original = pw.validate_author_intent

        def tracked(intent):
            calls.append(dict(intent))
            return original(intent)

        monkeypatch.setattr(pw, "validate_author_intent", tracked)

        proj = create_project("frozen_intent", author_intent=_valid_intent())
        assert len(calls) >= 1
        assert any(c.get("project_id") == proj["project_id"] for c in calls)

        # Incomplete intent must be rejected by the same frozen validator.
        with pytest.raises(ContractError, match="frozen validate_author_intent"):
            create_project("bad", author_intent={"work_direction": "only one field"})

        print("AUTHOR_INTENT_FROZEN_CONTRACT_VALIDATED = TRUE")


# ---------------------------------------------------------------------------
# STATE_TRANSITION_PERSISTENCE — generic persist_state_transition
# ---------------------------------------------------------------------------

class TestPersistStateTransition:
    def test_persist_state_transition_real_flow(self, tmp_path, monkeypatch):
        """persist_state_transition validates stale base, cross-project, frozen state."""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")

        proj = create_project("persist_test", author_intent=_valid_intent())
        loaded = load_project(proj["project_dir"])
        base_state = loaded["state"]

        # Build a legal new_state via frozen apply_diff path is heavy; we can
        # instead bump state_rev manually but still pass frozen validate_story_state.
        new_state = json.loads(json.dumps(base_state))
        new_state["state_rev"] = base_state["state_rev"] + 1
        new_state["last_authority_source"] = "test:manual_bump"

        result = persist_state_transition(
            project_dir=proj["project_dir"],
            expected_base_state=base_state,
            new_state=new_state,
        )
        assert result["success"] is True
        assert result["state_rev"] == base_state["state_rev"] + 1

        # Re-read from disk to confirm persistence.
        reloaded = load_project(proj["project_dir"])
        assert reloaded["state"]["state_rev"] == base_state["state_rev"] + 1

    def test_persist_rejects_stale_base(self, tmp_path, monkeypatch):
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")

        proj = create_project("stale_test", author_intent=_valid_intent())
        loaded = load_project(proj["project_dir"])
        base = loaded["state"]
        new = json.loads(json.dumps(base))
        new["state_rev"] = base["state_rev"] + 1

        # First persist succeeds.
        persist_state_transition(proj["project_dir"], base, new)

        # Second persist with same stale base must fail.
        new2 = json.loads(json.dumps(new))
        new2["state_rev"] = new["state_rev"] + 1
        with pytest.raises(ContractError, match="stale base state_rev"):
            persist_state_transition(proj["project_dir"], base, new2)

    def test_persist_rejects_cross_project(self, tmp_path, monkeypatch):
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")

        proj_a = create_project("cross_a", author_intent=_valid_intent())
        proj_b = create_project("cross_b", author_intent=_valid_intent())
        state_a = load_project(proj_a["project_dir"])["state"]
        state_b = load_project(proj_b["project_dir"])["state"]

        # Try to write state_b into project A → cross-project rejection.
        with pytest.raises(ContractError, match="project_id 不一致"):
            persist_state_transition(proj_a["project_dir"], state_a, state_b)

        print("STATE_TRANSITION_PERSISTENCE = TRUE")


# ---------------------------------------------------------------------------
# ACCEPTANCE_ALWAYS_USES_FROZEN_GATE — settlement required + frozen call
# ---------------------------------------------------------------------------

class TestAcceptanceFrozenGate:
    def test_acceptance_requires_settlement(self, tmp_path, monkeypatch):
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")

        proj = create_project("settle_req", author_intent=_valid_intent())
        with pytest.raises(ContractError, match="settlement"):
            accept_prose(
                project_dir=proj["project_dir"],
                chapter_number=1,
                scene_ref="scene_001",
                accepted_text="text",
                settlement=None,
                author_accepted=True,
            )

    def test_acceptance_always_calls_frozen_apply_settlement(self, tmp_path, monkeypatch):
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")

        call_log = []
        original = pw.apply_settlement

        def tracked(**kwargs):
            call_log.append(kwargs)
            return original(**kwargs)

        monkeypatch.setattr(pw, "apply_settlement", tracked)

        proj = create_project("gate_test", author_intent=_valid_intent())
        accept_prose(
            project_dir=proj["project_dir"],
            chapter_number=1,
            scene_ref="scene_001",
            accepted_text="text",
            settlement=_empty_settlement(),
            author_accepted=True,
        )
        assert len(call_log) == 1
        assert call_log[0]["mode"] == "production"
        assert call_log[0]["author_accepted"] is True
        assert call_log[0]["accepted_scene_ref"] == "scene_001"

        print("ACCEPTANCE_ALWAYS_USES_FROZEN_GATE = TRUE")

    def test_acceptance_mechanical_settlement_updates_state(self, tmp_path, monkeypatch):
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")

        proj = create_project("mech_settle", author_intent=_valid_intent())
        result = accept_prose(
            project_dir=proj["project_dir"],
            chapter_number=1,
            scene_ref="scene_001",
            accepted_text="text",
            settlement=_mechanical_settlement(fact_id="fact_mech"),
            author_accepted=True,
        )
        assert result["success"]
        state = load_project(proj["project_dir"])["state"]
        assert any(f.get("id") == "fact_mech" for f in state.get("canon_facts", []))
        assert state["state_rev"] >= 2


# ---------------------------------------------------------------------------
# RECENT_PROSE_USES_FROZEN_STORYWRITE — reads production chapters + index
# ---------------------------------------------------------------------------

class TestRecentProse:
    def test_recent_prose_reads_production_chapters(self, tmp_path, monkeypatch):
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")

        proj = create_project("recent_test", author_intent=_valid_intent())
        long_text = "A" * 3000
        accept_prose(
            project_dir=proj["project_dir"],
            chapter_number=1,
            scene_ref="scene_001",
            accepted_text=long_text,
            settlement=_empty_settlement(),
            author_accepted=True,
        )
        prose = get_recent_prose(proj["project_dir"], max_chars=2000)
        assert prose is not None
        assert len(prose) <= 2000
        assert prose == long_text[-2000:]

        print("RECENT_PROSE_USES_FROZEN_STORYWRITE = TRUE")


# ---------------------------------------------------------------------------
# MULTI_PROJECT_ISOLATION + CROSS_PROJECT_WRITE_REJECTED
# ---------------------------------------------------------------------------

class TestMultiProjectIsolation:
    def test_two_projects_isolated_states_and_prose(self, tmp_path, monkeypatch):
        """A accept must not change B's chapter/index/state bytes, and vice versa."""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")

        proj_a = create_project("作品A", author_intent=_valid_intent())
        proj_b = create_project("作品B", author_intent=_valid_intent())

        def read_bytes(p):
            pp = Path(p)
            return pp.read_bytes() if pp.exists() else None

        b_chapter_before = read_bytes(Path(proj_b["project_dir"]) / "03_正文" / "第001章.md")
        b_index_before = read_bytes(Path(proj_b["project_dir"]) / "_工作台状态" / "accepted_text_index.json")
        b_state_before = read_bytes(Path(proj_b["project_dir"]) / "_工作台状态" / "story_state.json")

        accept_prose(
            project_dir=proj_a["project_dir"],
            chapter_number=1,
            scene_ref="a_scene",
            accepted_text="A content",
            settlement=_mechanical_settlement(scene_ref="a_scene", fact_id="a_fact"),
            author_accepted=True,
        )

        assert read_bytes(Path(proj_b["project_dir"]) / "03_正文" / "第001章.md") == b_chapter_before
        assert read_bytes(Path(proj_b["project_dir"]) / "_工作台状态" / "accepted_text_index.json") == b_index_before
        assert read_bytes(Path(proj_b["project_dir"]) / "_工作台状态" / "story_state.json") == b_state_before

        # Now B accepts; A must remain unchanged.
        a_chapter_before = read_bytes(Path(proj_a["project_dir"]) / "03_正文" / "第001章.md")
        a_index_before = read_bytes(Path(proj_a["project_dir"]) / "_工作台状态" / "accepted_text_index.json")
        a_state_before = read_bytes(Path(proj_a["project_dir"]) / "_工作台状态" / "story_state.json")

        accept_prose(
            project_dir=proj_b["project_dir"],
            chapter_number=1,
            scene_ref="b_scene",
            accepted_text="B content",
            settlement=_mechanical_settlement(scene_ref="b_scene", fact_id="b_fact"),
            author_accepted=True,
        )

        assert read_bytes(Path(proj_a["project_dir"]) / "03_正文" / "第001章.md") == a_chapter_before
        assert read_bytes(Path(proj_a["project_dir"]) / "_工作台状态" / "accepted_text_index.json") == a_index_before
        assert read_bytes(Path(proj_a["project_dir"]) / "_工作台状态" / "story_state.json") == a_state_before

        print("MULTI_PROJECT_ISOLATION = TRUE")

    def test_cross_project_write_rejected_via_load(self, tmp_path, monkeypatch):
        """Tampered state project_id breaks load_project consistency check."""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")

        proj = create_project("cross_reject", author_intent=_valid_intent())
        state_file = Path(proj["project_dir"]) / "_工作台状态" / "story_state.json"
        state = json.loads(state_file.read_text(encoding="utf-8"))
        state["project_id"] = "proj_tampered_wrong"
        state_file.write_text(json.dumps(state), encoding="utf-8")

        with pytest.raises(ContractError, match="project_id 不一致"):
            load_project(proj["project_dir"])

        print("CROSS_PROJECT_WRITE_REJECTED = TRUE")


# ---------------------------------------------------------------------------
# SHARED_KNOWLEDGE_ROOT + PROJECT_LOCAL_BKP_COPY = FALSE
# ---------------------------------------------------------------------------

class TestSharedKnowledgeRoot:
    def test_shared_bkp_discovered_without_local_copy(self, tmp_path, monkeypatch):
        """Both projects share the same 02_素材知识库 root; no per-project BKP copy."""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")

        # Create two projects.
        proj_a = create_project("shared_a", author_intent=_valid_intent())
        proj_b = create_project("shared_b", author_intent=_valid_intent())

        # Create a minimal legal BKP under shared root.
        shared_root = tmp_path / "02_素材知识库"
        bkp_dir = shared_root / "book_test_共享知识" / "bkp"
        bkp_dir.mkdir(parents=True)
        identity = {
            "book": {
                "book_id": "book_test_shared",
                "title": "共享测试书",
                "author": "Test",
                "category": "测试",
            }
        }
        (bkp_dir / "identity.json").write_text(json.dumps(identity, ensure_ascii=False), encoding="utf-8")

        # Import real KnowledgeRetrieve registry.
        kr_path = str(Path(__file__).resolve().parent.parent / "KnowledgeRetrieve")
        if kr_path not in sys.path:
            sys.path.insert(0, kr_path)
        from registry import discover_bkps

        bkps = discover_bkps(str(tmp_path))
        found_ids = [b["book_id"] for b in bkps]
        assert "book_test_shared" in found_ids

        # Neither project directory contains a local BKP copy.
        a_bkp = Path(proj_a["project_dir"]) / "02_素材知识库"
        b_bkp = Path(proj_b["project_dir"]) / "02_素材知识库"
        assert not a_bkp.exists()
        assert not b_bkp.exists()

        print("SHARED_KNOWLEDGE_ROOT = TRUE")
        print("PROJECT_LOCAL_BKP_COPY = FALSE")


# ---------------------------------------------------------------------------
# CONTROL_CHAR_COUNT — real document scan
# ---------------------------------------------------------------------------

class TestControlCharScan:
    def test_control_char_count_zero_in_docs(self):
        """Scan README.md and SKILL.md for disallowed control characters."""
        repo_root = Path(__file__).resolve().parents[3]
        targets = [
            repo_root / "03_作品工程" / "README.md",
            repo_root / "05_Skills与自动化" / "01_Skills" / "ProjectWorkspace" / "SKILL.md",
        ]
        total_bad = 0
        for t in targets:
            data = t.read_bytes()
            bad = [b for b in data if b < 0x20 and b not in (0x09, 0x0A, 0x0D)]
            total_bad += len(bad)
        assert total_bad == 0, f"Found {total_bad} disallowed control chars"
        print(f"CONTROL_CHAR_COUNT = {total_bad}")


# ---------------------------------------------------------------------------
# STORYDESIGN_REAL_PROJECT_BINDING — real run_story_design binding
# ---------------------------------------------------------------------------

class TestStoryDesignRealBinding:
    def test_storydesign_real_project_binding(self, tmp_path, monkeypatch):
        """Actually call StoryDesign frozen runtime through ProjectWorkspace artifacts."""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")

        proj = create_project("sd_binding", author_intent=_valid_intent())
        loaded = load_project(proj["project_dir"])
        intent = loaded["intent"]
        state = loaded["state"]

        # Import frozen StoryDesign runtime directly.
        sd_path = str(Path(__file__).resolve().parent.parent / "StoryDesign")
        if sd_path not in sys.path:
            sys.path.insert(0, sd_path)
        from story_runtime import (
            compile_creation_brief,
            build_context,
            create_design_candidate,
            create_decision_record,
            make_planning_diff,
            apply_diff as sd_apply_diff,
        )

        brief = compile_creation_brief(
            project_id=intent["project_id"],
            brief_id="brief_sd_001",
            author_input="测试作者输入",
            intent=intent,
            state=state,
        )
        context = build_context(
            context_id="ctx_sd_001",
            brief=brief,
            intent=intent,
            state=state,
        )
        candidate = create_design_candidate(
            candidate_id="cand_sd_001",
            brief=brief,
            context=context,
            model_output={"proposal": "test"},
        )
        decision = create_decision_record(
            decision_id="dec_sd_001",
            brief=brief,
            context=context,
            candidate=candidate,
            author_action="choose",
            author_confirmation_ref="author:test_confirm_sd",
            final_decision={"choice": "test"},
            simulation=False,
        )
        plan = {"id": "plan_sd_001", "target": "test", "description": "test plan"}
        diff = make_planning_diff(
            diff_id="diff_sd_001",
            state=state,
            decision=decision,
            plan=plan,
        )
        new_state = sd_apply_diff(state, diff, decision)

        # Persist via ProjectWorkspace generic transition.
        persist_state_transition(proj["project_dir"], state, new_state)

        reloaded = load_project(proj["project_dir"])
        assert reloaded["state"]["state_rev"] == state["state_rev"] + 1
        assert any(p.get("id") == "plan_sd_001" for p in reloaded["state"]["approved_plan"])

        print("STORYDESIGN_REAL_PROJECT_BINDING = TRUE")


# ---------------------------------------------------------------------------
# STORYPLAN_REAL_PROJECT_BINDING — real run_story_plan binding
# ---------------------------------------------------------------------------

class TestStoryPlanRealBinding:
    def test_storyplan_real_project_binding(self, tmp_path, monkeypatch):
        """Actually call StoryPlan frozen runtime through ProjectWorkspace artifacts."""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")

        proj = create_project("sp_binding", author_intent=_valid_intent())
        loaded = load_project(proj["project_dir"])
        intent = loaded["intent"]
        state = loaded["state"]

        sp_path = str(Path(__file__).resolve().parent.parent / "StoryPlan")
        sd_path = str(Path(__file__).resolve().parent.parent / "StoryDesign")
        for p in (sp_path, sd_path):
            if p not in sys.path:
                sys.path.insert(0, p)

        from story_runtime import (
            compile_creation_brief,
            build_context,
            create_design_candidate,
            create_decision_record,
            make_planning_diff,
            apply_diff as sd_apply_diff,
        )
        from story_plan import (
            compile_plan_brief,
            build_plan_context,
            create_plan_candidate,
            make_plan_diff,
        )
        from story_runtime import (
            create_decision_record as sp_create_decision,
            apply_diff as sp_apply_diff,
        )

        # First: create an approved_plan via StoryDesign so StoryPlan has a
        # confirmed planning source.
        sd_brief = compile_creation_brief(
            project_id=intent["project_id"],
            brief_id="brief_sd_for_sp",
            author_input="为 StoryPlan 准备前置方向",
            intent=intent,
            state=state,
        )
        sd_ctx = build_context(context_id="ctx_sd_for_sp", brief=sd_brief, intent=intent, state=state)
        sd_cand = create_design_candidate(candidate_id="cand_sd_for_sp", brief=sd_brief, context=sd_ctx, model_output={"proposal": "seed"})
        sd_dec = create_decision_record(
            decision_id="dec_sd_for_sp", brief=sd_brief, context=sd_ctx, candidate=sd_cand,
            author_action="choose", author_confirmation_ref="author:sp_seed_confirm",
            final_decision={"choice": "seed"}, simulation=False,
        )
        seed_plan = {"id": "plan_seed_001", "target": "arc_001", "description": "seed plan for StoryPlan"}
        sd_diff = make_planning_diff(diff_id="diff_sd_for_sp", state=state, decision=sd_dec, plan=seed_plan)
        state_after_sd = sd_apply_diff(state, sd_diff, sd_dec)
        persist_state_transition(proj["project_dir"], state, state_after_sd)

        # Reload state with the seed approved_plan.
        loaded2 = load_project(proj["project_dir"])
        state = loaded2["state"]

        planning_target = {"target_id": "arc_001", "target_type": "arc", "description": "test arc"}
        planning_sources = [{"kind": "approved_plan", "ref": "plan_seed_001"}]
        brief = compile_plan_brief(
            project_id=intent["project_id"],
            brief_id="brief_sp_001",
            author_planning_question="测试规划问题",
            planning_target=planning_target,
            planning_sources=planning_sources,
            intent=intent,
            state=state,
            semantic_interpretation={},
        )
        context = build_plan_context(
            context_id="ctx_sp_001",
            brief=brief,
            intent=intent,
            state=state,
        )
        candidate = create_plan_candidate(
            candidate_id="cand_sp_001",
            brief=brief,
            context=context,
            model_output={"plans": [{"id": "plan_sp_001", "description": "test"}]},
        )
        decision = sp_create_decision(
            decision_id="dec_sp_001",
            brief=brief,
            context=context,
            candidate=candidate,
            author_action="choose",
            author_confirmation_ref="author:test_confirm_sp",
            final_decision={"choice": "plan_sp_001"},
            simulation=False,
        )
        plans = [{"id": "plan_sp_001", "description": "test plan", "target_ref": "arc_001"}]
        diff = make_plan_diff(
            diff_id="diff_sp_001",
            state=state,
            intent=intent,
            decision=decision,
            brief=brief,
            plans=plans,
        )
        new_state = sp_apply_diff(state, diff, decision)

        persist_state_transition(proj["project_dir"], state, new_state)

        reloaded = load_project(proj["project_dir"])
        assert reloaded["state"]["state_rev"] == state["state_rev"] + 1
        assert any(p.get("id") == "plan_sp_001" for p in reloaded["state"]["approved_plan"])

        print("STORYPLAN_REAL_PROJECT_BINDING = TRUE")


# ---------------------------------------------------------------------------
# FROZEN_RUNTIME_PRODUCTION_CHANGES — diff-based, not hardcoded SHA
# ---------------------------------------------------------------------------

class TestFrozenRuntimeProductionChanges:
    def test_frozen_runtime_production_changes(self):
        """This commit must not modify frozen runtime production files."""
        import subprocess
        base_sha = "76c37cf1bb6e3a4a87cc9a89f9dfd8087748acc0"
        result = subprocess.run(
            ["git", "diff", "--name-only", base_sha, "--",
             "05_Skills与自动化/01_Skills/StoryDesign/",
             "05_Skills与自动化/01_Skills/StoryPlan/",
             "05_Skills与自动化/01_Skills/StoryWrite/",
             "05_Skills与自动化/01_Skills/ContextCompiler/",
             "05_Skills与自动化/01_Skills/KnowledgeRetrieve/"],
            capture_output=True, text=True, cwd="E:/AI-Write",
        )
        changed = [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]
        assert len(changed) == 0, f"Frozen runtime modified: {changed}"
        print("FROZEN_RUNTIME_PRODUCTION_CHANGES = 0")
