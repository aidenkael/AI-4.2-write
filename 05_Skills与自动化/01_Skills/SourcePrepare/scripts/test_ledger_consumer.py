# -*- coding: utf-8 -*-
"""
test_ledger_consumer.py — SourcePrepare ledger consumer 最小验证（tmp fixture，不碰真实数据）。

覆盖 Phase 2B1 第 29 节 9 项：
  1. book_id → 找到正确 asset
  2. 单来源 candidate
  3. 双来源 candidate
  4. source_container provenance
  5. REFERENCE_WORK 可处理
  6. NEEDS_REVIEW 拒绝自动处理
  7. RESEARCH 当前不进入参考作品处理链（保守：转换结果强制 REVIEW）
  8. LOOSE_MATERIAL 不适用
  9. 不依赖目录名称语义（random_old_folder/Alpha/ 只要 ledger 注册即可识别）

运行：
  python -m pytest test_ledger_consumer.py -v
"""
import hashlib
import json
from pathlib import Path

import pytest

import source_prepare as sp


def _write_file(root: Path, rel: str, content: bytes = b"x") -> str:
    p = root / "01_原始素材" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


@pytest.fixture()
def fixture(tmp_path):
    """ledger 驱动测试树：5 种 type × 3 类来源布局。"""
    root = tmp_path
    sha_a = _write_file(root, "random_old_folder/Alpha/Alpha.epub", b"alpha epub")
    sha_t = _write_file(root, "01_网络小说/长安十二时辰/长安十二时辰.txt", b"cz txt")
    sha_e = _write_file(root, "02_中文文学/马伯庸作品合集/长安十二时辰.epub", b"cz epub")
    sha_m = _write_file(root, "02_中文文学/明朝那些事儿.epub", b"mz epub")
    sha_r = _write_file(root, "05_现代专业资料/研究报告.pdf", b"research pdf")
    sha_z = _write_file(root, "06_其他参考资料/杂项.zip", b"loose zip")

    assets = [
        # 单来源 REFERENCE_WORK，目录名任意（random_old_folder/）
        {"id": "book_0001", "name": "Alpha", "type": "REFERENCE_WORK",
         "author": "作者A", "tags": [], "notes": "",
         "files": [{"path": "random_old_folder/Alpha/Alpha.epub", "sha256": sha_a,
                    "primary": True, "source_container": ""}],
         "purification": {"status": "未处理", "evidence": None},
         "knowledge": {"status": "未开始"}},
        # 双来源 REFERENCE_WORK：独立 txt + 合集 epub（provenance）
        {"id": "book_0035", "name": "长安十二时辰", "type": "REFERENCE_WORK",
         "author": "马伯庸", "tags": [], "notes": "",
         "files": [
             {"path": "01_网络小说/长安十二时辰/长安十二时辰.txt", "sha256": sha_t,
              "primary": False, "source_container": ""},
             {"path": "02_中文文学/马伯庸作品合集/长安十二时辰.epub", "sha256": sha_e,
              "primary": True, "source_container": "马伯庸作品合集"},
         ],
         "purification": {"status": "未处理", "evidence": None},
         "knowledge": {"status": "未开始"}},
        {"id": "book_0080", "name": "明朝那些事儿", "type": "NEEDS_REVIEW",
         "author": "", "tags": [], "notes": "",
         "files": [{"path": "02_中文文学/明朝那些事儿.epub", "sha256": sha_m,
                    "primary": True, "source_container": ""}],
         "purification": {"status": "未处理", "evidence": None},
         "knowledge": {"status": "未开始"}},
        {"id": "book_0057", "name": "研究报告", "type": "RESEARCH",
         "author": "", "tags": [], "notes": "",
         "files": [{"path": "05_现代专业资料/研究报告.pdf", "sha256": sha_r,
                    "primary": True, "source_container": ""}],
         "purification": {"status": "未处理", "evidence": None},
         "knowledge": {"status": "未开始"}},
        {"id": "book_0500", "name": "杂项素材", "type": "LOOSE_MATERIAL",
         "author": "", "tags": [], "notes": "",
         "files": [{"path": "06_其他参考资料/杂项.zip", "sha256": sha_z,
                    "primary": True, "source_container": ""}],
         "purification": {"status": "未处理", "evidence": None},
         "knowledge": {"status": "未开始"}},
    ]
    containers = [{
        "id": "马伯庸作品合集", "container_dir": "02_中文文学/马伯庸作品合集",
        "category": "02_中文文学", "source_format": "epub",
        "manifest_path": "02_中文文学/马伯庸作品合集/collection_manifest.json",
        "original": {"path": "", "filename": "", "sha256": ""},
        "split_count": 1, "split_book_ids": ["book_0035"],
    }]
    ledger = {"schema_version": "1.0", "assets": assets, "containers": containers}
    mat = root / "01_原始素材"
    mat.mkdir(parents=True, exist_ok=True)
    (mat / "素材资产.json").write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    return root, ledger


