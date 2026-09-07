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


def _make_repo(tmp_path: Path, assets=None, containers=None) -> Path:
    root = tmp_path
    mat = root / catalog.MATERIAL_DIR_NAME
    (mat / intake.INBOX_DIR).mkdir(parents=True)
    for d in ROLE_DIRS:
        (mat / d).mkdir(parents=True)
    catalog.write_ledger({"schema_version": "1.0", "assets": assets or [],
                          "containers": containers or []},
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


def _csv_rows(root: Path) -> list:
    import csv as _csv
    p = root / catalog.MATERIAL_DIR_NAME / catalog.LEGACY_CSV_FILENAME
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(_csv.reader(f))


def _index_md(root: Path) -> str:
    return (root / catalog.MATERIAL_DIR_NAME / catalog.INDEX_FILENAME).read_text(encoding="utf-8")


def _multi_asset(asset_id, name, mtype, files):
    """files = [(rel, content, primary)] → 多来源资产 fixture。"""
    recs = [{"path": rel, "sha256": _sha(content), "primary": prim} for rel, content, prim in files]
    return {"id": asset_id, "name": name, "type": mtype, "author": "", "tags": [], "notes": "",
            "files": recs, "purification": {"status": "未处理", "evidence": None},
            "knowledge": {"status": "未开始"}}


def test_all_source_deletion_removes_asset(tmp_path):
    """§5.2：删除一个资产的全部来源 → refresh 后该 asset 从 ledger 移除（取代旧的永久保留）。"""
    content = b"existing-book"
    root = _make_repo(tmp_path, [_asset("book_0001", "书", "REFERENCE_WORK", "01_原著/书/b.epub", content)])
    _put_source(root, "01_原著/书/b.epub", content)
    _rm(root, "01_原著/书/b.epub")

    rep = intake.reconcile_manual_edits(root)
    assert rep["ok"] is True and rep["changed"] is True
    assert "book_0001" in rep["removed_assets"]
    led = _read(root)
    assert led["assets"] == [], "全部来源删除 → 移除 canonical asset，不留 source-less 卡片"
    # §6：CSV/index 从结算后 ledger 派生（不再含被删资产）
    rows = _csv_rows(root)
    assert all(r[0] != "book_0001" for r in rows[1:])
    assert "book_0001" not in _index_md(root)


def test_partial_source_deletion_preserves_id(tmp_path):
    """§5.1/§5.3：多来源资产删其中一个（子集 SHA）→ 保留同一 id，不新建重复 asset。"""
    a_bytes, b_bytes = b"src-a", b"src-b"
    asset = _multi_asset("book_0001", "书", "REFERENCE_WORK", [
        ("01_原著/书/a.epub", a_bytes, True),
        ("01_原著/书/b.epub", b_bytes, False)])
    root = _make_repo(tmp_path, [asset])
    _put_source(root, "01_原著/书/a.epub", a_bytes)
    _put_source(root, "01_原著/书/b.epub", b_bytes)
    _rm(root, "01_原著/书/a.epub")

    rep = intake.reconcile_manual_edits(root)
    assert rep["ok"] is True and rep["changed"] is True
    led = _read(root)
    assert len(led["assets"]) == 1, "子集 SHA 绝不新建重复 asset"
    a = led["assets"][0]
    assert a["id"] == "book_0001"
    assert [f["path"] for f in a["files"]] == ["01_原著/书/b.epub"]
    assert rep["registered"] == []


def test_primary_deletion_reselects_remaining_primary(tmp_path):
    """§5.1：删除当前 primary 来源 → 确定性选首个剩余 canonical 文件为 primary。"""
    a_bytes, b_bytes = b"primary-src", b"second-src"
    asset = _multi_asset("book_0001", "书", "REFERENCE_WORK", [
        ("01_原著/书/a.epub", a_bytes, True),
        ("01_原著/书/b.epub", b_bytes, False)])
    root = _make_repo(tmp_path, [asset])
    _put_source(root, "01_原著/书/a.epub", a_bytes)
    _put_source(root, "01_原著/书/b.epub", b_bytes)
    _rm(root, "01_原著/书/a.epub")

    rep = intake.reconcile_manual_edits(root)
    assert rep["ok"] is True
    a = _read(root)["assets"][0]
    assert len(a["files"]) == 1 and a["files"][0]["primary"] is True


def test_partial_deletion_keeps_unsupported_survivor(tmp_path):
    """§5.4 围城形态：EPUB(primary) 删除 + 不支持的 .mobi 幸存 → 保留 id、.mobi 升为 primary。"""
    epub_bytes, mobi_bytes = b"weicheng-epub", b"weicheng-mobi"
    asset = _multi_asset("book_0072", "围城", "REFERENCE_WORK", [
        ("01_原著/围城/w.epub", epub_bytes, True),
        ("01_原著/围城/w.mobi", mobi_bytes, False)])
    root = _make_repo(tmp_path, [asset])
    _put_source(root, "01_原著/围城/w.epub", epub_bytes)
    _put_source(root, "01_原著/围城/w.mobi", mobi_bytes)
    _rm(root, "01_原著/围城/w.epub")  # 只删 EPUB，.mobi 保留

    rep = intake.reconcile_manual_edits(root)
    assert rep["ok"] is True
    led = _read(root)
    assert len(led["assets"]) == 1 and led["assets"][0]["id"] == "book_0072"
    files = led["assets"][0]["files"]
    assert [f["path"] for f in files] == ["01_原著/围城/w.mobi"]
    assert files[0]["primary"] is True, ".mobi 幸存 → 重选为 primary"
    # 结算后账本不再指向已删来源
    assert all("w.epub" not in f["path"] for f in files)


def test_all_source_deletion_relocates_finalized_02_package(tmp_path):
    """§5.2：全来源删除 → 已定稿正式 02 包移出可发现 02（不永久删除）。"""
    content = b"distilled-book"
    root = _make_repo(tmp_path, [_asset("book_0001", "书", "REFERENCE_WORK", "01_原著/书/b.epub", content)])
    _put_source(root, "01_原著/书/b.epub", content)
    package = _finalized_bkp(root)
    _rm(root, "01_原著/书/b.epub")

    rep = intake.reconcile_manual_edits(root)
    assert rep["ok"] is True
    assert "book_0001" in rep["removed_assets"]
    assert not package.exists(), "正式 02 包已移出可发现 02"
    recovery = root / "06_工作区" / "BookDistill" / "_source_deleted_recovery" / package.name
    assert (recovery / "old.marker").is_file(), "02 包保留在 06 recovery，未永久删除"


def test_multi_asset_overlap_fails_closed(tmp_path):
    """§5.3：一个文件夹内容同时与多个已登记 asset 重叠 → fail closed，不写盘。"""
    x_bytes, y_bytes = b"content-x", b"content-y"
    root = _make_repo(tmp_path, [
        _asset("book_0001", "甲", "REFERENCE_WORK", "01_原著/甲/x.epub", x_bytes),
        _asset("book_0002", "乙", "REFERENCE_WORK", "01_原著/乙/y.epub", y_bytes)])
    _put_source(root, "01_原著/甲/x.epub", x_bytes)
    _put_source(root, "01_原著/乙/y.epub", y_bytes)
    # 把两个来源合并进同一文件夹（同时重叠 book_0001 与 book_0002）
    _put_source(root, "01_原著/合并/x.epub", x_bytes)
    _put_source(root, "01_原著/合并/y.epub", y_bytes)
    _rm(root, "01_原著/甲/x.epub")
    _rm(root, "01_原著/乙/y.epub")
    before = (root / catalog.MATERIAL_DIR_NAME / catalog.LEDGER_FILENAME).read_bytes()

    rep = intake.reconcile_manual_edits(root)
    assert rep["ok"] is False and rep["errors"]
    assert (root / catalog.MATERIAL_DIR_NAME / catalog.LEDGER_FILENAME).read_bytes() == before


def test_no_manual_edit_is_noop(tmp_path):
    """无结构变化 → reconcile 不写盘（changed=False），交给常规刷新。"""
    content = b"stable-book"
    root = _make_repo(tmp_path, [_asset("book_0001", "书", "REFERENCE_WORK", "01_原著/书/b.epub", content)])
    _put_source(root, "01_原著/书/b.epub", content)
    before = (root / catalog.MATERIAL_DIR_NAME / catalog.LEDGER_FILENAME).read_bytes()
    rep = intake.reconcile_manual_edits(root)
    assert rep["ok"] is True and rep["changed"] is False
    assert (root / catalog.MATERIAL_DIR_NAME / catalog.LEDGER_FILENAME).read_bytes() == before


def _finalized_bkp(root: Path, asset_id="book_0001", name="书") -> Path:
    package = root / catalog.DISTILL_DIR_NAME / f"{asset_id}_{name}"
    (package / "bkp").mkdir(parents=True)
    (package / "bkp" / "identity.json").write_text("{}\n", encoding="utf-8")
    (package / "old.marker").write_text("old\n", encoding="utf-8")
    return package


def test_type_change_package_and_metadata_rollback_together(tmp_path, monkeypatch):
    """A. catalog settlement 失败 → metadata bytes + 不兼容 02 包一起恢复。"""
    content = b"transaction-book"
    root = _make_repo(tmp_path, [_asset(
        "book_0001", "书", "REFERENCE_WORK", "01_原著/书/book.epub", content)])
    _put_source(root, "01_原著/书/book.epub", content)
    _put_source(root, "02_技巧类/书/book.epub", content)
    _rm(root, "01_原著/书/book.epub")
    package = _finalized_bkp(root)
    mat = root / catalog.MATERIAL_DIR_NAME
    (mat / catalog.LEGACY_CSV_FILENAME).write_bytes(b"csv-before\n")
    (mat / catalog.INDEX_FILENAME).write_bytes(b"md-before\n")
    before = {name: (mat / name).read_bytes() for name in (
        catalog.LEDGER_FILENAME, catalog.LEGACY_CSV_FILENAME, catalog.INDEX_FILENAME)}
    monkeypatch.setattr(catalog, "refresh_and_render",
                        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("forced")))

    rep = intake.reconcile_manual_edits(root)

    assert rep["ok"] is False
    assert package.is_dir() and (package / "old.marker").is_file()
    assert not (root / "06_工作区" / "BookDistill" / "_incompatible_recovery" / package.name).exists()
    assert {name: (mat / name).read_bytes() for name in before} == before


