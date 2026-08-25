# -*- coding: utf-8 -*-
"""灵感箱 targeted tests：原子 CRUD、非权威、无模型调用。"""
import json
from pathlib import Path

import pytest

from operations import ideas


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_WRITE_CONFIG_DIR", str(tmp_path / "cfg"))
    return tmp_path / "cfg"


def test_create_and_list(isolated):
    created = ideas.create_idea("雨后傍晚的天台，一只橘猫。", kind="text")
    assert created["idea"]["id"]
    assert created["idea"]["content"] == "雨后傍晚的天台，一只橘猫。"
    assert created["idea"]["kind"] == "text"
    assert created["idea"]["used_project_ids"] == []
    assert created["idea"]["created_at"]

    items = ideas.list_ideas()["ideas"]
    assert len(items) == 1
    assert items[0]["id"] == created["idea"]["id"]


def test_create_link_kind(isolated):
    created = ideas.create_idea("https://example.com", kind="link")
    assert created["idea"]["kind"] == "link"


def test_create_rejects_invalid_kind(isolated):
    with pytest.raises(ideas.IdeasError):
        ideas.create_idea("内容", kind="文件")


def test_create_rejects_empty(isolated):
    with pytest.raises(ideas.IdeasError):
        ideas.create_idea("   ")


def test_delete_idempotent(isolated):
    created = ideas.create_idea("一条灵感")
    assert ideas.delete_idea(created["idea"]["id"])["deleted"] == created["idea"]["id"]
    assert ideas.list_ideas()["ideas"] == []
    # 幂等：再删一次不抛错
    assert ideas.delete_idea(created["idea"]["id"])["deleted"] == created["idea"]["id"]


def test_delete_missing_id_rejected(isolated):
    with pytest.raises(ideas.IdeasError):
        ideas.delete_idea("")


def test_mark_used(isolated):
    created = ideas.create_idea("一条灵感")
    updated = ideas.mark_idea_used(created["idea"]["id"], "project-x")
    assert updated["idea"]["used_project_ids"] == ["project-x"]
    # 重复标记不重复追加
    updated2 = ideas.mark_idea_used(created["idea"]["id"], "project-x")
    assert updated2["idea"]["used_project_ids"] == ["project-x"]


def test_mark_used_missing_idea_rejected(isolated):
    with pytest.raises(ideas.IdeasError):
        ideas.mark_idea_used("nonexistent", "project-x")


def test_atomic_write_no_half_file(isolated):
    ideas.create_idea("第一条")
    ideas.create_idea("第二条")
    # 磁盘上只有一个 ideas.json，无 .tmp 残留
    files = list(isolated.iterdir())
    assert [f.name for f in files] == ["ideas.json"]
    data = json.loads((isolated / "ideas.json").read_text(encoding="utf-8"))
    assert data["schema_version"] == ideas.SCHEMA_VERSION
    assert len(data["items"]) == 2


def test_no_model_called(isolated, monkeypatch):
    """灵感操作绝不调用任何模型/Agent/Skill（这里以无外部调用的事实保证）。"""
    created = ideas.create_idea("纯本地操作")
    assert created["idea"]["id"]
    # 只读/删除/mark_used 均为纯本地文件操作
    ideas.mark_idea_used(created["idea"]["id"], "p1")
    ideas.delete_idea(created["idea"]["id"])
    assert ideas.list_ideas()["ideas"] == []
