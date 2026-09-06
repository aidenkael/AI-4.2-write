# -*- coding: utf-8 -*-
"""素材目录 targeted tests：只读目录、显式 refresh、只读 inbox scan、确定性 intake 事务。"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from operations import materials  # noqa: E402


def _ledger():
    return {
        "schema_version": "1.0",
        "assets": [
            {
                "id": "book_0001", "name": "样例作品", "type": "REFERENCE_WORK",
                "author": "作者甲", "tags": ["标签1"], "notes": "备注",
                "files": [{"path": "01_原著/样例作品/样例.epub", "sha256": "a" * 64, "primary": True}],
                "purification": {"status": "可用", "evidence": "sourceprepare_metadata"},
                "knowledge": {"status": "可用"},
            },
        ],
        "containers": [],
    }


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    root = tmp_path / "root"
    (root / "01_原始素材").mkdir(parents=True)
    monkeypatch.setattr(materials, "get_repo_root", lambda: root)
    return root


def _write_ledger(root):
    ledger_path = root / "01_原始素材" / "素材资产.json"
    ledger_path.write_text(json.dumps(_ledger(), ensure_ascii=False), encoding="utf-8")
    return ledger_path


def test_list_materials_reads_real_ledger(isolated, monkeypatch):
    monkeypatch.setattr(materials, "_knowledge_is_discoverable", lambda asset: True)
    _write_ledger(isolated)
    result = materials.list_materials()
    assert len(result["materials"]) == 1
    m = result["materials"][0]
    assert m["id"] == "book_0001"
    assert m["name"] == "样例作品"
    assert m["type"] == "REFERENCE_WORK"
    assert m["author"] == "作者甲"
    assert m["type_label"] == "原著"
    assert m["source_formats"] == ["EPUB"]
    assert m["state"] == "ready"


def test_list_materials_missing_ledger_rejected(isolated):
    with pytest.raises(materials.MaterialsError):
        materials.list_materials()


def test_author_group_classification_mapping(monkeypatch):
    """作者面状态只来自真实生命周期投影。"""
    monkeypatch.setattr(materials, "_knowledge_is_discoverable", lambda asset: True)
    cases = [
        # (purification, knowledge, expected_group, callable)
        ("可用", "可用", "usable", True),
        ("可用", "未开始", "pending", False),
        ("需复核", "未开始", "needs_attention", False),
        ("未处理", "未开始", "pending", False),
    ]
    for pur, know, group, callable_ok in cases:
        item = {"purification": {"status": pur}, "knowledge": {"status": know}}
        classified = materials._classify_author_group(item)
        assert classified["author_group"] == group, (pur, know)
        assert classified["writing_callable"] is callable_ok, (pur, know)
        assert classified["state"] in {"ready", "pending_distill", "needs_attention", "pending_prepare"}


def test_list_materials_includes_author_facing_fields(isolated, monkeypatch):
    monkeypatch.setattr(materials, "_knowledge_is_discoverable", lambda asset: True)
    ledger = _ledger()
    # 第二个素材：有素材但还没提炼知识
    ledger["assets"].append({
        "id": "book_0002", "name": "待整理作品", "type": "LOOSE_MATERIAL",
        "author": "", "tags": [], "notes": "",
        "files": [{"path": "03_其他/待整理/资料.pdf", "sha256": "b" * 64, "primary": True}],
        "purification": {"status": "不适用"},
        "knowledge": {"status": "未开始"},
    })
    (isolated / "01_原始素材" / "素材资产.json").write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
    result = materials.list_materials()
    by_id = {m["id"]: m for m in result["materials"]}
    assert by_id["book_0001"]["author_group"] == "usable"
    assert by_id["book_0001"]["writing_callable"] is True
    assert by_id["book_0002"]["author_group"] == "pending"
    assert by_id["book_0002"]["writing_callable"] is False


def test_author_learning_markdown_parser_and_format_safety():
    summary, sections = materials._parse_learning_markdown("# 标题\n> 说明\n\n总览正文\n\n## 可以学习\n第一段\n")
    assert summary == "总览正文"
    assert sections == [{"title": "可以学习", "body": "第一段"}]
    assert materials._source_formats({"files": [{"path": "private/path/book.epub", "sha256": "secret"}]}) == ["EPUB"]


def test_refresh_uses_materialintake(isolated, monkeypatch):
    _write_ledger(isolated)
    catalog, intake, post_action = materials._load_materialintake()

    called = {}
    # §5：刷新先 reconcile 手动文件夹编辑（无编辑 → changed=False），再常规确定性刷新。
    monkeypatch.setattr(intake, "reconcile_manual_edits",
                        lambda root: {"ok": True, "changed": False, "registered": [],
                                      "moved": [], "renamed": [], "missing_sources": []})
    monkeypatch.setattr(catalog, "refresh_and_render",
                        lambda root, check_only=False, tolerate_missing=False: (called.setdefault("rc", 0) and 0))
    result = materials.refresh_materials()
    assert result["assets"] == 1
    assert result["files"] == 1
    assert result["containers"] == 0
    assert "rc" in called


def test_scan_inbox_read_only(isolated, monkeypatch):
    _write_ledger(isolated)
    catalog, intake, post_action = materials._load_materialintake()
    monkeypatch.setattr(intake, "scan_inbox", lambda mat_dir, ledger: [
        {"path": "00_待入库/x.epub", "filename": "x.epub", "sha256": "b" * 64,
         "suffix": ".epub", "unsupported": False, "exact_duplicate_matches": [], "possible_existing_candidates": []},
    ])
    result = materials.scan_material_inbox()
    assert result["inbox"] == "00_待入库"
    assert len(result["files"]) == 1


def test_apply_respects_transaction(isolated, monkeypatch):
    _write_ledger(isolated)
    catalog, intake, post_action = materials._load_materialintake()

    plan = {"items": [{"action": "REVIEW", "files": ["00_待入库/x.epub"], "reason": "待确认"}]}
    report = {"ok": True, "new_ids": [], "attached": [], "duplicates_removed": [],
              "reviews": ["00_待入库/x.epub"], "moves": [], "errors": [], "rolled_back": []}

    monkeypatch.setattr(intake, "apply_plan", lambda p, l, r: report)

    result = materials.apply_material_intake(plan)
    assert result["ok"] is True
    assert result["reviews"] == ["00_待入库/x.epub"]
    # §6：已移除死的 author-facing git_outcome/git_warning
    assert "git_outcome" not in result and "git_warning" not in result


def test_workbench_intake_does_not_call_git(isolated, monkeypatch):
    """§6/§15C：Workbench 入库不做 Git precheck/commit/push，不因 DIRTY_WORKTREE 失败。"""
    _write_ledger(isolated)
    catalog, intake, post_action = materials._load_materialintake()
    git_calls = []
    monkeypatch.setattr(post_action, "precheck",
                        lambda root: git_calls.append("precheck") or (False, "DIRTY_WORKTREE"))
    monkeypatch.setattr(post_action, "safe_commit_push",
                        lambda root, allowlist, msg: git_calls.append("push") or "OK")
    monkeypatch.setattr(intake, "apply_plan", lambda p, l, r: {
        "ok": True, "new_ids": [], "attached": [], "duplicates_removed": [],
        "reviews": [], "moves": [], "errors": [], "rolled_back": []})
    result = materials.apply_material_intake({"items": []})
    assert result["ok"] is True
    assert git_calls == [], "Workbench 入库绝不触发 Git precheck/commit/push"


def test_apply_surfaces_transaction_failure(isolated, monkeypatch):
    _write_ledger(isolated)
    catalog, intake, post_action = materials._load_materialintake()
    monkeypatch.setattr(intake, "apply_plan",
                        lambda p, l, r: {"ok": False, "errors": ["STOP_BEFORE_MOVE: MISSING_REGISTERED_FILE: x"]})
    with pytest.raises(materials.MaterialsError) as ei:
        materials.apply_material_intake({"items": []})
    # §12：作者可读，绝不泄露 STOP_BEFORE_MOVE / MISSING_REGISTERED_FILE 内部文本
    msg = str(ei.value)
    assert "刷新状态" in msg
    assert "STOP_BEFORE_MOVE" not in msg and "MISSING_REGISTERED_FILE" not in msg


def test_validate_intake_plan(isolated):
    assert materials.validate_intake_plan({"items": []}) == []
    assert materials.validate_intake_plan("not-a-plan") == ["入库计划格式错误。"]
    assert materials.validate_intake_plan({"items": [{"action": "BAD", "files": []}]}) != []
