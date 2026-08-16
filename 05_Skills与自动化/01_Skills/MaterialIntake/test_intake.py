# -*- coding: utf-8 -*-
"""MaterialIntake intake 测试（Phase 2B2，tmp_path，无真实数据依赖）。

覆盖：
  A. EMPTY_INBOX             无文件 → no-op
  B. EXACT_DUPLICATE         SHA 已存在 → 不建 asset / 不分 ID / 安全移除 inbox 副本
  C. NEW_SINGLE              单文件新素材 → 新 asset / next monotonic ID / 正确目录
  D. NEW_MULTI_FILE          EPUB+TXT 同一 plan group → 一个 asset / 一个 ID / 2 files
  E. ATTACH_EXISTING         同书新版本 → asset count 不增加 / file 增加 / ID 不变
  F. REVIEW                  文件留 inbox / ledger 不变
  G. NO_FUZZY_AUTO_MERGE     runtime 不因标题近似自动合并
  H. ID_NO_GAP_FILL          book_0001/0003/0141 → next book_0142，不生成 book_0002
  I. COLLISION_NO_OVERWRITE  同名不同 SHA → 不覆盖 / deterministic alternate filename
  J. MOVE_SHA_INTEGRITY      before SHA == after SHA
  K. ROLLBACK                中途失败 → 已移动文件回滚 / ledger 未写半份
  L. ROLE_ROUTING            三种正式 type → 三个正确目录
  M. ATTACH_MARKS_STALE      已有可用 asset 附新版本 → purification 需更新 / knowledge 仍可用
  N. LOOSE_MATERIAL_NA       新 LOOSE_MATERIAL → purification=不适用；再次 refresh 仍=不适用
"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog  # noqa: E402
import intake  # noqa: E402


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _write_ledger(root: Path, ledger: dict) -> None:
    mat = root / catalog.MATERIAL_DIR_NAME
    catalog.write_ledger(ledger, mat / catalog.LEDGER_FILENAME)


def _read_ledger(root: Path) -> dict:
    mat = root / catalog.MATERIAL_DIR_NAME
    return json.loads((mat / catalog.LEDGER_FILENAME).read_text(encoding="utf-8"))


def _ledger_bytes(root: Path) -> bytes:
    return (root / catalog.MATERIAL_DIR_NAME / catalog.LEDGER_FILENAME).read_bytes()


def _make_repo(tmp_path: Path) -> tuple[Path, str]:
    """最小仓库：Alpha（REFERENCE_WORK，可用 record + FINALIZED BKP）与 Beta（RESEARCH，未处理）。
    返回 (root, alpha_sha1)。"""
    root = tmp_path
    mat = root / catalog.MATERIAL_DIR_NAME
    (mat / intake.INBOX_DIR).mkdir(parents=True)
    (mat / "01_网络小说" / "Alpha").mkdir(parents=True)
    (mat / "05_现代专业资料").mkdir(parents=True)

    epub = mat / "01_网络小说" / "Alpha" / "Alpha.epub"
    epub.write_bytes(b"alpha v1 content")
    sha1 = _sha(b"alpha v1 content")
    pdf = mat / "05_现代专业资料" / "Beta.pdf"
    pdf.write_bytes(b"beta pdf content")
    sha2 = _sha(b"beta pdf content")

    fp1 = catalog.content_fingerprint([{"sha256": sha1, "path": "x"}])

    # FINALIZED BKP：book_0001 knowledge 可用 且 refresh 后稳定
    bkp_dir = root / catalog.DISTILL_DIR_NAME / "book_0001_Alpha" / "bkp"
    bkp_dir.mkdir(parents=True)
    (bkp_dir / "identity.json").write_text(json.dumps({
        "bkp_version": "0.2", "schema_status": "FINALIZED",
        "book": {"book_id": "book_0001", "title": "Alpha", "author": "作者A"},
        "source_snapshot": {"source_sha256": sha1},
    }, ensure_ascii=False), encoding="utf-8")

    assets = [
        {"id": "book_0001", "name": "Alpha", "type": "REFERENCE_WORK", "author": "作者A",
         "tags": [], "notes": "",
         "files": [{"path": "01_网络小说/Alpha/Alpha.epub", "sha256": sha1, "primary": True}],
         "purification": {"status": "可用", "evidence": "sourceprepare_record",
                          "source_sha256": sha1, "input_fingerprint": fp1},
         "knowledge": {"status": "可用", "path": "02_原著蒸馏/book_0001_Alpha",
                       "source_sha256": sha1}},
        {"id": "book_0003", "name": "Beta", "type": "RESEARCH", "author": "", "tags": [], "notes": "",
         "files": [{"path": "05_现代专业资料/Beta.pdf", "sha256": sha2, "primary": True}],
         "purification": {"status": "未处理", "evidence": None},
         "knowledge": {"status": "未开始"}},
    ]
    _write_ledger(root, {"schema_version": "1.0", "assets": assets, "containers": []})
    return root, sha1


def _put_inbox(root: Path, name: str, content: bytes) -> Path:
    p = root / catalog.MATERIAL_DIR_NAME / intake.INBOX_DIR / name
    p.write_bytes(content)
    return p


def _load_plan(root: Path, items: list[dict]) -> Path:
    plan = root / "intake_plan.json"
    plan.write_text(json.dumps({"items": items}, ensure_ascii=False), encoding="utf-8")
    return plan


# ---------- A. EMPTY_INBOX ----------

def test_empty_inbox(tmp_path):
    root, _ = _make_repo(tmp_path)
    facts = intake.scan_inbox(root / catalog.MATERIAL_DIR_NAME)
    assert facts == []
    before = _ledger_bytes(root)
    plan = _load_plan(root, [])
    report = intake.apply_plan({"items": []}, _read_ledger(root), root)
    assert report["ok"] is True
    assert report["moves"] == [] and report["new_ids"] == []
    assert _ledger_bytes(root) == before  # no-op：ledger byte-for-byte 不变


# ---------- B. EXACT_DUPLICATE ----------

def test_exact_duplicate(tmp_path):
    root, sha1 = _make_repo(tmp_path)
    dup = _put_inbox(root, "Alpha 副本.epub", b"alpha v1 content")  # 与 book_0001 相同内容
    plan = _load_plan(root, [{"action": "NEW_ASSET", "files": ["00_待入库/Alpha 副本.epub"],
                              "name": "Alpha 副本", "type": "REFERENCE_WORK"}])
    report = intake.apply_plan({"items": [{"action": "NEW_ASSET",
                                           "files": ["00_待入库/Alpha 副本.epub"],
                                           "name": "Alpha 副本", "type": "REFERENCE_WORK"}]},
                               _read_ledger(root), root)
    assert report["ok"] is True
    assert len(report["duplicates_removed"]) == 1
    assert report["duplicates_removed"][0]["sha"] == sha1
    assert not dup.exists()  # 三条件满足 → 安全移除 inbox 副本
    ledger = _read_ledger(root)
    assert len(ledger["assets"]) == 2  # 不建新 asset
    assert report["new_ids"] == []


# ---------- C. NEW_SINGLE ----------

def test_new_single(tmp_path):
    root, _ = _make_repo(tmp_path)
    _put_inbox(root, "新书.epub", b"brand new book")
    sha = _sha(b"brand new book")
    plan = _load_plan(root, [{"action": "NEW_ASSET", "files": ["00_待入库/新书.epub"],
                              "name": "新书", "type": "REFERENCE_WORK", "author": "作者B",
                              "tags": ["科幻"]}])
    report = intake.apply_plan({"items": [{"action": "NEW_ASSET", "files": ["00_待入库/新书.epub"],
                                           "name": "新书", "type": "REFERENCE_WORK",
                                           "author": "作者B", "tags": ["科幻"]}]},
                               _read_ledger(root), root)
    assert report["ok"] is True
    assert report["new_ids"] == ["book_0004"]  # 0001/0003 → next monotonic 0004（不补 0002 gap）
    ledger = _read_ledger(root)
    a = next(x for x in ledger["assets"] if x["id"] == "book_0004")
    assert a["name"] == "新书" and a["type"] == "REFERENCE_WORK"
    assert a["author"] == "作者B" and a["tags"] == ["科幻"]
    assert len(a["files"]) == 1
    f = a["files"][0]
    assert f["path"] == "01_参考作品/新书/新书.epub"  # 正确目录
    assert f["sha256"] == sha and f["primary"] is True
    assert a["purification"] == {"status": "未处理", "evidence": None}
    assert a["knowledge"] == {"status": "未开始"}
    assert (root / catalog.MATERIAL_DIR_NAME / "01_参考作品" / "新书" / "新书.epub").exists()
    assert not (root / catalog.MATERIAL_DIR_NAME / intake.INBOX_DIR / "新书.epub").exists()


# ---------- D. NEW_MULTI_FILE ----------

def test_new_multi_file(tmp_path):
    root, _ = _make_repo(tmp_path)
    _put_inbox(root, "多书.epub", b"multi epub")
    _put_inbox(root, "多书.txt", b"multi txt")
    plan = _load_plan(root, [{"action": "NEW_ASSET",
                              "files": ["00_待入库/多书.epub", "00_待入库/多书.txt"],
                              "name": "多书", "type": "REFERENCE_WORK"}])
    report = intake.apply_plan({"items": [{"action": "NEW_ASSET",
                                           "files": ["00_待入库/多书.epub", "00_待入库/多书.txt"],
                                           "name": "多书", "type": "REFERENCE_WORK"}]},
                               _read_ledger(root), root)
    assert report["ok"] is True
    assert report["new_ids"] == ["book_0004"]
    ledger = _read_ledger(root)
    a = next(x for x in ledger["assets"] if x["id"] == "book_0004")
    assert len(a["files"]) == 2
    assert {f["primary"] for f in a["files"]} == {True, False}  # 一个 asset、一个 ID、2 files
    assert {f["path"].split("/")[-1] for f in a["files"]} == {"多书.epub", "多书.txt"}


# ---------- E. ATTACH_EXISTING ----------

def test_attach_existing(tmp_path):
    root, _ = _make_repo(tmp_path)
    _put_inbox(root, "Alpha_v2.epub", b"alpha v2 content")
    plan = _load_plan(root, [{"action": "ATTACH_EXISTING", "files": ["00_待入库/Alpha_v2.epub"],
                              "asset_id": "book_0001"}])
    report = intake.apply_plan({"items": [{"action": "ATTACH_EXISTING",
                                           "files": ["00_待入库/Alpha_v2.epub"],
                                           "asset_id": "book_0001"}]},
                               _read_ledger(root), root)
    assert report["ok"] is True
    ledger = _read_ledger(root)
    assert len(ledger["assets"]) == 2  # asset count 不增加
    a = next(x for x in ledger["assets"] if x["id"] == "book_0001")
    assert len(a["files"]) == 2  # file 增加
    assert a["id"] == "book_0001"  # ID 不变
    nf = next(f for f in a["files"] if "Alpha_v2" in f["path"])
    assert nf["primary"] is False
    assert nf["path"] == "01_网络小说/Alpha/Alpha_v2.epub"  # 移到 primary source 所在目录


# ---------- F. REVIEW ----------

def test_review_keeps_inbox(tmp_path):
    root, _ = _make_repo(tmp_path)
    p = _put_inbox(root, "abc.pdf", b"ambiguous pdf")
    before = _ledger_bytes(root)
    plan = _load_plan(root, [{"action": "REVIEW", "files": ["00_待入库/abc.pdf"],
                              "reason": "无法确认类型"}])
    report = intake.apply_plan({"items": [{"action": "REVIEW", "files": ["00_待入库/abc.pdf"],
                                           "reason": "无法确认类型"}]},
                               _read_ledger(root), root)
    assert report["ok"] is True
    assert report["reviews"] == ["00_待入库/abc.pdf"]
    assert p.exists()  # 文件留 inbox
    assert _ledger_bytes(root) == before  # ledger 不变


# ---------- G. NO_FUZZY_AUTO_MERGE ----------

def test_no_fuzzy_auto_merge(tmp_path):
    root, _ = _make_repo(tmp_path)
    _put_inbox(root, "Alpha2.epub", b"alpha sequel content")
    plan = _load_plan(root, [{"action": "NEW_ASSET", "files": ["00_待入库/Alpha2.epub"],
                              "name": "Alpha2", "type": "REFERENCE_WORK"}])
    report = intake.apply_plan({"items": [{"action": "NEW_ASSET", "files": ["00_待入库/Alpha2.epub"],
                                           "name": "Alpha2", "type": "REFERENCE_WORK"}]},
                               _read_ledger(root), root)
    assert report["ok"] is True
    ledger = _read_ledger(root)
    assert len(ledger["assets"]) == 3  # 新 asset，不并入 Alpha
    alpha = next(x for x in ledger["assets"] if x["id"] == "book_0001")
    assert len(alpha["files"]) == 1  # Alpha 未变
    # scan 的 candidate hint 只是信息，不触发合并
    facts = intake.scan_inbox(root / catalog.MATERIAL_DIR_NAME, ledger)
    assert all(f["exact_duplicate_matches"] == [] for f in facts)


# ---------- H. ID_NO_GAP_FILL ----------

def test_id_no_gap_fill(tmp_path):
    _, _ = _make_repo(tmp_path)
    ledger = {"assets": [{"id": "book_0001"}, {"id": "book_0003"}, {"id": "book_0141"}]}
    assert intake.allocate_next_id(ledger) == "book_0142"  # 不生成 book_0002 / 不补 gap


# ---------- I. COLLISION_NO_OVERWRITE ----------

def test_collision_no_overwrite(tmp_path):
    root, _ = _make_repo(tmp_path)
    orig = root / catalog.MATERIAL_DIR_NAME / "01_网络小说" / "Alpha" / "Alpha.epub"
    orig_bytes = orig.read_bytes()
    _put_inbox(root, "Alpha.epub", b"alpha v3 different content")  # 同名不同 SHA
    sha3 = _sha(b"alpha v3 different content")
    plan = _load_plan(root, [{"action": "ATTACH_EXISTING", "files": ["00_待入库/Alpha.epub"],
                              "asset_id": "book_0001"}])
    report = intake.apply_plan({"items": [{"action": "ATTACH_EXISTING",
                                           "files": ["00_待入库/Alpha.epub"],
                                           "asset_id": "book_0001"}]},
                               _read_ledger(root), root)
    assert report["ok"] is True
    assert orig.read_bytes() == orig_bytes  # 原文件未被覆盖
    target = root / catalog.MATERIAL_DIR_NAME / "01_网络小说" / "Alpha" / f"Alpha__{sha3[:8]}.epub"
    assert target.exists()  # deterministic collision filename


# ---------- J. MOVE_SHA_INTEGRITY ----------

def test_move_sha_integrity(tmp_path):
    root, _ = _make_repo(tmp_path)
    _put_inbox(root, "书.epub", b"integrity book")
    sha = _sha(b"integrity book")
    report = intake.apply_plan({"items": [{"action": "NEW_ASSET", "files": ["00_待入库/书.epub"],
                                           "name": "书", "type": "REFERENCE_WORK"}]},
                               _read_ledger(root), root)
    assert report["ok"] is True
    m = report["moves"][0]
    assert m["before"] == m["after"] == sha  # before SHA == after SHA
    moved = root / catalog.MATERIAL_DIR_NAME / "01_参考作品" / "书" / "书.epub"
    assert catalog.sha256_file(moved) == sha


# ---------- K. ROLLBACK ----------

def test_rollback_on_failure(tmp_path, monkeypatch):
    root, _ = _make_repo(tmp_path)
    _put_inbox(root, "a.epub", b"rollback a")
    _put_inbox(root, "b.epub", b"rollback b")
    before = _ledger_bytes(root)
    real = catalog.sha256_file
    calls = {"n": 0}

    def fake(p):
        calls["n"] += 1
        # planned: a#1, b#2；after 校验: a#3, b#4 → 第 4 次调用（b 的 after）返回错误 SHA
        if calls["n"] == 4:
            return "0" * 64
        return real(p)

    monkeypatch.setattr(catalog, "sha256_file", fake)
    items = [{"action": "NEW_ASSET", "files": [f"00_待入库/{n}.epub"], "name": n,
              "type": "REFERENCE_WORK"} for n in ("a", "b")]
    report = intake.apply_plan({"items": items}, _read_ledger(root), root)
    assert report["ok"] is False
    assert any("SHA 不匹配" in e for e in report["errors"])
    assert sorted(report["rolled_back"]) == ["00_待入库/a.epub", "00_待入库/b.epub"]
    # 已移动文件全部回滚到 inbox；目标目录无残留
    inbox = root / catalog.MATERIAL_DIR_NAME / intake.INBOX_DIR
    assert (inbox / "a.epub").exists() and (inbox / "b.epub").exists()
    assert not (root / catalog.MATERIAL_DIR_NAME / "01_参考作品" / "a").exists()
    assert not (root / catalog.MATERIAL_DIR_NAME / "01_参考作品" / "b").exists()
    assert _ledger_bytes(root) == before  # ledger 未写半份


# ---------- L. ROLE_ROUTING ----------

def test_role_routing(tmp_path):
    root, _ = _make_repo(tmp_path)
    _put_inbox(root, "c.pdf", b"research doc")
    _put_inbox(root, "a.epub", b"reference work")
    _put_inbox(root, "b.txt", b"loose note")
    items = [
        {"action": "NEW_ASSET", "files": ["00_待入库/a.epub"], "name": "参考甲",
         "type": "REFERENCE_WORK"},
        {"action": "NEW_ASSET", "files": ["00_待入库/b.txt"], "name": "零散乙",
         "type": "LOOSE_MATERIAL"},
        {"action": "NEW_ASSET", "files": ["00_待入库/c.pdf"], "name": "研究丙",
         "type": "RESEARCH"},
    ]
    report = intake.apply_plan({"items": items}, _read_ledger(root), root)
    assert report["ok"] is True
    ledger = _read_ledger(root)
    ids = {a["name"]: a for a in ledger["assets"] if a["id"].startswith("book_000")}
    ref = next(a for a in ledger["assets"] if a["name"] == "参考甲")
    res = next(a for a in ledger["assets"] if a["name"] == "研究丙")
    loose = next(a for a in ledger["assets"] if a["name"] == "零散乙")
    assert ref["files"][0]["path"].startswith("01_参考作品/")
    assert res["files"][0]["path"].startswith("02_研究资料/")
    assert loose["files"][0]["path"].startswith("03_零散素材/")
    # 批量 NEW_ASSET 按 deterministic inbox path 排序分配 ID：a.epub < b.txt < c.pdf
    assert sorted(report["new_ids"]) == ["book_0004", "book_0005", "book_0006"]
    assert [a["id"] for a in (ref, loose, res)] == ["book_0004", "book_0005", "book_0006"]


# ---------- M. ATTACH_MARKS_STALE（第 47 节） ----------

def test_attach_existing_marks_stale(tmp_path):
    root, _ = _make_repo(tmp_path)
    _put_inbox(root, "Alpha_v2.epub", b"alpha v2 content")
    report = intake.apply_plan({"items": [{"action": "ATTACH_EXISTING",
                                           "files": ["00_待入库/Alpha_v2.epub"],
                                           "asset_id": "book_0001"}]},
                               _read_ledger(root), root)
    assert report["ok"] is True
    ledger = _read_ledger(root)
    a = next(x for x in ledger["assets"] if x["id"] == "book_0001")
    # source set fingerprint 改变 → purification 需更新（旧可用不覆盖已变化素材）
    assert a["purification"]["status"] == "需更新"
    assert a["purification"]["evidence"] == "sourceprepare_record_input_changed"
    # knowledge：原 BKP 使用的旧 source 仍存在 → 可以继续可用（两状态 authority 不同）
    assert a["knowledge"]["status"] == "可用"


# ---------- N. LOOSE_MATERIAL_NA（第 48 节） ----------

def test_loose_material_purification_not_applicable(tmp_path):
    root, _ = _make_repo(tmp_path)
    _put_inbox(root, "note.txt", b"a loose note")
    report = intake.apply_plan({"items": [{"action": "NEW_ASSET", "files": ["00_待入库/note.txt"],
                                           "name": "便签", "type": "LOOSE_MATERIAL"}]},
                               _read_ledger(root), root)
    assert report["ok"] is True
    ledger = _read_ledger(root)
    a = next(x for x in ledger["assets"] if x["name"] == "便签")
    assert a["purification"] == {"status": "不适用", "evidence": None}
    # 再次 catalog refresh：仍=不适用，不能变回未处理
    assert catalog.refresh_and_render(root) == 0
    ledger2 = _read_ledger(root)
    a2 = next(x for x in ledger2["assets"] if x["name"] == "便签")
    assert a2["purification"]["status"] == "不适用"
    assert a2["knowledge"]["status"] == "未开始"
