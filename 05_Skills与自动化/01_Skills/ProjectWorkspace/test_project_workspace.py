# -*- coding: utf-8 -*-
"""ProjectWorkspace F0.2 测试 — final mechanical closure。

每个 gate 通过真实 frozen runtime 调用验证。
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
# Helpers
# ---------------------------------------------------------------------------

def _valid_intent() -> dict:
    return {
        "work_direction": "探索自由意志与体制冲突",
        "reader_promise": "紧张感与道德困境",
        "hard_constraints": ["不美化暴力"],
        "open_space": ["世界观细节可自由扩展"],
    }


def _empty_settlement(scene_ref="scene_001"):
    return {"scene_ref": scene_ref, "candidates": []}


def _mechanical_settlement(scene_ref="scene_001", fact_id="fact_001"):
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
# 1. RECENT_PROSE_USES_FROZEN_STORYWRITE
# ---------------------------------------------------------------------------

class TestRecentProseFrozenWindow:
    def test_returns_frozen_recent_prose_window(self, tmp_path, monkeypatch):
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")

        proj = create_project("recent_test", author_intent=_valid_intent())
        long_text = "A" * 3000
        accept_prose(
            project_dir=proj["project_dir"],
            chapter_number=1,
            scene_ref="scene_recent",
            accepted_text=long_text,
            settlement=_empty_settlement("scene_recent"),
            author_accepted=True,
        )
        artifact = get_recent_prose(proj["project_dir"])

        assert artifact["artifact_type"] == "recent_prose_window"
        assert artifact["scene_ref"] == "scene_recent"
        assert artifact["is_authority"] is False
        assert artifact["must_not_write_state"] is True
        assert artifact["window_chars"] == 2000
        assert artifact["text"] == long_text[-2000:]
        assert "writing_hint" in artifact

        print("RECENT_PROSE_USES_FROZEN_STORYWRITE = TRUE")


# ---------------------------------------------------------------------------
# 2. ACCEPTANCE_SCENE_REF_BOUND + CROSS_PROJECT_CANDIDATE_REJECTED
#    + DUPLICATE_SCENE_REF_REJECTED
# ---------------------------------------------------------------------------

class TestAcceptanceProvenanceGuards:
    def test_settlement_scene_ref_mismatch_rejected(self, tmp_path, monkeypatch):
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")

        proj = create_project("ref_mismatch", author_intent=_valid_intent())
        with pytest.raises(ContractError, match="scene_ref"):
            accept_prose(
                project_dir=proj["project_dir"],
                chapter_number=1,
                scene_ref="scene_A",
                accepted_text="text",
                settlement=_empty_settlement("scene_B"),
                author_accepted=True,
            )
        print("ACCEPTANCE_SCENE_REF_BOUND = TRUE")

    def test_cross_project_candidate_rejected(self, tmp_path, monkeypatch):
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")

        proj_a = create_project("cand_proj_a", author_intent=_valid_intent())
        proj_b = create_project("cand_proj_b", author_intent=_valid_intent())

        # Build a settlement with candidate carrying proj_b's project_id.
        settle = {
            "scene_ref": "scene_cross",
            "candidates": [{
                "classification": "mechanical",
                "target_area": "canon_facts",
                "entry": {"id": "cross_fact", "content": "x"},
                "operation": "append",
                "reason": "test",
                "project_id": proj_b["project_id"],
            }],
        }
        with pytest.raises(ContractError, match="candidate project_id"):
            accept_prose(
                project_dir=proj_a["project_dir"],
                chapter_number=1,
                scene_ref="scene_cross",
                accepted_text="text",
                settlement=settle,
                author_accepted=True,
            )
        print("CROSS_PROJECT_CANDIDATE_REJECTED = TRUE")

    def test_duplicate_scene_ref_rejected(self, tmp_path, monkeypatch):
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")

        proj = create_project("dup_ref", author_intent=_valid_intent())
        accept_prose(
            project_dir=proj["project_dir"],
            chapter_number=1,
            scene_ref="scene_dup",
            accepted_text="first",
            settlement=_empty_settlement("scene_dup"),
            author_accepted=True,
        )
        with pytest.raises(ContractError, match="已在 accepted_text_index"):
            accept_prose(
                project_dir=proj["project_dir"],
                chapter_number=1,
                scene_ref="scene_dup",
                accepted_text="second",
                settlement=_empty_settlement("scene_dup"),
                author_accepted=True,
            )
        print("DUPLICATE_SCENE_REF_REJECTED = TRUE")

    def test_empty_candidates_still_passes_frozen_gate(self, tmp_path, monkeypatch):
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")

        proj = create_project("empty_cand", author_intent=_valid_intent())
        result = accept_prose(
            project_dir=proj["project_dir"],
            chapter_number=1,
            scene_ref="scene_empty",
            accepted_text="text",
            settlement=_empty_settlement("scene_empty"),
            author_accepted=True,
        )
        assert result["success"]


# ---------------------------------------------------------------------------
# 3. STATE_TRANSITION_PERSISTENCE — tightened guards
# ---------------------------------------------------------------------------

class TestPersistStateTransitionTightened:
    def _make_planning_new_state(self, proj_dir):
        """Use real frozen StoryDesign apply_diff to produce a legal new_state."""
        sd_path = str(Path(__file__).resolve().parent.parent / "StoryDesign")
        if sd_path not in sys.path:
            sys.path.insert(0, sd_path)
        from story_runtime import (
            compile_creation_brief, build_context, create_design_candidate,
            create_decision_record, make_planning_diff, apply_diff,
        )
        loaded = load_project(proj_dir)
        intent = loaded["intent"]
        state = loaded["state"]
        brief = compile_creation_brief(
            project_id=intent["project_id"], brief_id="brief_persist",
            author_input="测试", intent=intent, state=state,
        )
        ctx = build_context(context_id="ctx_persist", brief=brief, intent=intent, state=state)
        cand = create_design_candidate(candidate_id="cand_persist", brief=brief, context=ctx, model_output={"p": "t"})
        dec = create_decision_record(
            decision_id="dec_persist", brief=brief, context=ctx, candidate=cand,
            author_action="choose", author_confirmation_ref="author:persist_confirm",
            final_decision={"choice": "t"}, simulation=False,
        )
        plan = {"id": "plan_persist_001", "target": "test", "description": "test"}
        diff = make_planning_diff(diff_id="diff_persist", state=state, decision=dec, plan=plan)
        return state, apply_diff(state, diff, dec)

    def test_real_storydesign_persist_succeeds(self, tmp_path, monkeypatch):
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")

        proj = create_project("persist_sd", author_intent=_valid_intent())
        base, new = self._make_planning_new_state(proj["project_dir"])
        result = persist_state_transition(proj["project_dir"], base, new)
        assert result["success"]

        reloaded = load_project(proj["project_dir"])
        assert reloaded["state"]["state_rev"] == base["state_rev"] + 1
        assert any(p.get("id") == "plan_persist_001" for p in reloaded["state"]["approved_plan"])

        print("STATE_TRANSITION_PERSISTENCE = TRUE")

    def test_fake_state_rev_bump_rejected(self, tmp_path, monkeypatch):
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")

        proj = create_project("fake_rev", author_intent=_valid_intent())
        loaded = load_project(proj["project_dir"])
        base = loaded["state"]
        fake = json.loads(json.dumps(base))
        fake["state_rev"] = base["state_rev"] + 1
        fake["last_authority_source"] = "author_decision:fake"

        with pytest.raises(ContractError):
            persist_state_transition(proj["project_dir"], base, fake)

    def test_wrong_authority_prefix_rejected(self, tmp_path, monkeypatch):
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")

        proj = create_project("wrong_auth", author_intent=_valid_intent())
        base, new = self._make_planning_new_state(proj["project_dir"])
        # Tamper last_authority_source.
        new["last_authority_source"] = "simulation_author_decision:bad"
        with pytest.raises(ContractError, match="author_decision:"):
            persist_state_transition(proj["project_dir"], base, new)

    def test_canon_change_rejected(self, tmp_path, monkeypatch):
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")

        proj = create_project("canon_chg", author_intent=_valid_intent())
        base, new = self._make_planning_new_state(proj["project_dir"])
        # Tamper canon.
        new["canon_facts"].append({"id": "injected", "authority": "author_decision:x", "content": "bad"})
        with pytest.raises(ContractError, match="canon_facts"):
            persist_state_transition(proj["project_dir"], base, new)

    def test_full_base_equality_required(self, tmp_path, monkeypatch):
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")

        proj = create_project("full_eq", author_intent=_valid_intent())
        base, new = self._make_planning_new_state(proj["project_dir"])
        # Use a slightly different base (add a harmless key).
        wrong_base = json.loads(json.dumps(base))
        wrong_base["_extra"] = "nope"
        with pytest.raises(ContractError, match="disk current != expected_base_state"):
            persist_state_transition(proj["project_dir"], wrong_base, new)


# ---------------------------------------------------------------------------
# 4. ACCEPTED_PROSE_PARTIAL_WRITE — fault injection
# ---------------------------------------------------------------------------

class TestPartialWriteFaultInjection:
    def test_case_a_chapter_ok_index_fail_rollback(self, tmp_path, monkeypatch):
        """Chapter write succeeds, index write fails → full rollback."""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")

        proj = create_project("fault_a", author_intent=_valid_intent())
        proj_dir = Path(proj["project_dir"])
        state_file = proj_dir / "_工作台状态" / "story_state.json"
        index_file = proj_dir / "_工作台状态" / "accepted_text_index.json"
        chapter_file = proj_dir / "03_正文" / "第001章.md"

        state_before = state_file.read_bytes()
        index_before = index_file.read_bytes()
        chapter_before = None  # does not exist yet

        call_count = [0]
        original_safe_write = pw._safe_write_file

        def fault_injector(path, content):
            call_count[0] += 1
            # 1st call = chapter (succeed), 2nd call = index (fail)
            if call_count[0] == 2:
                raise RuntimeError("SIMULATED_INDEX_FAIL")
            return original_safe_write(path, content)

        monkeypatch.setattr(pw, "_safe_write_file", fault_injector)

        with pytest.raises(WorkspaceError, match="已回滚"):
            accept_prose(
                project_dir=proj["project_dir"],
                chapter_number=1,
                scene_ref="fault_a_scene",
                accepted_text="fault text",
                settlement=_empty_settlement("fault_a_scene"),
                author_accepted=True,
            )

        # Verify full rollback.
        assert state_file.read_bytes() == state_before
        assert index_file.read_bytes() == index_before
        assert not chapter_file.exists()  # was new, should be deleted

        print("ACCEPTED_PROSE_PARTIAL_WRITE_CASE_A = FALSE")

    def test_case_b_chapter_index_ok_state_fail_rollback(self, tmp_path, monkeypatch):
        """Chapter + index succeed, state write fails → full rollback."""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")

        proj = create_project("fault_b", author_intent=_valid_intent())
        proj_dir = Path(proj["project_dir"])
        state_file = proj_dir / "_工作台状态" / "story_state.json"
        index_file = proj_dir / "_工作台状态" / "accepted_text_index.json"
        chapter_file = proj_dir / "03_正文" / "第001章.md"

        state_before = state_file.read_bytes()
        index_before = index_file.read_bytes()

        call_count = [0]
        original_safe_write = pw._safe_write_file

        def fault_injector(path, content):
            call_count[0] += 1
            # 1st=chapter ok, 2nd=index ok, 3rd=state fail
            if call_count[0] == 3:
                raise RuntimeError("SIMULATED_STATE_FAIL")
            return original_safe_write(path, content)

        monkeypatch.setattr(pw, "_safe_write_file", fault_injector)

        with pytest.raises(WorkspaceError, match="已回滚"):
            accept_prose(
                project_dir=proj["project_dir"],
                chapter_number=1,
                scene_ref="fault_b_scene",
                accepted_text="fault text",
                settlement=_mechanical_settlement("fault_b_scene", "fault_fact"),
                author_accepted=True,
            )

        # Verify full rollback.
        assert state_file.read_bytes() == state_before
        assert index_file.read_bytes() == index_before
        assert not chapter_file.exists()

        print("ACCEPTED_PROSE_PARTIAL_WRITE_CASE_B = FALSE")
        print("ACCEPTED_PROSE_PARTIAL_WRITE = FALSE")


# ---------------------------------------------------------------------------
# 5. PROJECT_PATH_CONTAINMENT
# ---------------------------------------------------------------------------

class TestPathContainment:
    def test_outside_project_dir_rejected(self, tmp_path, monkeypatch):
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")

        outside = tmp_path / "evil_dir"
        outside.mkdir()
        with pytest.raises(ContractError, match="不在 03_作品工程"):
            load_project(outside)

    def test_traversal_chapter_path_rejected(self, tmp_path, monkeypatch):
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")

        proj = create_project("path_test", author_intent=_valid_intent())
        # Accept one valid prose first so index has an entry.
        accept_prose(
            project_dir=proj["project_dir"],
            chapter_number=1,
            scene_ref="path_scene",
            accepted_text="text",
            settlement=_empty_settlement("path_scene"),
            author_accepted=True,
        )
        # Tamper index to point outside.
        index_file = Path(proj["project_dir"]) / "_工作台状态" / "accepted_text_index.json"
        idx = json.loads(index_file.read_text(encoding="utf-8"))
        idx["entries"][-1]["chapter_path"] = "../另一作品/03_正文/第001章.md"
        index_file.write_text(json.dumps(idx, ensure_ascii=False), encoding="utf-8")

        with pytest.raises(ContractError, match="chapter_path"):
            get_recent_prose(proj["project_dir"])

        print("PROJECT_PATH_CONTAINMENT = TRUE")


# ---------------------------------------------------------------------------
# 6. INTENT_REV LOCKED TO 1
# ---------------------------------------------------------------------------

class TestIntentRevLocked:
    def test_caller_intent_rev_not_1_rejected(self, tmp_path, monkeypatch):
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")

        intent = _valid_intent()
        intent["intent_rev"] = 7
        with pytest.raises(ContractError, match="intent_rev 必须为 1"):
            create_project("rev7", author_intent=intent)

    def test_caller_intent_rev_1_accepted(self, tmp_path, monkeypatch):
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")

        intent = _valid_intent()
        intent["intent_rev"] = 1
        proj = create_project("rev1", author_intent=intent)
        stored = json.loads(
            (Path(proj["project_dir"]) / "_工作台状态" / "author_intent.json").read_text(encoding="utf-8")
        )
        assert stored["intent_rev"] == 1


# ---------------------------------------------------------------------------
# 7. MULTI_PROJECT_CONTEXT_ISOLATION
# ---------------------------------------------------------------------------

class TestMultiProjectContextIsolation:
    def test_context_compiler_isolation(self, tmp_path, monkeypatch):
        """A/B same character id, different facts → Context only sees own facts."""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")

        proj_a = create_project("ctx_iso_a", author_intent=_valid_intent())
        proj_b = create_project("ctx_iso_b", author_intent=_valid_intent())

        # Add character_state to A: 怕雨
        state_a = load_project(proj_a["project_dir"])["state"]
        state_a["character_state"].append({
            "id": "char_main",
            "authority": "accepted_text:scene_ctx_a",
            "content": "怕雨",
        })
        state_a["state_rev"] = 2
        state_a["last_authority_source"] = "accepted_text:scene_ctx_a"
        sf_a = Path(proj_a["project_dir"]) / "_工作台状态" / "story_state.json"
        sf_a.write_text(json.dumps(state_a, ensure_ascii=False, indent=2), encoding="utf-8")

        # Add character_state to B: 喜欢雨
        state_b = load_project(proj_b["project_dir"])["state"]
        state_b["character_state"].append({
            "id": "char_main",
            "authority": "accepted_text:scene_ctx_b",
            "content": "喜欢雨",
        })
        state_b["state_rev"] = 2
        state_b["last_authority_source"] = "accepted_text:scene_ctx_b"
        sf_b = Path(proj_b["project_dir"]) / "_工作台状态" / "story_state.json"
        sf_b.write_text(json.dumps(state_b, ensure_ascii=False, indent=2), encoding="utf-8")

        # Import frozen ContextCompiler.
        cc_path = str(Path(__file__).resolve().parent.parent / "ContextCompiler")
        sd_path = str(Path(__file__).resolve().parent.parent / "StoryDesign")
        for p in (cc_path, sd_path):
            if p not in sys.path:
                sys.path.insert(0, p)
        from context_compiler import compile_context
        from story_runtime import compile_creation_brief

        # Reload projects with updated state.
        la = load_project(proj_a["project_dir"])
        lb = load_project(proj_b["project_dir"])

        brief_a = compile_creation_brief(
            project_id=la["intent"]["project_id"], brief_id="brief_ctx_a",
            author_input="test", intent=la["intent"], state=la["state"],
        )
        brief_b = compile_creation_brief(
            project_id=lb["intent"]["project_id"], brief_id="brief_ctx_b",
            author_input="test", intent=lb["intent"], state=lb["state"],
        )

        sel_a = [{"area": "character_state", "id": "char_main", "reason": "test"}]
        sel_b = [{"area": "character_state", "id": "char_main", "reason": "test"}]

        ctx_a = compile_context(
            context_id="ctx_a", brief=brief_a, intent=la["intent"], state=la["state"],
            state_selections=sel_a,
        )
        ctx_b = compile_context(
            context_id="ctx_b", brief=brief_b, intent=lb["intent"], state=lb["state"],
            state_selections=sel_b,
        )

        chars_a = ctx_a["selected_story_state"].get("character_state", [])
        chars_b = ctx_b["selected_story_state"].get("character_state", [])

        assert len(chars_a) == 1 and chars_a[0]["content"] == "怕雨"
        assert len(chars_b) == 1 and chars_b[0]["content"] == "喜欢雨"

        print("MULTI_PROJECT_CONTEXT_ISOLATION = TRUE")
        print("MULTI_PROJECT_ISOLATION = TRUE")


# ---------------------------------------------------------------------------
# CONTROL_CHAR_COUNT
# ---------------------------------------------------------------------------

class TestControlCharScan:
    def test_control_char_count_zero(self):
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
        assert total_bad == 0
        print(f"CONTROL_CHAR_COUNT = {total_bad}")


# ---------------------------------------------------------------------------
# FROZEN_RUNTIME_PRODUCTION_CHANGES
# ---------------------------------------------------------------------------

class TestFrozenRuntimeProductionChanges:
    def test_no_frozen_runtime_modified(self):
        import subprocess
        base_sha = "fbe806f3aeec57629cf5139602a12df92772beae"
        result = subprocess.run(
            ["git", "diff", "--name-only", base_sha, "--",
             "05_Skills与自动化/01_Skills/StoryDesign/",
             "05_Skills与自动化/01_Skills/StoryPlan/",
             "05_Skills与自动化/01_Skills/StoryWrite/",
             "05_Skills与自动化/01_Skills/ContextCompiler/",
             "05_Skills与自动化/01_Skills/KnowledgeRetrieve/"],
            capture_output=True, text=True, cwd="E:/AI-Write",
        )
        changed = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
        assert len(changed) == 0, f"Frozen runtime modified: {changed}"
        print("FROZEN_RUNTIME_PRODUCTION_CHANGES = 0")