def _group(fixture, bid: str) -> dict:
    root, ledger = fixture
    groups = sp.group_candidates(sp.collect_candidates(ledger, root))
    return next(x for x in groups if x["book_id"] == bid)


# ---------- 1. book_id → 正确 asset ----------

def test_book_id_finds_asset(fixture):
    root, ledger = fixture
    cands = sp.collect_candidates(ledger, root)
    by_id = {c.book_id: c for c in cands}
    assert by_id["book_0001"].work_name == "Alpha"
    assert by_id["book_0001"].path.name == "Alpha.epub"
    assert by_id["book_0001"].asset_type == "REFERENCE_WORK"
    assert by_id["book_0035"].work_name == "长安十二时辰"
    assert by_id["book_0080"].asset_type == "NEEDS_REVIEW"


# ---------- 2. 单来源 candidate ----------

def test_single_source_candidate(fixture):
    g = _group(fixture, "book_0001")
    assert len(g["files"]) == 1
    assert g["containers"] == {""}
    assert g["files"][0].name == "Alpha.epub"


# ---------- 3. 双来源 candidate ----------

def test_multi_source_candidate(fixture):
    g = _group(fixture, "book_0035")
    assert len(g["files"]) == 2
    assert {f.suffix for f in g["files"]} == {".txt", ".epub"}


# ---------- 4. source_container provenance ----------

def test_source_container_provenance(fixture):
    root, ledger = fixture
    cands = sp.collect_candidates(ledger, root)
    c35 = [c for c in cands if c.book_id == "book_0035"]
    assert sorted(c.source_container for c in c35) == ["", "马伯庸作品合集"]
    assert sum(1 for c in c35 if c.primary) == 1  # primary 唯一（合集 epub）
    assert len([c for c in c35 if c.source_container == ""]) == 1  # 独立来源不带容器


# ---------- 5. REFERENCE_WORK 可处理 ----------

def test_reference_work_processable(fixture):
    root, ledger = fixture
    g = _group(fixture, "book_0001")
    # 预建 full.md → 走到“已存在”检查，证明未被 type 拒绝（进入处理管线）
    out_dir = root / "06_工作区" / "SourcePrepare" / "book_0001_Alpha"
    out_dir.mkdir(parents=True)
    (out_dir / "full.md").write_text("# x\n", encoding="utf-8")
    out = sp.process_book(root, g["work_name"], g["asset_type"], g["files"],
                          g["book_id"], None, False)
    assert out.startswith("SKIP Alpha")
    assert "已存在 full.md" in out


# ---------- 6. NEEDS_REVIEW 拒绝自动处理 ----------

def test_needs_review_skipped(fixture):
    root, ledger = fixture
    g = _group(fixture, "book_0080")
    out = sp.process_book(root, g["work_name"], g["asset_type"], g["files"],
                          g["book_id"], None, False)
    assert out.startswith("SKIP 明朝那些事儿")
    assert "不自动处理" in out


# ---------- 7. RESEARCH 保守：不进参考作品链（结果强制 REVIEW） ----------

def test_research_not_in_reference_chain(fixture, monkeypatch):
    root, ledger = fixture
    g = _group(fixture, "book_0057")
    md = root / "tmp_md.md"
    md.write_text("# 第一章\n内容\n# 第二章\n内容\n", encoding="utf-8")
    fake = sp.Candidate(str(g["files"][0]), ".pdf", "0" * 64)
    fake.temp_md = str(md)
    fake.char_count = 99999
    fake.garbled = 0
    fake.chapter_count = 10
    fake.status = "PASS"
    monkeypatch.setattr(sp, "convert_pdf", lambda p, w: fake)
    monkeypatch.setattr(sp, "choose_candidate", lambda cands: (fake, []))
    monkeypatch.setattr(sp, "split_chapters", lambda text, out_dir: 10)
    out = sp.process_book(root, g["work_name"], g["asset_type"], g["files"],
                          g["book_id"], None, False)
    # PASS 被强制降为 REVIEW：研究资料不进参考作品链
    assert out.startswith("REVIEW 研究报告")


# ---------- 8. LOOSE_MATERIAL 不适用 ----------

def test_loose_material_not_applicable(fixture):
    root, ledger = fixture
    g = _group(fixture, "book_0500")
    out = sp.process_book(root, g["work_name"], g["asset_type"], g["files"],
                          g["book_id"], None, False)
    assert out.startswith("NOT_APPLICABLE 杂项素材")


# ---------- 9. 不依赖目录名称语义 ----------

def test_no_directory_name_semantics(fixture):
    root, ledger = fixture
    # Alpha 位于 random_old_folder/ 下（任意目录名）；只要 ledger 注册即可识别
    cands = sp.collect_candidates(ledger, root)
    a = [c for c in cands if c.book_id == "book_0001"]
    assert len(a) == 1
    assert "random_old_folder" in a[0].path.as_posix()
    groups = sp.group_candidates(cands)
    g = next(x for x in groups if x["book_id"] == "book_0001")
    assert g["work_name"] == "Alpha"
    assert len(g["files"]) == 1
