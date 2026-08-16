# -*- coding: utf-8 -*-
"""ProjectWorkspace — 最小真实项目接线层。

不负责文学判断，只做：
- 项目创建/解析
- project_id 隔离
- production 文件落盘
- accepted prose 索引
- Story State 安全持久化
- recent prose 定位
- 多项目防串书
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

# Import frozen runtime contracts
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "StoryWrite"))
from storywrite_entry import apply_settlement, validate_story_state

# Import from StoryDesign/StoryPlan if needed for validation
# (will be added as needed)


class WorkspaceError(Exception):
    """ProjectWorkspace 操作错误。"""
    pass


class ContractError(WorkspaceError):
    """合同违反错误。"""
    pass


def _safe_write_file(path: Path, content: str | bytes) -> None:
    """安全写入文件：先写 temp 再 replace。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=".tmp_")
    try:
        with os.fdopen(fd, "wb" if isinstance(content, bytes) else "w", encoding="utf-8" if isinstance(content, str) else None) as f:
            f.write(content)
        os.replace(tmp_path, str(path))
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _read_file_bytes(path: Path) -> bytes | None:
    """读取文件字节，不存在返回 None。"""
    if not path.exists():
        return None
    return path.read_bytes()


def _sha256(data: bytes) -> str:
    """计算 SHA256。"""
    return hashlib.sha256(data).hexdigest()


def generate_project_id(name: str) -> str:
    """生成稳定 project_id。
    
    基于作品名生成 deterministic ID，确保同一名称始终得到相同 ID。
    """
    # 使用 name 的 hash 作为 project_id 基础
    name_hash = hashlib.sha256(name.encode("utf-8")).hexdigest()[:16]
    return f"proj_{name_hash}"


def validate_project_name(name: str) -> None:
    """验证项目名称合法性。"""
    if not name or not name.strip():
        raise ContractError("作品名不能为空")
    
    # 拒绝危险名称
    dangerous = {".", ".."}
    if name.strip() in dangerous:
        raise ContractError(f"非法作品名：{name}")
    
    # 拒绝路径分隔符注入
    if "/" in name or "\\" in name:
        raise ContractError(f"作品名不能包含路径分隔符：{name}")
    
    # 拒绝空字符
    if "\x00" in name:
        raise ContractError("作品名不能包含空字符")


def get_projects_root() -> Path:
    """获取 03_作品工程 根目录。"""
    return Path(__file__).parent.parent.parent.parent / "03_作品工程"


def list_projects() -> list[dict[str, Any]]:
    """列出所有项目。
    
    Returns:
        项目列表，每个项目包含 name, project_id, project_dir
    """
    root = get_projects_root()
    if not root.exists():
        return []
    
    projects = []
    for item in sorted(root.iterdir()):
        if item.is_dir() and not item.name.startswith("_"):
            state_dir = item / "_工作台状态"
            if state_dir.exists():
                state_file = state_dir / "story_state.json"
                if state_file.exists():
                    state = json.loads(state_file.read_text(encoding="utf-8"))
                    projects.append({
                        "name": item.name,
                        "project_id": state.get("project_id"),
                        "project_dir": str(item),
                    })
    
    return projects


def resolve_project(selector: str | None = None) -> dict[str, Any]:
    """解析项目。
    
    Args:
        selector: 作品名或 project_id。None 时尝试唯一解析。
    
    Returns:
        项目信息字典
    
    Raises:
        ContractError: 无法解析或歧义
    """
    projects = list_projects()
    
    if not projects:
        raise ContractError("没有可用项目")
    
    if selector is None:
        if len(projects) == 1:
            return projects[0]
        else:
            raise ContractError(
                f"存在 {len(projects)} 个项目，必须明确指定作品名或 project_id"
            )
    
    # 精确匹配作品名或 project_id
    for proj in projects:
        if proj["name"] == selector or proj["project_id"] == selector:
            return proj
    
    raise ContractError(f"未找到项目: {selector}")


