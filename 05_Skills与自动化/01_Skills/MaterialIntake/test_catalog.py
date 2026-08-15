# -*- coding: utf-8 -*-
"""
MaterialIntake catalog builder 测试（CATALOG_FOUNDATION_ONLY）。

覆盖 A–G 七组：
  A. BOOTSTRAP_COUNTS       141 assets / 182 registered files / 1 container
  B. ID_PRESERVATION        全部 book_xxxx ID 与 legacy CSV 主来源一致、无 gap
  C. MULTI_SOURCE           book_0035 单 asset 双 file（含 source_container）；book_0072 双 file
  D. BKP_RECOVERY           book_0035/0038/0065 knowledge=可用 且 BKP source_sha256 在 files 中
  E. LEGACY_STATUS_RECOVERY CSV SP 状态映射（一次性 migration bootstrap）+ B 优先于 C
  F. IDEMPOTENCY            同输入重建 byte-for-byte（真实 serialize + tmp_path 端到端两次）
  G. VIEW_PARITY            preview 141 数据行 / 9 列；索引不含易变与敏感字段

真实数据测试依赖仓库存在（HAS_REAL），不存在时自动 skip；
纯逻辑测试（_pure / tmp_path）不依赖真实数据，任何环境可跑。
"""

import csv
import hashlib
import json
from pathlib import Path

import pytest

import catalog

ROOT = Path(__file__).resolve().parents[3]
HAS_REAL = (ROOT / catalog.MATERIAL_DIR_NAME / catalog.LEGACY_CSV_FILENAME).exists()

BKP_SHA_EXPECT = {
    "book_0035": "38b604e406bcb58b793a94446433c4a69b4a17de3c25125da4217ccc8f38d8d6",
    "book_0038": "a426098082241b8260ee67112dd656e7677f3d90dab323083f2d0338322a5627",
    "book_0065": "0fb3cde2dc4f8c9f4e5a2ba612f3d3d3eb049d67928cce4fcc8b2c94ea20c6a8",
}

ALL_IDS = [f"book_{i:04d}" for i in range(1, 142)]


def _asset(ledger, bid):
    return next(a for a in ledger["assets"] if a["id"] == bid)


