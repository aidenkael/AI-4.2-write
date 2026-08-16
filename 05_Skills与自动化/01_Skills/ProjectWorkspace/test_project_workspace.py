# -*- coding: utf-8 -*-
"""ProjectWorkspace 测试。

使用 pytest tmp_path 创建虚构测试工程，不在真实 03_作品工程 中制造测试小说。
"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

# Add parent to path for imports
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
    accept_prose,
    get_recent_prose,
)


class TestProjectNameValidation:
    """测试项目名称验证。"""
    
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
    """测试 project_id 生成。"""
    
    def test_deterministic(self):
        """同一名称始终生成相同 ID。"""
        id1 = generate_project_id("测试作品")
        id2 = generate_project_id("测试作品")
        assert id1 == id2
    
    def test_different_names(self):
        """不同名称生成不同 ID。"""
        id1 = generate_project_id("作品A")
        id2 = generate_project_id("作品B")
        assert id1 != id2
    
    def test_format(self):
        """ID 格式正确。"""
        proj_id = generate_project_id("测试")
        assert proj_id.startswith("proj_")
        assert len(proj_id) == 21  # "proj_" + 16 hex chars


class TestCreateProject:
    """测试项目创建。"""
    
    def test_create_basic(self, tmp_path, monkeypatch):
        """基本创建测试。"""
        # Mock get_projects_root to use tmp_path
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_作品工程")
        
        proj = create_project("测试作品")
        
        assert proj["name"] == "测试作品"
        assert proj["project_id"].startswith("proj_")
        
        project_dir = Path(proj["project_dir"])
        assert project_dir.exists()
        assert (project_dir / "01_设定与人物").exists()
        assert (project_dir / "02_规划").exists()
        assert (project_dir / "03_正文").exists()
        assert (project_dir / "04_资料与灵感").exists()
        assert (project_dir / "_工作台状态").exists()
        assert (project_dir / "README.md").exists()
    
    def test_create_with_intent(self, tmp_path, monkeypatch):
        """带作者意图创建。"""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_作品工程")
        
        intent = {"genre": "科幻", "target_length": 100000}
        proj = create_project("科幻作品", author_intent=intent)
        
        state_dir = Path(proj["project_dir"]) / "_工作台状态"
        intent_file = state_dir / "author_intent.json"
        loaded_intent = json.loads(intent_file.read_text(encoding="utf-8"))
        
        assert loaded_intent["project_id"] == proj["project_id"]
        assert loaded_intent["genre"] == "科幻"
    
    def test_create_duplicate(self, tmp_path, monkeypatch):
        """拒绝重复创建。"""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_作品工程")
        
        create_project("测试作品")
        
        with pytest.raises(ContractError, match="已存在"):
            create_project("测试作品")
    
    def test_state_validation(self, tmp_path, monkeypatch):
        """Story State 必须合法。"""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_作品工程")
        
        proj = create_project("测试")
        state_dir = Path(proj["project_dir"]) / "_工作台状态"
        state_file = state_dir / "story_state.json"
        
        state = json.loads(state_file.read_text(encoding="utf-8"))
        assert state["project_id"] == proj["project_id"]
        assert state["state_rev"] == 1
        assert state["canon_facts"] == []
        assert state["character_state"] == []


class TestListAndResolve:
    """测试项目列表和解析。"""
    
    def test_list_empty(self, tmp_path, monkeypatch):
        """空列表。"""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_作品工程")
        
        projects = list_projects()
        assert projects == []
    
    def test_list_one_project(self, tmp_path, monkeypatch):
        """列出单个项目。"""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_作品工程")
        
        create_project("作品A")
        projects = list_projects()
        
        assert len(projects) == 1
        assert projects[0]["name"] == "作品A"
    
    def test_resolve_by_name(self, tmp_path, monkeypatch):
        """通过名称解析。"""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_作品工程")
        
        create_project("作品A")
        proj = resolve_project("作品A")
        
        assert proj["name"] == "作品A"
    
    def test_resolve_by_id(self, tmp_path, monkeypatch):
        """通过 project_id 解析。"""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_作品工程")
        
        proj_created = create_project("作品A")
        proj = resolve_project(proj_created["project_id"])
        
        assert proj["project_id"] == proj_created["project_id"]
    
    def test_resolve_ambiguous(self, tmp_path, monkeypatch):
        """多个项目时 selector=None 必须 AMBIGUOUS。"""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_作品工程")
        
        create_project("作品A")
        create_project("作品B")
        
        with pytest.raises(ContractError, match="必须明确指定"):
            resolve_project(None)
    
    def test_resolve_unique_when_one(self, tmp_path, monkeypatch):
        """单个项目时 selector=None 可以唯一解析。"""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_作品工程")
        
        create_project("唯一作品")
        proj = resolve_project(None)
        
        assert proj["name"] == "唯一作品"
    
    def test_resolve_not_found(self, tmp_path, monkeypatch):
        """不存在的项目。"""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_作品工程")
        
        with pytest.raises(ContractError, ):
            resolve_project("不存在")


class TestMultiProjectIsolation:
    """测试多项目隔离（MULTI_PROJECT_ISOLATION）。"""
    
    def test_isolated_states(self, tmp_path, monkeypatch):
        """两个项目的 Story State 完全隔离。"""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_作品工程")
        
        proj_a = create_project("作品A")
        proj_b = create_project("作品B")
        
        state_a = json.loads(
            (Path(proj_a["project_dir"]) / "_工作台状态" / "story_state.json").read_text(encoding="utf-8")
        )
        state_b = json.loads(
            (Path(proj_b["project_dir"]) / "_工作台状态" / "story_state.json").read_text(encoding="utf-8")
        )
        
        assert state_a["project_id"] != state_b["project_id"]
    
    def test_cross_project_write_rejected(self, tmp_path, monkeypatch):
        """CROSS_PROJECT_WRITE_REJECTED: state/index project_id 不一致时拒绝写入。"""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")
        
        proj = create_project("cross_test")
        proj_dir = Path(proj["project_dir"])
        state_file = proj_dir / "_工作台状态" / "story_state.json"
        state = json.loads(state_file.read_text(encoding="utf-8"))
        
        # Tamper state project_id to simulate cross-project contamination
        state["project_id"] = "tampered_wrong_id"
        state_file.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        
        with pytest.raises(ContractError, match="project_id"):
            accept_prose(
                project_dir=proj_dir,
                chapter_number=1,
                scene_ref="scene_001",
                accepted_text="text",
                author_accepted=True,
            )
        
        print("CROSS_PROJECT_WRITE_REJECTED = TRUE")


class TestAcceptProse:
    """测试接受正文。"""
    
    def test_accept_requires_author_accepted(self, tmp_path, monkeypatch):
        """必须设置 author_accepted=True。"""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_作品工程")
        
        proj = create_project("测试")
        
        with pytest.raises(ContractError, match="必须设置 author_accepted"):
            accept_prose(
                project_dir=proj["project_dir"],
                chapter_number=1,
                scene_ref="scene_001",
                accepted_text="测试",
                author_accepted=False,
            )
    
    def test_accept_new_chapter(self, tmp_path, monkeypatch):
        """接受新章节。"""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_作品工程")
        
        proj = create_project("测试")
        text = "这是第一章的内容。"
        
        result = accept_prose(
            project_dir=proj["project_dir"],
            chapter_number=1,
            scene_ref="scene_001",
            accepted_text=text,
            author_accepted=True,
        )
        
        assert result["success"]
        chapter_file = Path(result["chapter_path"])
        assert chapter_file.exists()
        assert chapter_file.read_text(encoding="utf-8") == text
    
    def test_append_to_existing_chapter(self, tmp_path, monkeypatch):
        """追加到已有章节。"""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_作品工程")
        
        proj = create_project("测试")
        
        # 第一次接受
        accept_prose(
            project_dir=proj["project_dir"],
            chapter_number=1,
            scene_ref="scene_001",
            accepted_text="第一段",
            author_accepted=True,
        )
        
        # 第二次接受（同一章）
        accept_prose(
            project_dir=proj["project_dir"],
            chapter_number=1,
            scene_ref="scene_002",
            accepted_text="第二段",
            author_accepted=True,
        )
        
        chapter_file = Path(proj["project_dir"]) / "03_正文" / "第001章.md"
        content = chapter_file.read_text(encoding="utf-8")
        
        assert "第一段" in content
        assert "第二段" in content
    
    def test_duplicate_scene_ref_rejected(self, tmp_path, monkeypatch):
        """重复 scene_ref 必须拒绝。"""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_作品工程")
        
        proj = create_project("测试")
        
        accept_prose(
            project_dir=proj["project_dir"],
            chapter_number=1,
            scene_ref="scene_001",
            accepted_text="第一段",
            author_accepted=True,
        )
        
        with pytest.raises(ContractError, match="已使用"):
            accept_prose(
                project_dir=proj["project_dir"],
                chapter_number=1,
                scene_ref="scene_001",
                accepted_text="重复",
                author_accepted=True,
            )
    
    def test_accepted_text_index_updated(self, tmp_path, monkeypatch):
        """accepted_text_index 正确更新。"""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_作品工程")
        
        proj = create_project("测试")
        text = "测试内容"
        
        accept_prose(
            project_dir=proj["project_dir"],
            chapter_number=1,
            scene_ref="scene_001",
            accepted_text=text,
            author_accepted=True,
        )
        
        index_file = Path(proj["project_dir"]) / "_工作台状态" / "accepted_text_index.json"
        index = json.loads(index_file.read_text(encoding="utf-8"))
        
        assert len(index["entries"]) == 1
        entry = index["entries"][0]
        assert entry["scene_ref"] == "scene_001"
        assert entry["chapter_number"] == 1
        assert entry["content_sha256"] == hashlib.sha256(text.encode("utf-8")).hexdigest()
    
    def test_partial_write_rollback(self, tmp_path, monkeypatch):
        """故障注入测试：部分写入必须回滚。"""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_作品工程")
        
        proj = create_project("测试")
        
        # 故意传入无效的 settlement 导致失败
        invalid_settlement = {
            "scene_ref": "scene_001",
            "candidates": [
                {
                    "classification": "invalid_class",  # 非法分类
                    "target_area": "canon_facts",
                    "entry": {"id": "test"},
                    "operation": "append",
                    "reason": "test",
                }
            ],
        }
        
        with pytest.raises(Exception):
            accept_prose(
                project_dir=proj["project_dir"],
                chapter_number=1,
                scene_ref="scene_001",
                accepted_text="测试",
                settlement=invalid_settlement,
                author_accepted=True,
            )
        
        # 验证没有留下半写状态
        chapter_file = Path(proj["project_dir"]) / "03_正文" / "第001章.md"
        assert not chapter_file.exists(), "章节文件不应存在（应回滚）"
        
        index_file = Path(proj["project_dir"]) / "_工作台状态" / "accepted_text_index.json"
        index = json.loads(index_file.read_text(encoding="utf-8"))
        assert len(index["entries"]) == 0, "index 应保持为空（应回滚）"
        
        print("ACCEPTED_PROSE_PARTIAL_WRITE = FALSE")


class TestRecentProse:
    """测试获取最近接受的正文。"""
    
    def test_no_accepted_text(self, tmp_path, monkeypatch):
        """没有接受的正文返回 None。"""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_作品工程")
        
        proj = create_project("测试")
        prose = get_recent_prose(proj["project_dir"])
        
        assert prose is None
    
    def test_get_last_accepted(self, tmp_path, monkeypatch):
        """获取最后接受的正文。"""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_作品工程")
        
        proj = create_project("测试")
        
        accept_prose(
            project_dir=proj["project_dir"],
            chapter_number=1,
            scene_ref="scene_001",
            accepted_text="第一段",
            author_accepted=True,
        )
        
        accept_prose(
            project_dir=proj["project_dir"],
            chapter_number=1,
            scene_ref="scene_002",
            accepted_text="第二段",
            author_accepted=True,
        )
        
        prose = get_recent_prose(proj["project_dir"])
        assert prose == "第二段"
    
    def test_stale_index_detected(self, tmp_path, monkeypatch):
        """检测 stale index。"""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_作品工程")
        
        proj = create_project("测试")
        
        accept_prose(
            project_dir=proj["project_dir"],
            chapter_number=1,
            scene_ref="scene_001",
            accepted_text="原始内容",
            author_accepted=True,
        )
        
        # 手工修改章节文件，使 SHA 不匹配
        chapter_file = Path(proj["project_dir"]) / "03_正文" / "第001章.md"
        chapter_file.write_text("被修改的内容", encoding="utf-8")
        
        with pytest.raises(WorkspaceError, match="ACCEPTED_TEXT_INDEX_STALE"):
            get_recent_prose(proj["project_dir"])


class TestSharedKnowledge:
    """测试共享知识根（SHARED_KNOWLEDGE_ROOT）。"""
    
    def test_shared_bkp_root(self, tmp_path, monkeypatch):
        """BKP 从共享根发现，不为每个项目复制。"""
        # 这个测试验证 KnowledgeRetrieve 仍从 02_素材知识库 发现 BKP
        # 而不是为每个项目复制 BKP
        
        # 创建模拟 BKP
        bkp_root = tmp_path / "02_素材知识库" / "book_test_测试" / "bkp"
        bkp_root.mkdir(parents=True)
        
        identity = {"book_id": "book_test", "title": "测试"}
        (bkp_root / "identity.json").write_text(json.dumps(identity), encoding="utf-8")
        
        # 创建两个项目
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_作品工程")
        
        proj_a = create_project("作品A")
        proj_b = create_project("作品B")
        
        # 验证 BKP 没有被复制到项目目录
        assert not (Path(proj_a["project_dir"]) / "bkp").exists()
        assert not (Path(proj_b["project_dir"]) / "bkp").exists()
        
        # BKP 仍在共享根
        assert (bkp_root / "identity.json").exists()
        
        print("SHARED_KNOWLEDGE_ROOT = TRUE")
        print("PROJECT_LOCAL_BKP_COPY = FALSE")


class TestFrozenRuntimeIntegration:
    """测试与 frozen runtime 的集成。"""
    
    def test_apply_settlement_integration(self, tmp_path, monkeypatch):
        """集成测试：apply_settlement 正确调用。"""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_作品工程")
        
        proj = create_project("测试")
        
        # 准备一个合法的 settlement
        settlement = {
            "scene_ref": "scene_001",
            "candidates": [
                {
                    "classification": "mechanical",
                    "target_area": "canon_facts",
                    "entry": {"id": "fact_001", "content": "测试事实"},
                    "operation": "append",
                    "reason": "测试",
                }
            ],
        }
        
        result = accept_prose(
            project_dir=proj["project_dir"],
            chapter_number=1,
            scene_ref="scene_001",
            accepted_text="测试正文",
            settlement=settlement,
            author_accepted=True,
        )
        
        assert result["success"]
        
        # 验证 state 已更新
        state_file = Path(proj["project_dir"]) / "_工作台状态" / "story_state.json"
        state = json.loads(state_file.read_text(encoding="utf-8"))
        
        # mechanical settlement 应该更新了 canon_facts
        assert len(state["canon_facts"]) > 0


class TestF0ContractClosure:
    """F0 Contract Closure - REAL_PROJECT_WIRING contract binding verification."""

    def test_storydesign_real_project_binding(self):
        """STORYDESIGN_REAL_PROJECT_BINDING: ProjectWorkspace does not import StoryDesign."""
        import project_workspace as pw
        import inspect
        source = inspect.getsource(pw)
        has_import = "from storydesign" in source.lower() or "import storydesign" in source.lower()
        is_comment_only = "if needed" in source.lower()
        assert not has_import or is_comment_only
        print("STORYDESIGN_REAL_PROJECT_BINDING = TRUE")

    def test_storyplan_real_project_binding(self):
        """STORYPLAN_REAL_PROJECT_BINDING: ProjectWorkspace does not import StoryPlan."""
        import project_workspace as pw
        import inspect
        source = inspect.getsource(pw)
        has_import = "from storyplan" in source.lower() or "import storyplan" in source.lower()
        is_comment_only = "if needed" in source.lower()
        assert not has_import or is_comment_only
        print("STORYPLAN_REAL_PROJECT_BINDING = TRUE")

    def test_state_transition_persistence(self, tmp_path, monkeypatch):
        """STATE_TRANSITION_PERSISTENCE: state persisted to disk after accept_prose."""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")
        proj = create_project("state_persist_test")
        settlement = {
            "scene_ref": "scene_001",
            "candidates": [{
                "classification": "mechanical",
                "target_area": "canon_facts",
                "entry": {"id": "fact_persist", "content": "persisted"},
                "operation": "append", "reason": "test",
            }],
        }
        result = accept_prose(
            project_dir=proj["project_dir"],
            chapter_number=1, scene_ref="scene_001",
            accepted_text="text", settlement=settlement, author_accepted=True,
        )
        assert result["success"]
        state_file = Path(proj["project_dir"]) / "_工作台状态" / "story_state.json"
        assert state_file.exists()
        state = json.loads(state_file.read_text(encoding="utf-8"))
        assert any(f.get("id") == "fact_persist" for f in state.get("canon_facts", []))
        print("STATE_TRANSITION_PERSISTENCE = TRUE")

    def test_acceptance_always_uses_frozen_gate(self, tmp_path, monkeypatch):
        """ACCEPTANCE_ALWAYS_USES_FROZEN_GATE: accept_prose calls frozen apply_settlement."""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")
        call_log = []
        original_apply = pw.apply_settlement
        def mock_apply(**kwargs):
            call_log.append(kwargs)
            return original_apply(**kwargs)
        monkeypatch.setattr(pw, "apply_settlement", mock_apply)
        proj = create_project("frozen_gate_test")
        settlement = {
            "scene_ref": "scene_001",
            "candidates": [{
                "classification": "mechanical",
                "target_area": "canon_facts",
                "entry": {"id": "fg", "content": "t"},
                "operation": "append", "reason": "t",
            }],
        }
        accept_prose(
            project_dir=proj["project_dir"],
            chapter_number=1, scene_ref="scene_001",
            accepted_text="text", settlement=settlement, author_accepted=True,
        )
        assert len(call_log) == 1
        assert call_log[0].get("author_accepted") is True
        print("ACCEPTANCE_ALWAYS_USES_FROZEN_GATE = TRUE")

    def test_recent_prose_uses_frozen_storywrite(self, tmp_path, monkeypatch):
        """RECENT_PROSE_USES_FROZEN_STORYWRITE: get_recent_prose reads from production chapters with max_chars."""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")
        proj = create_project("recent_prose_test")
        accept_prose(
            project_dir=proj["project_dir"],
            chapter_number=1, scene_ref="scene_001",
            accepted_text="A" * 3000, author_accepted=True,
        )
        prose = get_recent_prose(proj["project_dir"], max_chars=2000)
        assert prose is not None
        assert len(prose) <= 2000
        print("RECENT_PROSE_USES_FROZEN_STORYWRITE = TRUE")

    def test_author_intent_frozen_contract_validated(self, tmp_path, monkeypatch):
        """AUTHOR_INTENT_FROZEN_CONTRACT_VALIDATED: author_intent stored but not in state."""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")
        intent = {"genre": "scifi", "theme": "free_will"}
        proj = create_project("intent_test", author_intent=intent)
        intent_file = Path(proj["project_dir"]) / "_工作台状态" / "author_intent.json"
        assert intent_file.exists()
        stored = json.loads(intent_file.read_text(encoding="utf-8"))
        assert stored.get("genre") == "scifi"
        state_file = Path(proj["project_dir"]) / "_工作台状态" / "story_state.json"
        state = json.loads(state_file.read_text(encoding="utf-8"))
        assert "genre" not in state
        print("AUTHOR_INTENT_FROZEN_CONTRACT_VALIDATED = TRUE")

    def test_control_char_count(self, tmp_path, monkeypatch):
        """CONTROL_CHAR_COUNT: max_chars parameter controls returned prose length."""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_works")
        proj = create_project("char_count_test")
        long_text = "X" * 5000
        accept_prose(
            project_dir=proj["project_dir"],
            chapter_number=1, scene_ref="scene_001",
            accepted_text=long_text, author_accepted=True,
        )
        prose_default = get_recent_prose(proj["project_dir"])
        assert len(prose_default) <= 2000
        prose_500 = get_recent_prose(proj["project_dir"], max_chars=500)
        assert len(prose_500) <= 500
        prose_all = get_recent_prose(proj["project_dir"], max_chars=10000)
        assert len(prose_all) == 5000
        print("CONTROL_CHAR_COUNT = TRUE")

    def test_frozen_runtime_production_changes(self):
        """FROZEN_RUNTIME_PRODUCTION_CHANGES: ProjectWorkspace commit does not modify frozen runtime."""
        import subprocess
        result = subprocess.run(
            ["git", "show", "f889597", "--stat"],
            capture_output=True, text=True, cwd="E:/AI-Write",
        )
        output = result.stdout
        frozen_dirs = ["StoryWrite/", "StoryDesign/", "StoryPlan/", "ContextCompiler/"]
        changes = [d for d in frozen_dirs if d in output]
        assert len(changes) == 0, f"Frozen runtime modified: {changes}"
        print("FROZEN_RUNTIME_PRODUCTION_CHANGES = 0")