def create_project(
    name: str,
    author_intent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """创建新项目。
    
    Args:
        name: 作品名
        author_intent: 作者意图（可选）
    
    Returns:
        项目信息
    
    Raises:
        ContractError: 名称非法或项目已存在
    """
    validate_project_name(name)
    
    root = get_projects_root()
    project_dir = root / name
    
    if project_dir.exists():
        raise ContractError(f"项目已存在：{name}")
    
    project_id = generate_project_id(name)
    
    # 创建目录结构
    subdirs = [
        "01_设定与人物",
        "02_规划",
        "03_正文",
        "04_资料与灵感",
        "_工作台状态",
    ]
    for subdir in subdirs:
        (project_dir / subdir).mkdir(parents=True, exist_ok=True)
    
    # 创建 README
    readme_content = f"# {name}\n\n原创小说作品。\n"
    _safe_write_file(project_dir / "README.md", readme_content)
    
    # 初始化 Author Intent
    intent_data = {
        "schema_version": "0.1",
        "project_id": project_id,
        "intent_rev": 1,
        "name": name,
    }
    if author_intent:
        # 合并用户提供的 intent
        intent_data.update(author_intent)
        # 确保 project_id 一致
        intent_data["project_id"] = project_id
    
    _safe_write_file(
        project_dir / "_工作台状态" / "author_intent.json",
        json.dumps(intent_data, ensure_ascii=False, indent=2),
    )
    
    # 初始化 Story State
    state_data = {
        "schema_version": "0.1",
        "project_id": project_id,
        "state_rev": 1,
        "canon_facts": [],
        "character_state": [],
        "relationship_state": [],
        "occurred_events": [],
        "open_threads": [],
        "approved_plan": [],
    }
    
    # Validate before writing
    validate_story_state(state_data)
    
    _safe_write_file(
        project_dir / "_工作台状态" / "story_state.json",
        json.dumps(state_data, ensure_ascii=False, indent=2),
    )
    
    # 初始化 accepted_text_index
    index_data = {
        "schema_version": "0.1",
        "project_id": project_id,
        "entries": [],
    }
    _safe_write_file(
        project_dir / "_工作台状态" / "accepted_text_index.json",
        json.dumps(index_data, ensure_ascii=False, indent=2),
    )
    
    return {
        "name": name,
        "project_id": project_id,
        "project_dir": str(project_dir),
    }


def load_project(project_dir: str | Path) -> dict[str, Any]:
    """加载项目状态。
    
    Args:
        project_dir: 项目目录路径
    
    Returns:
        包含 project_id, state, intent, index 的字典
    """
    project_dir = Path(project_dir)
    state_dir = project_dir / "_工作台状态"
    
    if not state_dir.exists():
        raise ContractError(f"项目状态目录不存在：{state_dir}")
    
    # 加载 Story State
    state_file = state_dir / "story_state.json"
    if not state_file.exists():
        raise ContractError(f"Story State 不存在：{state_file}")
    
    state = json.loads(state_file.read_text(encoding="utf-8"))
    validate_story_state(state)
    
    # 加载 Author Intent
    intent_file = state_dir / "author_intent.json"
    intent = None
    if intent_file.exists():
        intent = json.loads(intent_file.read_text(encoding="utf-8"))
    
    # 加载 accepted_text_index
    index_file = state_dir / "accepted_text_index.json"
    index = None
    if index_file.exists():
        index = json.loads(index_file.read_text(encoding="utf-8"))
    
    return {
        "project_id": state["project_id"],
        "project_dir": str(project_dir),
        "state": state,
        "intent": intent,
        "index": index,
    }


def accept_prose(
    project_dir: str | Path,
    chapter_number: int,
    scene_ref: str,
    accepted_text: str,
    settlement: dict[str, Any] | None = None,
    author_accepted: bool = False,
) -> dict[str, Any]:
    """接受正文并持久化。
    
    Args:
        project_dir: 项目目录
        chapter_number: 章节号
        scene_ref: 场景引用
        accepted_text: 接受的正文
        settlement: settlement candidates（可选）
        author_accepted: 作者是否接受（必须为 True）
    
    Returns:
        操作结果
    
    Raises:
        ContractError: 验证失败
    """
    if not author_accepted:
        raise ContractError("必须设置 author_accepted=True 才能接受正文")
    
    if not scene_ref:
        raise ContractError("scene_ref 不能为空")
    
    project_dir = Path(project_dir)
    proj = load_project(project_dir)
    project_id = proj["project_id"]
    state = proj["state"]
    index = proj["index"] or {"schema_version": "0.1", "project_id": project_id, "entries": []}
    
    # 验证 project_id 一致性
    if state["project_id"] != project_id:
        raise ContractError("Story State project_id 不匹配")
    
    if index["project_id"] != project_id:
        raise ContractError("accepted_text_index project_id 不匹配")
    
    # 检查 scene_ref 是否已使用
    existing_refs = {e["scene_ref"] for e in index.get("entries", [])}
    if scene_ref in existing_refs:
        raise ContractError(f"scene_ref 已使用：{scene_ref}")
    
    # 验证 settlement（如果提供）
    if settlement:
        if settlement.get("scene_ref") != scene_ref:
            raise ContractError("settlement.scene_ref 必须等于 scene_ref")
        
        # 检查 settlement candidate 的 project_id（如果携带）
        for candidate in settlement.get("candidates", []):
            cand_proj_id = candidate.get("project_id")
            if cand_proj_id and cand_proj_id != project_id:
                raise ContractError("settlement candidate project_id 不匹配")
    
    # 准备文件路径
    chapter_dir = project_dir / "03_正文"
    chapter_file = chapter_dir / f"第{chapter_number:03d}章.md"
    
    # === 事务开始 ===
    # 1. 保存原始 snapshot
    snapshots = {}
    new_files = []
    
    # Snapshot: chapter file
    if chapter_file.exists():
        snapshots["chapter"] = _read_file_bytes(chapter_file)
    else:
        new_files.append(chapter_file)
    
    # Snapshot: index
    index_file = project_dir / "_工作台状态" / "accepted_text_index.json"
    snapshots["index"] = _read_file_bytes(index_file)
    
    # Snapshot: state
    state_file = project_dir / "_工作台状态" / "story_state.json"
    snapshots["state"] = _read_file_bytes(state_file)
    
    try:
        # 2. 在内存中完成所有操作
        
        # 2a. 应用 settlement（如果提供且有效）
        new_state = state
        if settlement:
            # 绑定 project_id 到 settlement candidates（如果缺失）
            settlement_copy = json.loads(json.dumps(settlement))
            for candidate in settlement_copy.get("candidates", []):
                if "project_id" not in candidate:
                    candidate["project_id"] = project_id
            
            # 调用 frozen apply_settlement
            settlement_result = apply_settlement(
                state=state,
                settlement=settlement_copy,
                mode="production",
                author_accepted=True,
                accepted_scene_ref=scene_ref,
            )
            new_state = settlement_result.get("new_state", state)
            validate_story_state(new_state)
        
        # 2b. 准备章节内容
        if chapter_file.exists():
            existing_content = chapter_file.read_text(encoding="utf-8")
            # 追加到末尾
            new_chapter_content = existing_content + "\n\n" + accepted_text
        else:
            new_chapter_content = accepted_text
        
        # 2c. 更新 accepted_text_index
        start_char = len(existing_content) + 2 if chapter_file.exists() else 0  # +2 for \n\n
        end_char = start_char + len(accepted_text)
        content_sha = _sha256(accepted_text.encode("utf-8"))
        
        new_entry = {
            "sequence": len(index.get("entries", [])) + 1,
            "scene_ref": scene_ref,
            "chapter_number": chapter_number,
            "chapter_path": f"03_正文/第{chapter_number:03d}章.md",
            "start_char": start_char,
            "end_char": end_char,
            "content_sha256": content_sha,
            "state_rev_after": new_state.get("state_rev", state.get("state_rev", 1)),
        }
        
        new_index = json.loads(json.dumps(index))
        new_index.setdefault("entries", []).append(new_entry)
        
        # 3. 所有验证通过后写入
        
        # 3a. 写章节文件
        _safe_write_file(chapter_file, new_chapter_content)
        
        # 3b. 写 index
        _safe_write_file(
            index_file,
            json.dumps(new_index, ensure_ascii=False, indent=2),
        )
        
        # 3c. 写 state（如果有变化）
        if new_state != state:
            _safe_write_file(
                state_file,
                json.dumps(new_state, ensure_ascii=False, indent=2),
            )
        
        return {
            "success": True,
            "chapter_path": str(chapter_file),
            "scene_ref": scene_ref,
            "state_rev": new_state.get("state_rev"),
        }
    
    except Exception as e:
        # 4. Rollback
        rollback_failed = []
        
        # 恢复 snapshot
        for name, data in snapshots.items():
            if name == "chapter":
                path = chapter_file
            elif name == "index":
                path = index_file
            elif name == "state":
                path = state_file
            else:
                continue
            
            if data is not None:
                try:
                    _safe_write_file(path, data)
                except Exception:
                    rollback_failed.append(str(path))
            else:
                # 原文件不存在，删除新建的文件
                try:
                    if path.exists():
                        path.unlink()
                except Exception:
                    rollback_failed.append(str(path))
        
        # 清理新建的文件
        for new_file in new_files:
            try:
                if new_file.exists():
                    new_file.unlink()
            except Exception:
                rollback_failed.append(str(new_file))
        
        if rollback_failed:
            raise WorkspaceError(
                f"Rollback 失败，需要手动恢复：{rollback_failed}"
            ) from e
        
        raise WorkspaceError(f"接受正文失败，已回滚：{e}") from e


def get_recent_prose(project_dir: str | Path, max_chars: int = 2000) -> str | None:
    """获取最近接受的正文。
    
    Args:
        project_dir: 项目目录
        max_chars: 最大字符数
    
    Returns:
        最近接受的正文，或 None
    """
    project_dir = Path(project_dir)
    proj = load_project(project_dir)
    index = proj["index"]
    
    if not index or not index.get("entries"):
        return None
    
    # 获取最后一个 entry
    last_entry = index["entries"][-1]
    
    # 读取章节文件
    chapter_path = project_dir / last_entry["chapter_path"]
    if not chapter_path.exists():
        raise WorkspaceError(f"章节文件不存在：{chapter_path}")
    
    chapter_content = chapter_path.read_text(encoding="utf-8")
    
    # 提取对应范围
    start = last_entry["start_char"]
    end = last_entry["end_char"]
    
    if start >= len(chapter_content) or end > len(chapter_content):
        raise WorkspaceError("accepted_text_index 与章节内容不一致（ACCEPTED_TEXT_INDEX_STALE）")
    
    accepted_text = chapter_content[start:end]
    
    # 验证 SHA
    content_sha = _sha256(accepted_text.encode("utf-8"))
    if content_sha != last_entry["content_sha256"]:
        raise WorkspaceError("accepted_text_index SHA 不匹配（ACCEPTED_TEXT_INDEX_STALE）")
    
    # 返回末尾 max_chars
    if len(accepted_text) > max_chars:
        return accepted_text[-max_chars:]
    
    return accepted_text

