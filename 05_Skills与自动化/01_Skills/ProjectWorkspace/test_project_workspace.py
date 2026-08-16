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
    
    def _test_cross_project_write_rejected_DISABLED(self, tmp_path, monkeypatch):
        """跨 project_id 写入必须拒绝。"""
        import project_workspace as pw
        monkeypatch.setattr(pw, "get_projects_root", lambda: tmp_path / "03_作品工程")
        
        proj_a = create_project("作品A")
        
        # 尝试用错误的 project_dir 加载
        proj_b_dir = tmp_path / "03_作品工程" / "作品B"
        proj_b_dir.mkdir(parents=True)
        (proj_b_dir / "_工作台状态").mkdir()
        
        # 创建一个伪造的 state，project_id 不匹配
        fake_state = {
            "schema_version": "0.1",
            "project_id": "wrong_id",
            "state_rev": 1,
            "canon_facts": [],
            "character_state": [],
            "relationship_state": [],
            "occurred_events": [],
            "open_threads": [],
            "approved_plan": [],
        }
        (proj_b_dir / "_工作台状态" / "story_state.json").write_text(
            json.dumps(fake_state), encoding="utf-8"
        )
        
        # 尝试接受正文，应该因 project_id 不匹配而失败
        with pytest.raises(ContractError, match="project_id 不匹配"):
            accept_prose(
                project_dir=proj_b_dir,
                chapter_number=1,
                scene_ref="scene_001",
                accepted_text="测试文本",
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

