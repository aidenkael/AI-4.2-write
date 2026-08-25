# -*- coding: utf-8 -*-
"""灵感箱 Author Operations：轻量、非权威、无模型调用的本地灵感收件箱。

职责（对应 UI 1.0 Ideas 真实消费者）：
- list / create / delete / mark_used 四项本地操作；
- 单一原子 JSON 文件（ideas.json），存放在既有 app 配置目录约定
  （AI_WRITE_CONFIG_DIR 优先，否则 ~/.ai-write），与 Settings 同目录；
- 不进入 Story State、不是 Canon、不是 Skill 输出、不携带任何项目 authority；
- 绝不调用模型 / Agent / Skill；时间戳来自后台真实写入时刻（无假时间）。

schema（schema_version 1）：
  {
    "schema_version": 1,
    "items": [
      {
        "id": "<uuid>",
        "content": "作者记录的灵感文本",
        "kind": "text" | "link",
        "created_at": "<UTC ISO 8601>",
        "used_project_ids": ["<project_id>", ...]   # 可选，标记已用于某作品
      }
    ]
  }

写入纪律：原子写（同目录临时文件 + os.replace），绝不半写；严格 schema 校验。
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

IDEAS_FILENAME = "ideas.json"
SCHEMA_VERSION = 1
VALID_KINDS = ("text", "link")


class IdeasError(Exception):
    """灵感箱操作错误（面向 UI 的稳定错误类型，普通用户可读）。"""


# ---------------------------------------------------------------------------
# 路径与持久化（复用既有配置目录约定，与 SettingsStore 一致）
# ---------------------------------------------------------------------------

def get_config_dir() -> Path:
    """app 配置目录（测试可 monkeypatch 本函数或设置 AI_WRITE_CONFIG_DIR）。"""
    env = os.environ.get("AI_WRITE_CONFIG_DIR")
    if env:
        return Path(env)
    return Path.home() / ".ai-write"


def _ideas_path() -> Path:
    return get_config_dir() / IDEAS_FILENAME


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load() -> dict[str, Any]:
    """读取 ideas.json；不存在返回空结构；结构非法抛 IdeasError（不猜数据）。"""
    path = _ideas_path()
    if not path.exists():
        return {"schema_version": SCHEMA_VERSION, "items": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IdeasError(f"灵感箱数据损坏，无法读取：{exc}") from exc
    if not isinstance(data, dict):
        raise IdeasError("灵感箱数据损坏（应为 JSON 对象）。")
    if not isinstance(data.get("items"), list):
        raise IdeasError("灵感箱数据损坏（缺少 items 列表）。")
    return data


def _save(data: dict[str, Any]) -> None:
    """原子写：临时文件 + os.replace，绝不半写。"""
    path = _ideas_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise IdeasError(f"无法创建配置目录：{exc}") from exc
    tmp = path.with_suffix(".json.tmp")
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    try:
        tmp.write_text(text, encoding="utf-8", newline="\n")
        os.replace(tmp, path)
    except OSError as exc:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise IdeasError(f"保存灵感失败：{exc}") from exc


def _validate_item(item: Any) -> None:
    """校验单条灵感；类型错误抛 IdeasError（不自动修复）。"""
    if not isinstance(item, dict):
        raise IdeasError("灵感条目类型错误（应为对象）。")
    if not isinstance(item.get("id"), str) or not item["id"]:
        raise IdeasError("灵感条目缺少有效 id。")
    if not isinstance(item.get("content"), str) or not item["content"].strip():
        raise IdeasError("灵感内容不能为空。")
    if item.get("kind") not in VALID_KINDS:
        raise IdeasError(f"灵感类型非法：{item.get('kind')!r}。")
    used = item.get("used_project_ids", [])
    if not isinstance(used, list) or any(not isinstance(p, str) for p in used):
        raise IdeasError("灵感条目 used_project_ids 类型错误。")
    if not isinstance(item.get("created_at"), str):
        raise IdeasError("灵感条目缺少有效 created_at。")


def _item_view(item: dict[str, Any]) -> dict[str, Any]:
    """返回给 UI 的最小展示形状（不泄露任何内部字段，只回真实字段）。"""
    return {
        "id": item["id"],
        "content": item["content"],
        "kind": item["kind"],
        "created_at": item["created_at"],
        "used_project_ids": list(item.get("used_project_ids") or []),
    }


# ---------------------------------------------------------------------------
# 操作
# ---------------------------------------------------------------------------

def list_ideas() -> dict[str, Any]:
    """列出全部灵感（按 created_at 倒序：最新在前）。"""
    data = _load()
    for item in data["items"]:
        _validate_item(item)
    items = sorted(
        data["items"], key=lambda i: i.get("created_at") or "", reverse=True
    )
    return {"ideas": [_item_view(i) for i in items]}


def create_idea(content: str, kind: str = "text") -> dict[str, Any]:
    """新增一条灵感；原子写入；无任何模型调用。"""
    content = (content or "").strip()
    if not content:
        raise IdeasError("请先写下一句灵感。")
    if kind not in VALID_KINDS:
        raise IdeasError(f"灵感类型非法：{kind!r}。")
    data = _load()
    item = {
        "id": uuid.uuid4().hex,
        "content": content,
        "kind": kind,
        "created_at": _now_iso(),
        "used_project_ids": [],
    }
    data["items"].append(item)
    _save(data)
    return {"idea": _item_view(item)}


def delete_idea(idea_id: str) -> dict[str, Any]:
    """删除一条灵感（幂等：不存在也返回成功，不抛错）。"""
    idea_id = (idea_id or "").strip()
    if not idea_id:
        raise IdeasError("缺少灵感标识（idea id）。")
    data = _load()
    data["items"] = [i for i in data["items"] if i.get("id") != idea_id]
    _save(data)
    return {"deleted": idea_id}


def mark_idea_used(idea_id: str, project_id: str) -> dict[str, Any]:
    """可选：把一条灵感标记为已用于某作品（只追加 used_project_ids，非权威）。"""
    idea_id = (idea_id or "").strip()
    project_id = (project_id or "").strip()
    if not idea_id:
        raise IdeasError("缺少灵感标识（idea id）。")
    if not project_id:
        raise IdeasError("缺少作品标识（project_id）。")
    data = _load()
    updated: dict[str, Any] | None = None
    for item in data["items"]:
        if item.get("id") == idea_id:
            used = list(item.get("used_project_ids") or [])
            if project_id not in used:
                used.append(project_id)
            item["used_project_ids"] = used
            updated = item
            break
    if updated is None:
        raise IdeasError("这条灵感不存在，可能已被删除。")
    _save(data)
    return {"idea": _item_view(updated)}