def _ledger_bytes(ledger):
    return json.dumps(ledger, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


@pytest.fixture(scope="module")
def ledger():
    """真实数据一次性构建（含全量 SHA 扫描，模块级缓存）。"""
    if not HAS_REAL:
        pytest.skip("真实素材目录不存在，跳过真实数据测试")
    mat = ROOT / catalog.MATERIAL_DIR_NAME
    scanned = catalog.scan_material_files(mat)
    rows = catalog.load_legacy_csv(mat)
    assets = catalog.build_assets(rows, scanned, ROOT / catalog.DISTILL_DIR_NAME,
                                  ROOT / "06_工作区" / "SourcePrepare")
    manifests = catalog.load_manifests(mat)
    containers = catalog.build_containers(manifests, scanned)
    return catalog.build_ledger(assets, containers)


def _make_fake_tree(root: Path) -> str:
    """构造小型测试树：1 个带 BKP 的网络小说 + 1 个 RESEARCH PDF。返回 epub 的 SHA256。"""
    mat = root / catalog.MATERIAL_DIR_NAME
    (mat / "01_网络小说" / "Alpha").mkdir(parents=True)
    (mat / "05_现代专业资料").mkdir(parents=True)

    epub = mat / "01_网络小说" / "Alpha" / "Alpha (作者A) (z-library.sk, 1lib.sk, z-lib.sk).epub"
    txt = mat / "01_网络小说" / "Alpha" / "Alpha(作者A).txt"
    epub.write_bytes(b"fake epub content")
    txt.write_bytes(b"fake txt content")
    (mat / "05_现代专业资料" / "Beta.pdf").write_bytes(b"fake beta pdf")
    epub_sha = hashlib.sha256(b"fake epub content").hexdigest()

    header = ["作品ID", "作品名", "作者", "资料大类", "标签", "版本", "译者", "出版社",
              "本地相对路径", "文件名", "文件格式", "文件大小", "SHA256", "是否主来源", "来源容器",
              "SourcePrepare状态", "SourcePrepare版本", "标准MD字符数", "识别章节数",
              "BookDistill状态", "最后检查时间", "备注"]
    epub_name = "Alpha (作者A) (z-library.sk, 1lib.sk, z-lib.sk).epub"
    rows = [
        header,
        ["book_0001", "Alpha", "", "网络小说", "", "", "", "",
         f"01_原始素材/01_网络小说/Alpha/{epub_name}", epub_name, "epub", "1", epub_sha,
         "是", "", "未处理", "", "", "", "未开始", "", ""],
        ["book_0001", "Alpha", "", "网络小说", "", "", "", "",
         "01_原始素材/01_网络小说/Alpha/Alpha(作者A).txt", "Alpha(作者A).txt", "txt",
         "1", "x", "否", "", "未处理", "", "", "", "未开始", "", ""],
        ["book_0002", "Beta", "", "现代专业资料", "", "", "", "",
         "01_原始素材/05_现代专业资料/Beta.pdf", "Beta.pdf", "pdf", "1", "y",
         "是", "", "未处理", "", "", "", "未开始", "", ""],
    ]
    with open(mat / catalog.LEGACY_CSV_FILENAME, "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(rows)

    # BKP：book_0001 FINALIZED，source_sha256 匹配 epub
    bkp_dir = root / catalog.DISTILL_DIR_NAME / "book_0001_Alpha" / "bkp"
    bkp_dir.mkdir(parents=True)
    identity = {
        "bkp_version": "0.2",
        "schema_status": "FINALIZED",
        "book": {"book_id": "book_0001", "title": "Alpha", "author": "作者A"},
        "source_snapshot": {"source_sha256": epub_sha},
    }
    (bkp_dir / "identity.json").write_text(
        json.dumps(identity, ensure_ascii=False), encoding="utf-8")
    return epub_sha


# ---------- A. BOOTSTRAP_COUNTS ----------

def test_bootstrap_counts(ledger):
    assert ledger["schema_version"] == "1.0"
    assert len(ledger["assets"]) == 141
    assert sum(len(a["files"]) for a in ledger["assets"]) == 182
    assert len(ledger["containers"]) == 1


# ---------- B. ID_PRESERVATION ----------

def test_id_preservation(ledger):
    assert [a["id"] for a in ledger["assets"]] == ALL_IDS
    rows = catalog.load_legacy_csv(ROOT / catalog.MATERIAL_DIR_NAME)
    csv_ids = sorted({r["作品ID"] for r in rows})
    assert sorted(a["id"] for a in ledger["assets"]) == csv_ids


# ---------- C. MULTI_SOURCE ----------

def test_multi_source_0035(ledger):
    a = _asset(ledger, "book_0035")
    assert len(a["files"]) == 2
    assert len({f["sha256"] for f in a["files"]}) == 2
    epub = next(f for f in a["files"] if f["primary"])
    assert epub["source_container"] == "马伯庸作品合集"
    assert any(f["path"].endswith(".txt") for f in a["files"])


def test_multi_source_0072(ledger):
    a = _asset(ledger, "book_0072")
    assert len(a["files"]) == 2
    assert {f["primary"] for f in a["files"]} == {True, False}


# ---------- D. BKP_RECOVERY ----------

def test_bkp_recovery(ledger):
    for bid, expect_sha in BKP_SHA_EXPECT.items():
        a = _asset(ledger, bid)
        k = a["knowledge"]
        assert k["status"] == "可用"
        assert k["source_sha256"] == expect_sha
        assert k["path"].startswith("02_原著蒸馏/book_")
        assert expect_sha in {f["sha256"] for f in a["files"]}
        assert a["purification"]["status"] == "可用"
        assert a["purification"]["evidence"] == "bkp_source_snapshot"


# ---------- E. LEGACY_STATUS_RECOVERY ----------

def test_legacy_status_recovery_pure():
    assert catalog.derive_purification(None, None, "PASS", set()) == \
        {"status": "可用", "evidence": "legacy_catalog"}
    assert catalog.derive_purification(None, None, "REVIEW", set()) == \
        {"status": "需复核", "evidence": "legacy_catalog"}
    assert catalog.derive_purification(None, None, "FAIL", set()) == \
        {"status": "失败", "evidence": "legacy_catalog"}
    assert catalog.derive_purification(None, None, "", set()) == \
        {"status": "未处理", "evidence": None}


def test_purification_priority_b_over_c(ledger):
    # book_0035 同时具备 legacy PASS（C）与 FINALIZED BKP（B），B 优先
    a = _asset(ledger, "book_0035")
    assert a["purification"] == {"status": "可用", "evidence": "bkp_source_snapshot"}


# ---------- F. IDEMPOTENCY ----------

def test_idempotency_serialize(ledger):
    b1 = _ledger_bytes(catalog.build_ledger(ledger["assets"], ledger["containers"]))
    b2 = _ledger_bytes(catalog.build_ledger(ledger["assets"], ledger["containers"]))
    assert b1 == b2


def test_idempotency_end_to_end(tmp_path):
    _make_fake_tree(tmp_path)
    preview = tmp_path / "out"
    preview.mkdir()

    def snap():
        files = [
            tmp_path / catalog.MATERIAL_DIR_NAME / catalog.LEDGER_FILENAME,
            tmp_path / catalog.MATERIAL_DIR_NAME / catalog.INDEX_FILENAME,
            preview / catalog.PREVIEW_FILENAME,
        ]
        return {p.name: p.read_bytes() for p in files}

    assert catalog.main(["--root", str(tmp_path), "--preview-dir", str(preview)]) == 0
    first = snap()
    assert catalog.main(["--root", str(tmp_path), "--preview-dir", str(preview)]) == 0
    assert snap() == first


def test_fake_tree_recovery(tmp_path):
    epub_sha = _make_fake_tree(tmp_path)
    preview = tmp_path / "out"
    preview.mkdir()
    assert catalog.main(["--root", str(tmp_path), "--preview-dir", str(preview)]) == 0
    ledger = json.loads(
        (tmp_path / catalog.MATERIAL_DIR_NAME / catalog.LEDGER_FILENAME).read_text(encoding="utf-8"))
    a = next(x for x in ledger["assets"] if x["id"] == "book_0001")
    # BKP FINALIZED + SHA 匹配 → 可用；作者从 BKP identity 恢复
    assert a["knowledge"] == {"status": "可用", "path": "02_原著蒸馏/book_0001_Alpha",
                              "source_sha256": epub_sha}
    assert a["purification"] == {"status": "可用", "evidence": "bkp_source_snapshot"}
    assert a["author"] == "作者A"
    b = next(x for x in ledger["assets"] if x["id"] == "book_0002")
    assert b["type"] == "RESEARCH"
    assert b["knowledge"] == {"status": "未开始"}


# ---------- G. VIEW_PARITY ----------

def test_view_parity(ledger):
    rows = catalog.generate_preview_rows(ledger)
    assert rows[0] == ["素材ID", "名称", "类型", "作者", "标签", "位置", "提纯", "知识", "备注"]
    assert len(rows) == 142  # 1 表头 + 141 数据行
    assert all(len(r) == 9 for r in rows)
    assert [r[0] for r in rows[1:]] == ALL_IDS


def test_index_generation(ledger):
    text = catalog.generate_index(ledger)
    assert "素材总数：141" in text
    assert "## 参考作品（REFERENCE_WORK）" in text
    assert "## 研究资料（RESEARCH）" in text
    assert "## 待确认（NEEDS_REVIEW）" in text
    for banned in ("sha256", "SHA256", "z-library", "文件大小", "更新时间", "章节数"):
        assert banned not in text


def test_container(ledger):
    c = ledger["containers"][0]
    assert c["id"] == "马伯庸作品合集"
    assert c["split_count"] == 21
    assert "book_0035" in c["split_book_ids"]
    assert c["original"]["sha256"] == \
        "26f9d85186cc0afac16a144d48de8a4c931bc29a518078492a392b2122c074ee"


# ---------- 纯逻辑单元测试（不依赖真实数据） ----------

def test_bootstrap_type_pure():
    assert catalog.bootstrap_type("网络小说", "任意") == "REFERENCE_WORK"
    assert catalog.bootstrap_type("外国文学", "任意") == "REFERENCE_WORK"
    assert catalog.bootstrap_type("中文文学", "普通作品") == "REFERENCE_WORK"
    assert catalog.bootstrap_type("中文文学", "明朝那些事儿") == "NEEDS_REVIEW"
    assert catalog.bootstrap_type("中文文学", "事实证明，人民永远是最可爱的") == "NEEDS_REVIEW"
    assert catalog.bootstrap_type("中文文学", "我读书少你可别骗我") == "NEEDS_REVIEW"
    assert catalog.bootstrap_type("现代专业资料", "任意") == "RESEARCH"


def test_parse_author_pure():
    assert catalog.parse_author_from_filename(
        "一世之尊 (爱潜水的乌贼) (z-library.sk, 1lib.sk, z-lib.sk).epub") == "爱潜水的乌贼"
    assert catalog.parse_author_from_filename(
        "围城 (出版七十周年纪念版) (钱锺书) (z-library.sk, 1lib.sk, z-lib.sk).epub") == "钱锺书"
    assert catalog.parse_author_from_filename("创业在晚唐(痴人陈).epub") == "痴人陈"
    # 册标记 / 版本 / 系列标注 → 拒绝
    assert catalog.parse_author_from_filename("三国机密（上）龙难日.epub") == ""
    assert catalog.parse_author_from_filename("基督山伯爵（读客版）.epub") == ""
    assert catalog.parse_author_from_filename("战争与和平（名著名译丛书）.epub") == ""
    assert catalog.parse_author_from_filename(
        "尘埃落定：纪念版（畅销单行版） (阿来著) (z-library.sk, 1lib.sk, z-lib.sk).epub") == ""
    # 多候选（含译者）→ 保守放弃
    assert catalog.parse_author_from_filename("韩江 胡椒筒.epub") == ""
    assert catalog.parse_author_from_filename(
        "傲慢与偏见 (简·奥斯汀,李继宏 译) (z-library.sk, 1lib.sk, z-lib.sk).epub") == ""


def test_derive_knowledge_pure():
    bkp_ok = {"finalized": True, "source_sha256": "abc",
              "dir_rel": "02_原著蒸馏/book_x", "author": "A"}
    assert catalog.derive_knowledge(bkp_ok, {"abc"}) == \
        {"status": "可用", "path": "02_原著蒸馏/book_x", "source_sha256": "abc"}
    assert catalog.derive_knowledge(bkp_ok, {"def"})["status"] == "需更新"
    assert catalog.derive_knowledge(None, {"abc"}) == {"status": "未开始"}
    not_final = dict(bkp_ok, finalized=False)
    assert catalog.derive_knowledge(not_final, {"abc"}) == {"status": "未开始"}
