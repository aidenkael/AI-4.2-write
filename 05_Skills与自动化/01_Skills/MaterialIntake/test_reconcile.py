# -*- coding: utf-8 -*-
"""§5 manual Explorer reconcile focused tests（temp root；无真实数据 / 无模型 / 无 Git）。

覆盖 §15B：
  - 新手动素材文件夹确定性注册为新 asset；
  - 既有文件夹跨角色目录移动 → 内容身份保留 asset id + 更新 canonical type/path；
  - 文件夹改名（唯一）→ 更新作者面 name；
  - 重复/歧义身份 → fail closed，原子不写盘；
  - 缺失登记来源 → 安全 attention，绝不静默删除登记。
"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog  # noqa: E402
import intake  # noqa: E402

ROLE_DIRS = ("01_原著", "02_技巧类", "03_其他")


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _make_repo(tmp_path: Path, assets=None) -> Path:
    root = tmp_path
    mat = root / catalog.MATERIAL_DIR_NAME
    (mat / intake.INBOX_DIR).mkdir(parents=True)
    for d in ROLE_DIRS:
        (mat / d).mkdir(parents=True)
    catalog.write_ledger({"schema_version": "1.0", "assets": assets or [], "containers": []},
                         mat / catalog.LEDGER_FILENAME)
    return root


def _put_source(root: Path, rel: str, content: bytes) -> Path:
    p = root / catalog.MATERIAL_DIR_NAME / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return p


def _rm(root: Path, rel: str) -> None:
    p = root / catalog.MATERIAL_DIR_NAME / rel
    p.unlink()
    try:
        p.parent.rmdir()
    except OSError:
        pass


def _asset(asset_id, name, mtype, rel, content):
    return {"id": asset_id, "name": name, "type": mtype, "author": "", "tags": [], "notes": "",
            "files": [{"path": rel, "sha256": _sha(content), "primary": True}],
            "purification": {"status": "未处理", "evidence": None},
            "knowledge": {"status": "未开始"}}


def _read(root: Path) -> dict:
    return json.loads((root / catalog.MATERIAL_DIR_NAME / catalog.LEDGER_FILENAME).read_text(encoding="utf-8"))


def test_new_manual_folder_registers(tmp_path):
    """在角色目录下手动新建含 EPUB 的素材文件夹 → 刷新确定性注册为新 asset。"""
    root = _make_repo(tmp_path)
    _put_source(root, "01_原著/新书/new.epub", b"new-book-bytes")
    rep = intake.reconcile_manual_edits(root)
    assert rep["ok"] is True and rep["changed"] is True
    assert len(rep["registered"]) == 1
    led = _read(root)
    assert len(led["assets"]) == 1
    a = led["assets"][0]
    assert a["type"] == "REFERENCE_WORK"
    assert a["name"] == "新书"
    assert a["files"][0]["path"] == "01_原著/新书/new.epub"


def test_new_folder_type_follows_role_dir(tmp_path):
    """在 02_技巧类 / 03_其他 下新建文件夹 → 类型按角色目录。"""
    root = _make_repo(tmp_path)
    _put_source(root, "02_技巧类/方法书/m.txt", b"method-bytes")
    _put_source(root, "03_其他/杂项/o.txt", b"loose-bytes")
    rep = intake.reconcile_manual_edits(root)
    assert rep["ok"] is True
    by_name = {a["name"]: a for a in _read(root)["assets"]}
    assert by_name["方法书"]["type"] == "METHOD_SOURCE"
    assert by_name["杂项"]["type"] == "LOOSE_MATERIAL"


def test_move_folder_preserves_id_and_updates_type_path(tmp_path):
    """跨角色目录移动素材文件夹 → 内容身份保留 asset id + 更新 canonical type/path。"""
    content = b"the-book-bytes"
    root = _make_repo(tmp_path, [_asset("book_0001", "书", "REFERENCE_WORK", "01_原著/书/book.epub", content)])
    _put_source(root, "01_原著/书/book.epub", content)
    # 作者手动把整个文件夹从 01_原著 移到 02_技巧类（同内容）
    _put_source(root, "02_技巧类/书/book.epub", content)
    _rm(root, "01_原著/书/book.epub")

    rep = intake.reconcile_manual_edits(root)
    assert rep["ok"] is True and rep["changed"] is True
    a = _read(root)["assets"][0]
    assert a["id"] == "book_0001", "精确内容身份保留同一 asset id"
    assert a["type"] == "METHOD_SOURCE", "跨角色目录移动更新 canonical type"
    assert a["files"][0]["path"] == "02_技巧类/书/book.epub"
    assert any(t["id"] == "book_0001" and t["to"] == "METHOD_SOURCE" for t in rep["type_changed"])


def test_rename_folder_updates_name(tmp_path):
    """文件夹改名（身份唯一）→ 更新作者面 name，保留 id。"""
    content = b"renamed-book"
    root = _make_repo(tmp_path, [_asset("book_0001", "旧名", "REFERENCE_WORK", "01_原著/旧名/b.epub", content)])
    _put_source(root, "01_原著/旧名/b.epub", content)
    _put_source(root, "01_原著/新名/b.epub", content)
    _rm(root, "01_原著/旧名/b.epub")

    rep = intake.reconcile_manual_edits(root)
    assert rep["ok"] is True
    a = _read(root)["assets"][0]
    assert a["id"] == "book_0001" and a["name"] == "新名"
    assert a["files"][0]["path"] == "01_原著/新名/b.epub"
    assert any(r["id"] == "book_0001" for r in rep["renamed"])


def test_duplicate_identity_fails_closed_atomically(tmp_path):
    """同一内容出现在多个角色位置 → 歧义 fail closed，绝不写盘（原子）。"""
    content = b"same-bytes"
    root = _make_repo(tmp_path)
    _put_source(root, "01_原著/甲/x.epub", content)
    _put_source(root, "02_技巧类/乙/x.epub", content)
    before = (root / catalog.MATERIAL_DIR_NAME / catalog.LEDGER_FILENAME).read_bytes()

    rep = intake.reconcile_manual_edits(root)
    assert rep["ok"] is False
    assert rep["errors"]
    # 原子：ledger 完全未被写
    assert (root / catalog.MATERIAL_DIR_NAME / catalog.LEDGER_FILENAME).read_bytes() == before


def test_missing_source_is_safe_attention_not_deleted(tmp_path):
    """删除已登记素材文件夹 → 保留登记（绝不静默删除），记入 missing_sources 供可读 attention。"""
    content = b"existing-book"
    root = _make_repo(tmp_path, [_asset("book_0001", "书", "REFERENCE_WORK", "01_原著/书/b.epub", content)])
    _put_source(root, "01_原著/书/b.epub", content)
    _rm(root, "01_原著/书/b.epub")

    rep = intake.reconcile_manual_edits(root)
    assert rep["ok"] is True
    assert "book_0001" in rep["missing_sources"]
    led = _read(root)
    assert len(led["assets"]) == 1, "缺失来源绝不静默删除登记"
    assert led["assets"][0]["id"] == "book_0001"
    assert led["assets"][0]["files"][0]["path"] == "01_原著/书/b.epub"


def test_no_manual_edit_is_noop(tmp_path):
    """无结构变化 → reconcile 不写盘（changed=False），交给常规刷新。"""
    content = b"stable-book"
    root = _make_repo(tmp_path, [_asset("book_0001", "书", "REFERENCE_WORK", "01_原著/书/b.epub", content)])
    _put_source(root, "01_原著/书/b.epub", content)
    before = (root / catalog.MATERIAL_DIR_NAME / catalog.LEDGER_FILENAME).read_bytes()
    rep = intake.reconcile_manual_edits(root)
    assert rep["ok"] is True and rep["changed"] is False
    assert (root / catalog.MATERIAL_DIR_NAME / catalog.LEDGER_FILENAME).read_bytes() == before


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