def test_successful_type_change_relocates_incompatible_package(tmp_path):
    """B. 全部结算成功后，不兼容包在 06 recovery，ledger 提交新类型。"""
    content = b"successful-type-change"
    root = _make_repo(tmp_path, [_asset(
        "book_0001", "书", "REFERENCE_WORK", "01_原著/书/book.epub", content)])
    _put_source(root, "01_原著/书/book.epub", content)
    _put_source(root, "02_技巧类/书/book.epub", content)
    _rm(root, "01_原著/书/book.epub")
    package = _finalized_bkp(root)

    rep = intake.reconcile_manual_edits(root)

    recovery = root / "06_工作区" / "BookDistill" / "_incompatible_recovery" / package.name
    assert rep["ok"] is True and rep["changed"] is True
    assert not package.exists() and (recovery / "old.marker").is_file()
    assert _read(root)["assets"][0]["type"] == "METHOD_SOURCE"


def test_container_backed_folder_move_updates_all_paths_preserving_identity(tmp_path):
    """C. 精确 SHA 可证的容器文件夹改名，asset/container 路径同一事务更新。"""
    source = b"split-book"
    original = b"original-container"
    container_sha = _sha(original)
    asset = _asset("book_0001", "旧名", "REFERENCE_WORK", "01_原著/旧名/book.epub", source)
    asset["files"][0]["source_container"] = "container-1"
    container = {
        "id": "container-1", "category": "01_原著", "container_dir": "01_原著/旧名",
        "manifest_path": "01_原著/旧名/collection_manifest.json",
        "original": {"filename": "original.epub", "path": "01_原著/旧名/original.epub",
                     "sha256": container_sha},
        "source_format": "epub", "split_book_ids": ["book_0001"], "split_count": 1,
    }
    root = _make_repo(tmp_path, [asset], [container])
    old = root / catalog.MATERIAL_DIR_NAME / "01_原著" / "旧名"
    old.mkdir(parents=True)
    (old / "book.epub").write_bytes(source)
    (old / "original.epub").write_bytes(original)
    (old / "collection_manifest.json").write_text("{}\n", encoding="utf-8")
    new = old.with_name("新名")
    old.rename(new)

    rep = intake.reconcile_manual_edits(root)

    assert rep["ok"] is True and rep["container_paths_updated"] == [
        {"id": "container-1", "from": "01_原著/旧名", "to": "01_原著/新名"}]
    ledger = _read(root)
    assert ledger["assets"][0]["files"][0]["path"] == "01_原著/新名/book.epub"
    updated = ledger["containers"][0]
    assert updated["container_dir"] == "01_原著/新名"
    assert updated["manifest_path"] == "01_原著/新名/collection_manifest.json"
    assert updated["original"]["path"] == "01_原著/新名/original.epub"
    assert updated["id"] == "container-1" and updated["original"]["sha256"] == container_sha


def test_ambiguous_container_mapping_fails_closed(tmp_path):
    """D. 容器原始 SHA 在多个新位置出现 → fail closed，不写 metadata/不移 package。"""
    original = b"same-container"
    container = {
        "id": "container-1", "category": "01_原著", "container_dir": "01_原著/旧名",
        "manifest_path": "01_原著/旧名/collection_manifest.json",
        "original": {"filename": "original.epub", "path": "01_原著/旧名/original.epub",
                     "sha256": _sha(original)},
        "source_format": "epub", "split_book_ids": [], "split_count": 0,
    }
    root = _make_repo(tmp_path, containers=[container])
    _put_source(root, "01_原著/新名/original.epub", original)
    _put_source(root, "02_技巧类/另一份/original.epub", original)
    ledger_path = root / catalog.MATERIAL_DIR_NAME / catalog.LEDGER_FILENAME
    before = ledger_path.read_bytes()

    rep = intake.reconcile_manual_edits(root)

    assert rep["ok"] is False and rep["errors"]
    assert ledger_path.read_bytes() == before


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
