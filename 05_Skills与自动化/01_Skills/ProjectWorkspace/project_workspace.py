# -*- coding: utf-8 -*-
"""ProjectWorkspace — 最小真实项目接线层（F0.1）。

不负责文学判断，只做：
- 项目创建/解析（author_intent 必需并通过 frozen validate_author_intent）
- project_id 隔离与跨项目拒绝
- production 文件落盘（正式正文、Story State、accepted_text_index）
- accepted prose 索引维护
- persist_state_transition：通用 state 安全持久化（stale/cross-project guard）
- recent prose 定位（基于正式正文 + accepted_text_index）
- acceptance 必须经过 frozen StoryWrite.apply_settlement gate
- 多项目防串书
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Frozen runtime imports — NEVER copy their rules; always call them directly.
# ---------------------------------------------------------------------------
_SKILLS_ROOT = Path(__file__).resolve().parent.parent

if str(_SKILLS_ROOT / "StoryDesign") not in sys.path:
    sys.path.insert(0, str(_SKILLS_ROOT / "StoryDesign"))
if str(_SKILLS_ROOT / "StoryWrite") not in sys.path:
    sys.path.insert(0, str(_SKILLS_ROOT / "StoryWrite"))

from story_runtime import (  # noqa: E402  # StoryDesign frozen runtime
    ContractError as FrozenContractError,
    validate_author_intent,
    validate_story_state,
    create_decision_record,
    make_planning_diff,
    apply_diff as storydesign_apply_diff,
)

from storywrite_entry import apply_settlement  # noqa: E402  # StoryWrite frozen runtime


class WorkspaceError(Exception):
    """ProjectWorkspace 操作错误。"""


class ContractError(WorkspaceError):
    """合同违反错误。"""


def _safe_write_file(path: Path, content: str | bytes) -> None:
    """安全写入文件：先写 temp 再 replace。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=".tmp_")
    try:
        if isinstance(content, bytes):
            with os.fdopen(fd, "wb") as f:
                f.write(content)
        else:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
        os.replace(tmp_path, str(path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def generate_project_id(name: str) -> str:
    """生成稳定 project_id（deterministic）。"""
    name_hash = hashlib.sha256(name.encode("utf-8")).hexdigest()[:16]
    return f"proj_{name_hash}"


def validate_project_name(name: str) -> None:
    """验证项目名称合法性。"""
    if not name or not name.strip():
        raise ContractError("作品名不能为空")
    dangerous = {".", ".."}
    if name.strip() in dangerous:
        raise ContractError(f"非法作品名：{name}")
    if "/" in name or "\\" in name:
        raise ContractError(f"作品名不能包含路径分隔符：{name}")
    if "\x00" in name:
        raise ContractError("作品名不能包含空字符")


def get_projects_root() -> Path:
    """获取 03_作品工程 根目录。"""
    return Path(__file__).resolve().parent.parent.parent.parent / "03_作品工程"


def list_projects() -> list[dict[str, Any]]:
    """列出所有项目。"""
    root = get_projects_root()
    if not root.exists():
        return []
    projects: list[dict[str, Any]] = []
    for item in sorted(root.iterdir()):
        if item.is_dir() and not item.name.startswith("_"):
            state_dir = item / "_工作台状态"
            state_file = state_dir / "story_state.json"
            intent_file = state_dir / "author_intent.json"
            index_file = state_dir / "accepted_text_index.json"
            if state_file.exists() and intent_file.exists() and index_file.exists():
                try:
                    state = _read_json(state_file)
                    projects.append({
                        "name": item.name,
                        "project_id": state.get("project_id"),
                        "project_dir": str(item),
                    })
                except Exception:
                    continue
    return projects


def resolve_project(selector: str | None = None) -> dict[str, Any]:
    """解析项目。selector=None 时仅当唯一项目才成功。"""
    projects = list_projects()
    if not projects:
        raise ContractError("没有可用项目")
    if selector is None:
        if len(projects) == 1:
            return projects[0]
        raise ContractError(
            f"存在 {len(projects)} 个项目，必须明确指定作品名或 project_id"
        )
    for proj in projects:
        if proj["name"] == selector or proj["project_id"] == selector:
            return proj
    raise ContractError(f"未找到项目: {selector}")


def _initial_story_state(project_id: str) -> dict[str, Any]:
    """构造初始 Story State（通过 frozen validate_story_state）。"""
    state = {
        "project_id": project_id,
        "state_rev": 1,
        "canon_facts": [],
        "character_state": [],
        "relationship_state": [],
        "occurred_events": [],
        "open_threads": [],
        "approved_plan": [],
        "last_authority_source": "workspace:init",
    }
    validate_story_state(state)
    return state


def _initial_accepted_index(project_id: str) -> dict[str, Any]:
    return {"project_id": project_id, "entries": []}


def create_project(
    name: str,
    author_intent: dict[str, Any],
) -> dict[str, Any]:
    """创建新项目。author_intent 必填且必须通过 frozen validate_author_intent。

    Agent 提供语义字段；ProjectWorkspace 负责注入 project_id + intent_rev=1，
    然后调用 validate_author_intent。caller 传入的 project_id 若与生成值不一致则拒绝。
    """
    if author_intent is None or not isinstance(author_intent, dict):
        raise ContractError("create_project 需要完整 author_intent")

    validate_project_name(name)
    root = get_projects_root()
    project_dir = root / name
    if project_dir.exists():
        raise ContractError(f"项目已存在：{name}")

    project_id = generate_project_id(name)

    # Caller must not silently inject a mismatched project_id.
    caller_pid = author_intent.get("project_id")
    if caller_pid is not None and caller_pid != project_id:
        raise ContractError(
            f"author_intent.project_id 与生成值不一致（{caller_pid} vs {project_id}）"
        )

    # Workspace injects project_id + intent_rev; agent supplies semantic fields.
    intent = dict(author_intent)
    intent["project_id"] = project_id
    intent.setdefault("intent_rev", 1)

    # Frozen gate: incomplete / illegal intent is rejected before any write.
    try:
        validate_author_intent(intent)
    except FrozenContractError as e:
        raise ContractError(f"author_intent 未通过 frozen validate_author_intent: {e}") from e

    state = _initial_story_state(project_id)
    index = _initial_accepted_index(project_id)

    # Create directory tree.
    subdirs = [
        "01_设定与人物",
        "02_规划",
        "03_正文",
        "04_资料与灵感",
        "_工作台状态",
    ]
    for sub in subdirs:
        (project_dir / sub).mkdir(parents=True, exist_ok=False)

    # Persist canonical workspace files atomically.
    state_dir = project_dir / "_工作台状态"
    _safe_write_file(state_dir / "author_intent.json", json.dumps(intent, ensure_ascii=False, indent=2))
    _safe_write_file(state_dir / "story_state.json", json.dumps(state, ensure_ascii=False, indent=2))
    _safe_write_file(state_dir / "accepted_text_index.json", json.dumps(index, ensure_ascii=False, indent=2))
    _safe_write_file(project_dir / "README.md", f"# {name}\n\n作品工程。\n")

    return {
        "name": name,
        "project_id": project_id,
        "project_dir": str(project_dir),
    }


def load_project(project_dir: str | Path) -> dict[str, Any]:
    """加载项目并执行 frozen contract 校验 + project_id 一致性检查。"""
    project_dir = Path(project_dir)
    state_dir = project_dir / "_工作台状态"
    intent_file = state_dir / "author_intent.json"
    state_file = state_dir / "story_state.json"
    index_file = state_dir / "accepted_text_index.json"

    if not intent_file.exists():
        raise ContractError(f"缺少 author_intent.json：{project_dir}")
    if not state_file.exists():
        raise ContractError(f"缺少 story_state.json：{project_dir}")
    if not index_file.exists():
        raise ContractError(f"缺少 accepted_text_index.json：{project_dir}")

    try:
        intent = _read_json(intent_file)
        state = _read_json(state_file)
        index = _read_json(index_file)
    except json.JSONDecodeError as e:
        raise ContractError(f"项目 JSON 非法：{e}") from e

    # Frozen gates.
    try:
        validate_author_intent(intent)
        validate_story_state(state)
    except FrozenContractError as e:
        raise ContractError(f"frozen contract 校验失败：{e}") from e

    # Cross-artifact project_id consistency.
    pid_intent = intent.get("project_id")
    pid_state = state.get("project_id")
    pid_index = index.get("project_id")
    if not (pid_intent and pid_state and pid_index):
        raise ContractError("项目工件缺少 project_id")
    if not (pid_intent == pid_state == pid_index):
        raise ContractError(
            f"project_id 不一致：intent={pid_intent}, state={pid_state}, index={pid_index}"
        )

    return {
        "name": project_dir.name,
        "project_id": pid_state,
        "project_dir": str(project_dir),
        "intent": intent,
        "state": state,
        "index": index,
    }


def persist_state_transition(
    project_dir: str | Path,
    expected_base_state: dict[str, Any],
    new_state: dict[str, Any],
) -> dict[str, Any]:
    """通用 state 安全持久化。

    - 磁盘 current.project_id == expected_base_state.project_id == new_state.project_id
    - current.state_rev == expected_base_state.state_rev（stale base 拒绝）
    - frozen validate_story_state(new_state)
    - 不允许绕过 frozen runtime 写入任意 JSON
    - 不判断 Decision 是否正确；只持久化 frozen runtime 已生成的合法 new_state
    - 原子写入（temp + os.replace）
    """
    project_dir = Path(project_dir)
    state_file = project_dir / "_工作台状态" / "story_state.json"
    if not state_file.exists():
        raise ContractError(f"缺少 story_state.json：{project_dir}")

    current = _read_json(state_file)

    pid_current = current.get("project_id")
    pid_expected = expected_base_state.get("project_id")
    pid_new = new_state.get("project_id")
    if not (pid_current and pid_expected and pid_new):
        raise ContractError("persist_state_transition 需要完整 project_id")
    if not (pid_current == pid_expected == pid_new):
        raise ContractError(
            f"persist_state_transition project_id 不一致：current={pid_current}, "
            f"expected={pid_expected}, new={pid_new}"
        )

    if current.get("state_rev") != expected_base_state.get("state_rev"):
        raise ContractError(
            f"stale base state_rev：disk={current.get('state_rev')}, "
            f"expected={expected_base_state.get('state_rev')}"
        )

    try:
        validate_story_state(new_state)
    except FrozenContractError as e:
        raise ContractError(f"new_state 未通过 frozen validate_story_state: {e}") from e

    _safe_write_file(state_file, json.dumps(new_state, ensure_ascii=False, indent=2))
    return {"success": True, "state_rev": new_state.get("state_rev"), "project_id": pid_new}


def accept_prose(
    *,
    project_dir: str | Path,
    chapter_number: int,
    scene_ref: str,
    accepted_text: str,
    settlement: dict[str, Any],
    author_accepted: bool = False,
) -> dict[str, Any]:
    """接受正文。settlement 必需；每次 acceptance 必须经过 frozen apply_settlement gate。"""
    if not author_accepted:
        raise ContractError("accept_prose 必须设置 author_accepted=True")
    if not isinstance(settlement, dict):
        raise ContractError("accept_prose 需要 settlement（可为 {'scene_ref':..., 'candidates':[]}）")
    if not settlement.get("scene_ref"):
        raise ContractError("settlement.scene_ref 不能为空")
    if not isinstance(settlement.get("candidates"), list):
        raise ContractError("settlement.candidates 必须是列表")

    project_dir = Path(project_dir)
    proj = load_project(project_dir)
    state = proj["state"]
    index = proj["index"]

    # Frozen gate: every acceptance goes through StoryWrite.apply_settlement.
    try:
        settlement_result = apply_settlement(
            state=state,
            settlement=settlement,
            mode="production",
            author_accepted=True,
            accepted_scene_ref=scene_ref,
        )
    except FrozenContractError as e:
        raise ContractError(f"frozen apply_settlement 拒绝：{e}") from e

    new_state = settlement_result.get("new_state", state)

    # Prepare chapter paths.
    chapter_file = project_dir / "03_正文" / f"第{chapter_number:03d}章.md"
    state_file = project_dir / "_工作台状态" / "story_state.json"
    index_file = project_dir / "_工作台状态" / "accepted_text_index.json"

    # Snapshots for rollback.
    snapshots = {
        "chapter": _read_file_bytes(chapter_file),
        "index": _read_file_bytes(index_file),
        "state": _read_file_bytes(state_file),
    }
    new_files: list[Path] = []
    if not chapter_file.exists():
        new_files.append(chapter_file)

    try:
        # Build new chapter content.
        if chapter_file.exists():
            existing_content = chapter_file.read_text(encoding="utf-8")
            new_chapter_content = existing_content + "\n\n" + accepted_text
        else:
            existing_content = ""
            new_chapter_content = accepted_text

        start_char = len(existing_content) + (2 if existing_content else 0)
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
            "state_rev_after": new_state.get("state_rev", state.get("state_rev")),
        }
        new_index = json.loads(json.dumps(index))
        new_index.setdefault("entries", []).append(new_entry)

        # Atomic writes.
        _safe_write_file(chapter_file, new_chapter_content)
        _safe_write_file(index_file, json.dumps(new_index, ensure_ascii=False, indent=2))
        if new_state != state:
            _safe_write_file(state_file, json.dumps(new_state, ensure_ascii=False, indent=2))

        return {
            "success": True,
            "chapter_path": str(chapter_file),
            "scene_ref": scene_ref,
            "state_rev": new_state.get("state_rev"),
        }
    except Exception as e:
        # Rollback on any failure.
        rollback_failed: list[str] = []
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
                try:
                    if path.exists():
                        path.unlink()
                except Exception:
                    rollback_failed.append(str(path))
        for nf in new_files:
            try:
                if nf.exists():
                    nf.unlink()
            except Exception:
                rollback_failed.append(str(nf))
        if rollback_failed:
            raise WorkspaceError(f"Rollback 失败，需要手动恢复：{rollback_failed}") from e
        raise WorkspaceError(f"接受正文失败，已回滚：{e}") from e


def _read_file_bytes(path: Path) -> bytes | None:
    if not path.exists():
        return None
    return path.read_bytes()


def get_recent_prose(project_dir: str | Path, max_chars: int = 2000) -> str | None:
    """获取最近接受的正文（基于正式正文 + accepted_text_index）。

    This function reads only from production chapter files under 03_正文/ and
    validates the accepted_text_index SHA/range against disk. It does NOT
    consult Context packages or any derivative cache.
    """
    project_dir = Path(project_dir)
    proj = load_project(project_dir)
    index = proj["index"]
    if not index or not index.get("entries"):
        return None

    last_entry = index["entries"][-1]
    chapter_path = project_dir / last_entry["chapter_path"]
    if not chapter_path.exists():
        raise WorkspaceError(f"章节文件不存在：{chapter_path}")

    chapter_content = chapter_path.read_text(encoding="utf-8")
    start = last_entry["start_char"]
    end = last_entry["end_char"]
    if start >= len(chapter_content) or end > len(chapter_content):
        raise WorkspaceError("accepted_text_index 与章节内容不一致（ACCEPTED_TEXT_INDEX_STALE）")

    accepted_text = chapter_content[start:end]
    content_sha = _sha256(accepted_text.encode("utf-8"))
    if content_sha != last_entry["content_sha256"]:
        raise WorkspaceError("accepted_text_index SHA 不匹配（ACCEPTED_TEXT_INDEX_STALE）")

    if len(accepted_text) > max_chars:
        return accepted_text[-max_chars:]
    return accepted_text
