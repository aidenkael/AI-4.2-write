# -*- coding: utf-8 -*-
"""
MaterialIntake catalog builder 测试（CANONICAL_CATALOG，Phase 2B1）。

覆盖（原 A–H + Phase 2B1 cutover A–H + SP contract + 枚举）：
  A. BOOTSTRAP_COUNTS       141 assets / 182 registered files / 1 container
  B. ID_PRESERVATION        全部 book_xxxx ID 稳定、无 gap
  C. MULTI_SOURCE           book_0035 单 asset 双 file（含 source_container）；book_0072 双 file
  D. BKP_RECOVERY           book_0035/0038/0065 knowledge=可用 且 BKP source_sha256 在 files 中
  E. EVIDENCE_PRIORITY      无证据 → 未处理；FINALIZED BKP 优先于无证据
  F. IDEMPOTENCY            同输入重建 byte-for-byte（真实 serialize + tmp_path 端到端两次）
  G. VIEW_PARITY            9 列 CSV（142 行）/ 索引不含易变与敏感字段
  H. SP_CONTRACT            真实目录 discovery + metadata schema（PASS/REVIEW/FAIL/缺失/歧义）

Phase 2B1 cutover tests：
  A. LEDGER_ONLY_REBUILD       删除 legacy CSV 后从 ledger 正常 refresh/render
  B. SEMANTIC_FIELD_PRESERVATION 手工改 type/tags/notes/author → refresh 后保持
  C. FILE_SHA_REFRESH          registered file 内容变化 → SHA 更新 + SP/BKP 变需更新
  D. MISSING_REGISTERED_FILE   registered path 丢失 → fail 且原 ledger 不被半写
  E. UNREGISTERED_FILE         磁盘多一个未知 EPUB → 报告；不创建 asset / 新 ID
  F. CSV_VIEW                  正式 CSV 9 列、一 asset 一行、无 legacy 技术字段
  G. CSV_IS_DERIVED            篡改 CSV 再 render → 被 ledger 重建，CSV 修改不反向污染 ledger
  H. IDEMPOTENCY               连续 refresh/render 两次 → ledger/CSV/MD byte-for-byte 不变

Phase 2B1.1 persistence tests：
  A. SP_PASS_SURVIVES_WORKSPACE_CLEANUP    PASS 结算 → 删 workspace → 仍可用；改素材 → 需更新
  B. SP_REVIEW_SURVIVES_WORKSPACE_CLEANUP  REVIEW 结算 → 删 workspace → 仍需复核
  C. SP_FAIL_SURVIVES_WORKSPACE_CLEANUP    FAIL 结算 → 删 workspace → 仍失败
  D. SOURCE_CHANGE_MARKS_STALE             素材变化 → 需更新（旧可用不覆盖已变化素材）
  E. MISSING_CONTAINER_ORIGINAL_FAILS_SAFE container original 缺失 → rc!=0 且三文件不被半写
  F. PERSISTENT_RECORD_PURE                持久 record 匹配保持 / 变化判需更新（纯逻辑）
  G. REAL_LEDGER_COMPAT                    真实 ledger refresh 后不降级 + BKP record 补写

Phase 2B1.2 fingerprint/path decoupling tests：
  H. PATH_MOVE_PRESERVES_PURIFICATION     目录迁移/文件改名 → content fingerprint 不变 → 仍可用
  I. RENAME_PRESERVES_PURIFICATION         同 H（改名场景合并覆盖）
  J. CONTENT_CHANGE_MARKS_STALE            路径与 bytes 同时变化 → 仍需更新
  K. SOURCE_SET_CHANGE_MARKS_STALE         [A,B] vs [A,C]/[A,B,C]/[A] 均不同；[B,A]==[A,B]；multiset 保留重复
  L. LEGACY_FINGERPRINT_MIGRATION          旧 path-based record → 自动迁移为 content fingerprint，
                                          状态/source_sha256 不降级，第二次 refresh byte-for-byte 不变

真实数据测试依赖仓库存在（HAS_REAL），不存在时自动 skip；
纯逻辑测试（_pure / tmp_path）不依赖真实数据，任何环境可跑。
"""

import csv
import hashlib
import json
import shutil
from pathlib import Path

import pytest

import catalog

ROOT = Path(__file__).resolve().parents[3]
HAS_REAL = (ROOT / catalog.MATERIAL_DIR_NAME / catalog.LEDGER_FILENAME).exists()

BKP_SHA_EXPECT = {
    "book_0035": "38b604e406bcb58b793a94446433c4a69b4a17de3c25125da4217ccc8f38d8d6",
    "book_0038": "a426098082241b8260ee67112dd656e7677f3d90dab323083f2d0338322a5627",
    "book_0065": "0fb3cde2dc4f8c9f4e5a2ba612f3d3d3eb049d67928cce4fcc8b2c94ea20c6a8",
}

ALL_IDS = [f"book_{i:04d}" for i in range(1, 142)]

CSV_HEADER = ["素材ID", "名称", "类型", "作者", "标签", "位置", "提纯", "知识", "备注"]


def _asset(ledger, bid):
    return next(a for a in ledger["assets"] if a["id"] == bid)


def _ledger_bytes(ledger):
    return json.dumps(ledger, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


@pytest.fixture(scope="module")
def ledger():
    """真实数据：直接加载 canonical ledger（Phase 2B1 后 CSV/MD 均为 derived，不做输入）。
    注意：不能再用 load_legacy_csv 重建——素材清单.csv 已是 9 列 derived 视图。
    migration helper 路径由 _build_fake_ledger（tmp_path 自建 legacy 22 列 CSV）单独覆盖。
    """
    if not HAS_REAL:
        pytest.skip("真实素材目录不存在，跳过真实数据测试")
    mat = ROOT / catalog.MATERIAL_DIR_NAME
    return catalog.load_ledger(mat / catalog.LEDGER_FILENAME)


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


def _build_fake_ledger(root: Path) -> str:
    """在 fake tree 上走 migration helper 生成并落盘 ledger；返回 epub_sha。

    模拟 Phase 2A 产物：素材资产.json 已存在，legacy CSV 随后即可退役。
    """
    epub_sha = _make_fake_tree(root)
    mat = root / catalog.MATERIAL_DIR_NAME
    scanned = catalog.scan_material_files(mat)
    rows = catalog.load_legacy_csv(mat)
    assets = catalog.build_assets(rows, scanned, root / catalog.DISTILL_DIR_NAME,
                                  root / "06_工作区" / "SourcePrepare")
    containers = catalog.build_containers(catalog.load_manifests(mat), scanned)
    catalog.write_ledger(catalog.build_ledger(assets, containers), mat / catalog.LEDGER_FILENAME)
    return epub_sha


def _read_ledger(root: Path) -> dict:
    mat = root / catalog.MATERIAL_DIR_NAME
    return json.loads((mat / catalog.LEDGER_FILENAME).read_text(encoding="utf-8"))


# ---------- A. BOOTSTRAP_COUNTS ----------

def test_bootstrap_counts(ledger):
    assert ledger["schema_version"] == "1.0"
    assert len(ledger["assets"]) == 141
    assert sum(len(a["files"]) for a in ledger["assets"]) == 182
    assert len(ledger["containers"]) == 1


# ---------- B. ID_PRESERVATION ----------

def test_id_preservation(ledger):
    assert [a["id"] for a in ledger["assets"]] == ALL_IDS
    # derived CSV 的素材ID 列与 ledger 一致
    rows = catalog.render_catalog_csv(ledger)
    assert [r[0] for r in rows[1:]] == ALL_IDS


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
        assert k["path"].startswith("02_素材知识库/book_")
        assert expect_sha in {f["sha256"] for f in a["files"]}
        assert a["purification"]["status"] == "可用"
        assert a["purification"]["evidence"] == "bkp_source_snapshot"


# ---------- E. EVIDENCE_PRIORITY ----------

def test_no_evidence_unprocessed_pure():
    # legacy C 级证据已随 Phase 2B1 cutover 退役：无证据 → 未处理
    assert catalog.derive_purification(None, None, set()) == \
        {"status": "未处理", "evidence": None}
    assert catalog.derive_purification(None, None, {"abc"}) == \
        {"status": "未处理", "evidence": None}


def test_purification_priority_bkp_over_no_evidence(tmp_path):
    # 无 SP metadata + FINALIZED BKP + SHA 匹配 → B 级推导为可用，并补写长期 record
    epub_sha = _build_fake_ledger(tmp_path)
    assert catalog.main(["--root", str(tmp_path)]) == 0
    a = _asset(_read_ledger(tmp_path), "book_0001")
    assert a["purification"]["status"] == "可用"
    assert a["purification"]["evidence"] == "bkp_source_snapshot"
    assert a["purification"]["source_sha256"] == epub_sha
    assert "input_fingerprint" in a["purification"]  # BKP 恢复项补写持久 record


# ---------- F. IDEMPOTENCY ----------

def test_idempotency_serialize(ledger):
    b1 = _ledger_bytes(catalog.build_ledger(ledger["assets"], ledger["containers"]))
    b2 = _ledger_bytes(catalog.build_ledger(ledger["assets"], ledger["containers"]))
    assert b1 == b2


def test_idempotency_end_to_end(tmp_path):
    # H. IDEMPOTENCY：连续 refresh/render 两次 → ledger/CSV/MD byte-for-byte 不变
    _build_fake_ledger(tmp_path)
    mat = tmp_path / catalog.MATERIAL_DIR_NAME

    def snap():
        files = [mat / catalog.LEDGER_FILENAME, mat / catalog.LEGACY_CSV_FILENAME,
                 mat / catalog.INDEX_FILENAME]
        return {p.name: p.read_bytes() for p in files}

    assert catalog.main(["--root", str(tmp_path)]) == 0
    first = snap()
    assert catalog.main(["--root", str(tmp_path)]) == 0
    assert snap() == first


def test_fake_tree_recovery(tmp_path):
    epub_sha = _build_fake_ledger(tmp_path)
    assert catalog.main(["--root", str(tmp_path)]) == 0
    ledger = _read_ledger(tmp_path)
    a = next(x for x in ledger["assets"] if x["id"] == "book_0001")
    # BKP FINALIZED + SHA 匹配 → 可用；作者从 BKP identity 恢复；purification 补写持久字段
    assert a["knowledge"] == {"status": "可用", "path": "02_素材知识库/book_0001_Alpha",
                              "source_sha256": epub_sha}
    assert a["purification"]["status"] == "可用"
    assert a["purification"]["evidence"] == "bkp_source_snapshot"
    assert a["purification"]["source_sha256"] == epub_sha
    assert "input_fingerprint" in a["purification"]
    assert a["author"] == "作者A"
    b = next(x for x in ledger["assets"] if x["id"] == "book_0002")
    assert b["type"] == "RESEARCH"
    assert b["knowledge"] == {"status": "未开始"}


# ---------- G. VIEW_PARITY ----------

def test_view_parity(ledger):
    rows = catalog.render_catalog_csv(ledger)
    assert rows[0] == CSV_HEADER
    assert len(rows) == 142  # 1 表头 + 141 数据行
    assert all(len(r) == 9 for r in rows)
    assert [r[0] for r in rows[1:]] == ALL_IDS


def test_csv_excludes_legacy_fields(ledger):
    # 正式 CSV 不含 legacy 技术字段 / 时间戳（legacy 列名 / 字段名）
    # 注意：banned 用精确字段名（如 "来源网站"），不能是宽泛子串（如 "来源"）——
    # notes 是 canonical 字段，可含 "选中来源：…" 等自然文本，不应被误伤。
    text = "\n".join(",".join(r) for r in catalog.render_catalog_csv(ledger))
    for banned in ("SHA", "文件大小", "文件格式", "来源网站", "SourcePrepare版本", "章节数",
                   "BookDistill", "更新时间", "本地相对路径", "是否主来源"):
        assert banned not in text


def test_index_generation(ledger):
    text = catalog.render_index_md(ledger)
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


# ---------- Phase 2B1 cutover tests ----------

def test_ledger_only_rebuild(tmp_path):
    # A. LEDGER_ONLY_REBUILD：删除/不存在 legacy 22 列输入也能从 ledger 正常 refresh/render
    _build_fake_ledger(tmp_path)
    mat = tmp_path / catalog.MATERIAL_DIR_NAME
    (mat / catalog.LEGACY_CSV_FILENAME).unlink()
    assert catalog.main(["--root", str(tmp_path)]) == 0
    assert (mat / catalog.LEDGER_FILENAME).exists()
    assert (mat / catalog.LEGACY_CSV_FILENAME).exists()  # 重建为 9 列 derived CSV
    assert (mat / catalog.INDEX_FILENAME).exists()
    ledger = _read_ledger(tmp_path)
    assert len(ledger["assets"]) == 2
    rows = list(csv.reader(open(mat / catalog.LEGACY_CSV_FILENAME, encoding="utf-8-sig")))
    assert rows[0] == CSV_HEADER
    assert len(rows) == 3  # 表头 + 2 数据行


def test_semantic_field_preservation(tmp_path):
    # B. SEMANTIC_FIELD_PRESERVATION：作者已确认的 type/tags/notes/author 不被 refresh 覆盖
    _build_fake_ledger(tmp_path)
    mat = tmp_path / catalog.MATERIAL_DIR_NAME
    ledger_path = mat / catalog.LEDGER_FILENAME
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    a = next(x for x in ledger["assets"] if x["id"] == "book_0001")
    a["type"] = "RESEARCH"          # 作者手工确认的语义字段
    a["tags"] = ["作者确认标签"]
    a["notes"] = "作者确认备注"
    a["author"] = "作者确认"
    catalog.write_ledger(ledger, ledger_path)
    assert catalog.main(["--root", str(tmp_path)]) == 0
    a2 = _asset(_read_ledger(tmp_path), "book_0001")
    assert a2["type"] == "RESEARCH"
    assert a2["tags"] == ["作者确认标签"]
    assert a2["notes"] == "作者确认备注"
    assert a2["author"] == "作者确认"


def test_file_sha_refresh(tmp_path):
    # C. FILE_SHA_REFRESH：registered file 原地内容变化 → SHA 更新 + SP/BKP 变需更新
    _build_fake_ledger(tmp_path)
    mat = tmp_path / catalog.MATERIAL_DIR_NAME
    epub = mat / "01_网络小说" / "Alpha" / "Alpha (作者A) (z-library.sk, 1lib.sk, z-lib.sk).epub"
    epub.write_bytes(b"new fake epub content")  # 原地内容变化
    assert catalog.main(["--root", str(tmp_path)]) == 0
    ledger = _read_ledger(tmp_path)
    a = _asset(ledger, "book_0001")
    new_sha = hashlib.sha256(b"new fake epub content").hexdigest()
    epub_file = next(f for f in a["files"] if f["path"].endswith(".epub"))
    assert epub_file["sha256"] == new_sha
    # 旧 BKP fingerprint ≠ 当前文件 SHA → 需更新（不自动改 knowledge path）
    assert a["knowledge"]["status"] == "需更新"
    assert a["purification"]["status"] == "需更新"


def test_missing_registered_file(tmp_path):
    # D. MISSING_REGISTERED_FILE：registered path 丢失 → fail 且原 ledger 不被半写
    _build_fake_ledger(tmp_path)
    mat = tmp_path / catalog.MATERIAL_DIR_NAME
    (mat / "01_网络小说" / "Alpha" / "Alpha(作者A).txt").unlink()
    before = (mat / catalog.LEDGER_FILENAME).read_bytes()
    rc = catalog.main(["--root", str(tmp_path)])
    assert rc == 1
    after = (mat / catalog.LEDGER_FILENAME).read_bytes()
    assert before == after  # 原 ledger 保持原样
    # CSV / MD 也未写入（保持缺失状态 → 无半写产物）
    assert not (mat / catalog.INDEX_FILENAME).exists()


def test_unregistered_file(tmp_path):
    # E. UNREGISTERED_FILE：磁盘多一个未知 EPUB → 报告；不创建 asset / 新 ID
    _build_fake_ledger(tmp_path)
    mat = tmp_path / catalog.MATERIAL_DIR_NAME
    extra = mat / "05_其他参考资料" / "unknown_new.epub"
    extra.parent.mkdir(parents=True)
    extra.write_bytes(b"unregistered epub")
    assert catalog.main(["--root", str(tmp_path)]) == 0
    ledger = _read_ledger(tmp_path)
    assert len(ledger["assets"]) == 2  # 不创建新 asset
    assert {a["id"] for a in ledger["assets"]} == {"book_0001", "book_0002"}


def test_csv_view(ledger):
    # F. CSV_VIEW：正式 CSV 9 列、一 asset 一行（真实数据 141 数据行）
    rows = catalog.render_catalog_csv(ledger)
    assert rows[0] == CSV_HEADER
    assert len(rows) == 142
    assert all(len(r) == 9 for r in rows)
    # book_0035 单 asset 仅一行
    assert sum(1 for r in rows[1:] if r[0] == "book_0035") == 1


def test_csv_is_derived(tmp_path):
    # G. CSV_IS_DERIVED：篡改 CSV 再 render → 被 ledger 重建；CSV 修改不反向污染 ledger
    _build_fake_ledger(tmp_path)
    mat = tmp_path / catalog.MATERIAL_DIR_NAME
    assert catalog.main(["--root", str(tmp_path)]) == 0
    csv_path = mat / catalog.LEGACY_CSV_FILENAME
    rows = list(csv.reader(open(csv_path, encoding="utf-8-sig")))
    rows[1][1] = "被篡改的名称"
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows(rows)
    assert catalog.main(["--root", str(tmp_path)]) == 0
    rows2 = list(csv.reader(open(csv_path, encoding="utf-8-sig")))
    assert rows2[1][1] == "Alpha"  # 被 ledger 重建
    assert _asset(_read_ledger(tmp_path), "book_0001")["name"] == "Alpha"  # ledger 未被污染


# ---------- Phase 2B1.1 persistence tests ----------

def test_sp_pass_survives_workspace_cleanup(tmp_path):
    # A. SP_PASS_SURVIVES_WORKSPACE_CLEANUP：正式 PASS 结算进 ledger → 删 workspace → 仍可用
    _build_fake_ledger(tmp_path)
    mat = tmp_path / catalog.MATERIAL_DIR_NAME
    sp_dir = tmp_path / "06_工作区" / "SourcePrepare"
    epub = mat / "01_网络小说" / "Alpha" / "Alpha (作者A) (z-library.sk, 1lib.sk, z-lib.sk).epub"
    epub_sha = hashlib.sha256(b"fake epub content").hexdigest()
    _write_sp_metadata(sp_dir, "book_0001", "PASS", epub_sha)
    assert catalog.main(["--root", str(tmp_path)]) == 0
    p = _asset(_read_ledger(tmp_path), "book_0001")["purification"]
    assert p["status"] == "可用"
    assert p["evidence"] == "sourceprepare_metadata"
    assert p["source_sha256"] == epub_sha
    assert "input_fingerprint" in p
    fp_after_pass = p["input_fingerprint"]
    # 删除整个 06_工作区/SourcePrepare/<book_id>_<书名>/ → 再 refresh → 仍可用（不得退回未处理）
    shutil.rmtree(sp_dir)
    assert catalog.main(["--root", str(tmp_path)]) == 0
    p2 = _asset(_read_ledger(tmp_path), "book_0001")["purification"]
    assert p2["status"] == "可用"
    assert p2["input_fingerprint"] == fp_after_pass
    # 素材内容变化 → 再 refresh → 需更新（旧可用不覆盖已变化素材）
    epub.write_bytes(b"changed fake epub content")
    assert catalog.main(["--root", str(tmp_path)]) == 0
    p3 = _asset(_read_ledger(tmp_path), "book_0001")["purification"]
    assert p3["status"] == "需更新"
    assert p3["evidence"] == "sourceprepare_record_input_changed"


def test_sp_review_survives_workspace_cleanup(tmp_path):
    # B. SP_REVIEW_SURVIVES_WORKSPACE_CLEANUP：REVIEW 结算 → 删 workspace → 仍需复核
    _build_fake_ledger(tmp_path)
    mat = tmp_path / catalog.MATERIAL_DIR_NAME
    sp_dir = tmp_path / "06_工作区" / "SourcePrepare"
    epub_sha = hashlib.sha256(b"fake epub content").hexdigest()
    _write_sp_metadata(sp_dir, "book_0001", "REVIEW", epub_sha)
    assert catalog.main(["--root", str(tmp_path)]) == 0
    p = _asset(_read_ledger(tmp_path), "book_0001")["purification"]
    assert p["status"] == "需复核"
    shutil.rmtree(sp_dir)
    assert catalog.main(["--root", str(tmp_path)]) == 0
    p2 = _asset(_read_ledger(tmp_path), "book_0001")["purification"]
    assert p2["status"] == "需复核"  # 不因 workspace 清理丢失正式结果


def test_sp_fail_survives_workspace_cleanup(tmp_path):
    # C. SP_FAIL_SURVIVES_WORKSPACE_CLEANUP：FAIL 结算 → 删 workspace → 仍失败
    _build_fake_ledger(tmp_path)
    mat = tmp_path / catalog.MATERIAL_DIR_NAME
    sp_dir = tmp_path / "06_工作区" / "SourcePrepare"
    epub_sha = hashlib.sha256(b"fake epub content").hexdigest()
    _write_sp_metadata(sp_dir, "book_0001", "FAIL", epub_sha)
    assert catalog.main(["--root", str(tmp_path)]) == 0
    p = _asset(_read_ledger(tmp_path), "book_0001")["purification"]
    assert p["status"] == "失败"
    shutil.rmtree(sp_dir)
    assert catalog.main(["--root", str(tmp_path)]) == 0
    p2 = _asset(_read_ledger(tmp_path), "book_0001")["purification"]
    assert p2["status"] == "失败"  # 正式失败结果同样持久


def test_path_move_does_not_mark_purification_stale(tmp_path):
    # H+I. PATH_MOVE_PRESERVES_PURIFICATION / RENAME_PRESERVES_PURIFICATION：
    # 目录迁移 + 文件改名 → sha256 不变 → content fingerprint 不变 → 仍可用（不得需更新）
    _build_fake_ledger(tmp_path)
    mat = tmp_path / catalog.MATERIAL_DIR_NAME
    sp_dir = tmp_path / "06_工作区" / "SourcePrepare"
    old_epub = mat / "01_网络小说" / "Alpha" \
        / "Alpha (作者A) (z-library.sk, 1lib.sk, z-lib.sk).epub"
    epub_sha = hashlib.sha256(b"fake epub content").hexdigest()
    _write_sp_metadata(sp_dir, "book_0001", "PASS", epub_sha)
    assert catalog.main(["--root", str(tmp_path)]) == 0
    p = _asset(_read_ledger(tmp_path), "book_0001")["purification"]
    assert p["status"] == "可用"
    fp_before = p["input_fingerprint"]
    # 删 workspace → 物理移动文件到新目录并改名 → 同步修改 ledger files[].path（sha256 不变）
    shutil.rmtree(sp_dir)
    new_dir = mat / "02_中文文学" / "Alpha_renamed"
    new_dir.mkdir(parents=True)
    (mat / "01_网络小说" / "Alpha" / "Alpha(作者A).txt").rename(new_dir / "Alpha_renamed.txt")
    old_epub.rename(new_dir / "Alpha_renamed.epub")
    ledger = _read_ledger(tmp_path)
    for f in _asset(ledger, "book_0001")["files"]:
        f["path"] = f["path"].replace("01_网络小说/Alpha/", "02_中文文学/Alpha_renamed/")
        f["path"] = f["path"].replace(
            "Alpha (作者A) (z-library.sk, 1lib.sk, z-lib.sk).epub", "Alpha_renamed.epub")
        f["path"] = f["path"].replace("Alpha(作者A).txt", "Alpha_renamed.txt")
    catalog.write_ledger(ledger, mat / catalog.LEDGER_FILENAME)
    # refresh → 仍可用，input_fingerprint 与迁移前 content fingerprint 相同
    assert catalog.main(["--root", str(tmp_path)]) == 0
    p2 = _asset(_read_ledger(tmp_path), "book_0001")["purification"]
    assert p2["status"] == "可用"
    assert p2["input_fingerprint"] == fp_before


def test_content_change_marks_stale_with_path_change(tmp_path):
    # J. CONTENT_CHANGE_MARKS_STALE：路径同时变化 + bytes 变化 → 仍需更新（路径无关 ≠ 任何移动都算没变）
    _build_fake_ledger(tmp_path)
    mat = tmp_path / catalog.MATERIAL_DIR_NAME
    sp_dir = tmp_path / "06_工作区" / "SourcePrepare"
    epub = mat / "01_网络小说" / "Alpha" \
        / "Alpha (作者A) (z-library.sk, 1lib.sk, z-lib.sk).epub"
    epub_sha = hashlib.sha256(b"fake epub content").hexdigest()
    _write_sp_metadata(sp_dir, "book_0001", "PASS", epub_sha)
    assert catalog.main(["--root", str(tmp_path)]) == 0
    shutil.rmtree(sp_dir)
    # 物理移动 + 内容变化 → ledger path 同步 → refresh → 需更新
    new_dir = mat / "02_中文文学" / "Alpha"
    new_dir.mkdir(parents=True)
    (mat / "01_网络小说" / "Alpha" / "Alpha(作者A).txt").rename(new_dir / "Alpha.txt")
    epub.rename(new_dir / "Alpha.epub")
    new_epub = new_dir / "Alpha.epub"
    new_epub.write_bytes(b"changed fake epub content")
    ledger = _read_ledger(tmp_path)
    for f in _asset(ledger, "book_0001")["files"]:
        f["path"] = f["path"].replace("01_网络小说/Alpha/", "02_中文文学/Alpha/")
        f["path"] = f["path"].replace(
            "Alpha (作者A) (z-library.sk, 1lib.sk, z-lib.sk).epub", "Alpha.epub")
        f["path"] = f["path"].replace("Alpha(作者A).txt", "Alpha.txt")
    catalog.write_ledger(ledger, mat / catalog.LEDGER_FILENAME)
    assert catalog.main(["--root", str(tmp_path)]) == 0
    p = _asset(_read_ledger(tmp_path), "book_0001")["purification"]
    assert p["status"] == "需更新"
    assert p["evidence"] == "sourceprepare_record_input_changed"


def test_legacy_fingerprint_migration_end_to_end(tmp_path):
    # L. LEGACY_FINGERPRINT_MIGRATION：旧 path-based record → 自动迁移，状态/sha 不降级，幂等
    _build_fake_ledger(tmp_path)
    mat = tmp_path / catalog.MATERIAL_DIR_NAME
    sp_dir = tmp_path / "06_工作区" / "SourcePrepare"
    epub_sha = hashlib.sha256(b"fake epub content").hexdigest()
    _write_sp_metadata(sp_dir, "book_0001", "PASS", epub_sha)
    assert catalog.main(["--root", str(tmp_path)]) == 0
    # 删 workspace → 把 input_fingerprint 改成旧 path-based 算法值（模拟 Phase 2B1.1 record）
    shutil.rmtree(sp_dir)
    ledger = _read_ledger(tmp_path)
    a = _asset(ledger, "book_0001")
    legacy_fp = catalog.legacy_path_fingerprint(a["files"])
    content_fp = catalog.content_fingerprint(a["files"])
    assert legacy_fp != content_fp  # 旧算法与新算法确实不同（path 参与计算）
    a["purification"]["input_fingerprint"] = legacy_fp
    catalog.write_ledger(ledger, mat / catalog.LEDGER_FILENAME)
    # refresh → 迁移：保持可用 + source_sha256，input_fingerprint 自动改为 content fingerprint
    assert catalog.main(["--root", str(tmp_path)]) == 0
    p = _asset(_read_ledger(tmp_path), "book_0001")["purification"]
    assert p["status"] == "可用"
    assert p["source_sha256"] == epub_sha
    assert p["input_fingerprint"] == content_fp
    # 第二次 refresh → 三文件 byte-for-byte 不变（迁移完成后稳定）
    ledger_path = mat / catalog.LEDGER_FILENAME
    ledger_bytes = ledger_path.read_bytes()
    csv_bytes = (mat / catalog.LEGACY_CSV_FILENAME).read_bytes()
    idx_bytes = (mat / catalog.INDEX_FILENAME).read_bytes()
    assert catalog.main(["--root", str(tmp_path)]) == 0
    assert ledger_path.read_bytes() == ledger_bytes
    assert (mat / catalog.LEGACY_CSV_FILENAME).read_bytes() == csv_bytes
    assert (mat / catalog.INDEX_FILENAME).read_bytes() == idx_bytes


def test_container_original_missing_fails_safe(tmp_path):
    # E. MISSING_CONTAINER_ORIGINAL_FAILS_SAFE：container original 缺失 → rc!=0 且三文件不被半写
    _build_fake_ledger(tmp_path)
    mat = tmp_path / catalog.MATERIAL_DIR_NAME
    orig = mat / "01_网络小说" / "Alpha" / "Alpha合集原始.epub"
    orig.write_bytes(b"original container epub")
    orig_sha = hashlib.sha256(b"original container epub").hexdigest()
    ledger_path = mat / catalog.LEDGER_FILENAME
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["containers"] = [{
        "id": "Alpha合集", "container_dir": "01_网络小说/Alpha", "category": "",
        "source_format": "epub",
        "manifest_path": "01_网络小说/Alpha/collection_manifest.json",
        "original": {"path": "01_网络小说/Alpha/Alpha合集原始.epub",
                     "filename": "Alpha合集原始.epub", "sha256": orig_sha},
        "split_count": 0, "split_book_ids": [],
    }]
    catalog.write_ledger(ledger, ledger_path)
    # original 存在时 refresh 正常（container original 已登记 → 不算 unregistered）
    assert catalog.main(["--root", str(tmp_path)]) == 0
    # 删除 original → refresh 必须失败（不得静默保留旧 SHA 并返回成功），三文件不被半写
    orig.unlink()
    before = ledger_path.read_bytes()
    csv_before = (mat / catalog.LEGACY_CSV_FILENAME).read_bytes()
    idx_before = (mat / catalog.INDEX_FILENAME).read_bytes()
    rc = catalog.main(["--root", str(tmp_path)])
    assert rc == 1
    assert ledger_path.read_bytes() == before
    assert (mat / catalog.LEGACY_CSV_FILENAME).read_bytes() == csv_before
    assert (mat / catalog.INDEX_FILENAME).read_bytes() == idx_before


def test_real_ledger_refresh_compat(ledger):
    # G. REAL_LEDGER_COMPAT：真实 ledger refresh 后不降级 + BKP record 补写（只读，不写盘）
    mat = ROOT / catalog.MATERIAL_DIR_NAME
    new_ledger, report = catalog.refresh_ledger(
        ledger, mat, ROOT / catalog.DISTILL_DIR_NAME, ROOT / "06_工作区" / "SourcePrepare")
    assert report["missing"] == []
    assert [a["id"] for a in new_ledger["assets"]] == ALL_IDS
    assert sum(len(a["files"]) for a in new_ledger["assets"]) == 182
    assert len(new_ledger["containers"]) == 1
    statuses = [a["purification"]["status"] for a in new_ledger["assets"]]
    assert statuses.count("可用") == 4  # book_0035/0038/0065(BKP) + book_0003 亮剑(SP PASS)
    assert statuses.count("未处理") == 137
    for bid, expect_sha in BKP_SHA_EXPECT.items():
        p = _asset(new_ledger, bid)["purification"]
        assert p["status"] == "可用"  # 0035/0038/0065 不得降级
        assert p["evidence"] == "bkp_source_snapshot"
        assert p["source_sha256"] == expect_sha
        assert "input_fingerprint" in p  # BKP 恢复项补写长期 record
        # Phase 2B1.2：input_fingerprint 为 content fingerprint（SHA256 multiset，与路径无关）
        assert p["input_fingerprint"] == catalog.content_fingerprint(
            _asset(new_ledger, bid)["files"])
        assert p["input_fingerprint"] != catalog.legacy_path_fingerprint(
            _asset(new_ledger, bid)["files"])


# ---------- 纯逻辑单元测试（不依赖真实数据） ----------

def test_content_fingerprint_path_independent_pure():
    # Phase 2B1.2：fingerprint 只由内容 SHA multiset 决定，路径/顺序无关
    files1 = [{"path": "old/a.epub", "sha256": "s1"}, {"path": "b.txt", "sha256": "s2"}]
    files2 = [{"path": "new/x/b.txt", "sha256": "s2"}, {"path": "other/a.epub", "sha256": "s1"}]
    fp1 = catalog.content_fingerprint(files1)
    assert fp1 == catalog.content_fingerprint(files2)  # 路径与顺序均无关（按 sha 排序）
    assert len(fp1) == 64
    # 任一文件内容变化 → 指纹变化
    assert catalog.content_fingerprint(
        [{"path": "a.epub", "sha256": "s1-new"}, {"path": "b.txt", "sha256": "s2"}]) != fp1
    # 删除来源 → 指纹变化
    assert catalog.content_fingerprint(
        [{"path": "a.epub", "sha256": "s1"}]) != fp1
    # multiset：保留重复 SHA（同一 sha 出现两次 ≠ 出现一次）
    assert catalog.content_fingerprint(
        [{"path": "x", "sha256": "s1"}, {"path": "y", "sha256": "s1"}]) != \
        catalog.content_fingerprint([{"path": "x", "sha256": "s1"}])


def test_source_set_change_marks_stale_pure():
    # K. SOURCE_SET_CHANGE_MARKS_STALE：来源集合变化 → fingerprint 变化；顺序交换 → 相同
    def fp(*hashes):
        return catalog.content_fingerprint(
            [{"path": f"p{i}.epub", "sha256": h} for i, h in enumerate(hashes)])

    fp_ab = fp("A", "B")
    assert fp("A", "C") != fp_ab      # 换来源内容 → 变化
    assert fp("A", "B", "C") != fp_ab  # 新增来源 → 变化
    assert fp("A") != fp_ab           # 删除来源 → 变化
    assert fp("B", "A") == fp_ab     # 顺序交换 → 完全相同
    assert fp("A", "B", "A") != fp_ab  # multiset：重复内容参与指纹


def test_persistent_record_survives_no_workspace_pure():
    # 无 SP metadata，但 ledger 有持久 record 且 fingerprint 匹配 → 保持上次正式状态
    fp = catalog.content_fingerprint([{"path": "a.epub", "sha256": "s1"}])
    prev = {"status": "可用", "evidence": "sourceprepare_metadata",
            "source_sha256": "s1", "input_fingerprint": fp}
    assert catalog.derive_purification(None, None, {"s1"}, fp, prev) == prev


def test_persistent_record_input_changed_pure():
    # 持久 record 的 input fingerprint 已变化 → 需更新，且保留结算时指纹（不丢长期事实）
    fp1 = catalog.content_fingerprint([{"path": "a.epub", "sha256": "s1"}])
    fp2 = catalog.content_fingerprint([{"path": "a.epub", "sha256": "s2"}])
    prev = {"status": "可用", "evidence": "sourceprepare_metadata",
            "source_sha256": "s1", "input_fingerprint": fp1}
    rec = catalog.derive_purification(None, None, {"s2"}, fp2, prev)
    assert rec["status"] == "需更新"
    assert rec["evidence"] == "sourceprepare_record_input_changed"
    assert rec["input_fingerprint"] == fp1
    assert rec["source_sha256"] == "s1"


def test_legacy_fingerprint_migration_pure():
    # L. LEGACY_FINGERPRINT_MIGRATION_PURE：无 SP metadata，prev 为旧 path-based record →
    # 内容一致时保持状态并迁移为 content fingerprint；内容不一致仍判需更新（不误迁移）
    files = [{"path": "01_网络小说/Alpha/a.epub", "sha256": "s1"},
             {"path": "01_网络小说/Alpha/b.txt", "sha256": "s2"}]
    legacy_fp = catalog.legacy_path_fingerprint(files)
    content_fp = catalog.content_fingerprint(files)
    assert legacy_fp != content_fp
    prev = {"status": "可用", "evidence": "bkp_source_snapshot",
            "source_sha256": "s1", "input_fingerprint": legacy_fp}
    rec = catalog.derive_purification(None, None, {"s1", "s2"}, content_fp, prev, legacy_fp)
    assert rec["status"] == "可用"            # 状态不降级
    assert rec["source_sha256"] == "s1"       # source_sha256 保留
    assert rec["input_fingerprint"] == content_fp  # 自动迁移为 content fingerprint
    assert rec["evidence"] == "bkp_source_snapshot"
    # 内容变化（sha 变）→ 即使 path 也变也不得误迁移 → 需更新
    files2 = [{"path": "02_中文文学/Alpha/a.epub", "sha256": "s1-new"},
              {"path": "02_中文文学/Alpha/b.txt", "sha256": "s2"}]
    rec2 = catalog.derive_purification(None, None, {"s1-new", "s2"},
                                       catalog.content_fingerprint(files2), prev,
                                       catalog.legacy_path_fingerprint(files2))
    assert rec2["status"] == "需更新"
    assert rec2["evidence"] == "sourceprepare_record_input_changed"
    assert rec2["input_fingerprint"] == legacy_fp  # 保留结算时指纹

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
              "dir_rel": "02_素材知识库/book_x", "author": "A"}
    assert catalog.derive_knowledge(bkp_ok, {"abc"}) == \
        {"status": "可用", "path": "02_素材知识库/book_x", "source_sha256": "abc"}
    assert catalog.derive_knowledge(bkp_ok, {"def"})["status"] == "需更新"
    assert catalog.derive_knowledge(None, {"abc"}) == {"status": "未开始"}
    not_final = dict(bkp_ok, finalized=False)
    assert catalog.derive_knowledge(not_final, {"abc"}) == {"status": "未开始"}


def test_refresh_preserves_canonical_fields_pure(tmp_path):
    # refresh 必须保留 canonical 字段（含 files[].primary / source_container）
    _build_fake_ledger(tmp_path)
    mat = tmp_path / catalog.MATERIAL_DIR_NAME
    ledger = json.loads((mat / catalog.LEDGER_FILENAME).read_text(encoding="utf-8"))
    new_ledger, report = catalog.refresh_ledger(
        ledger, mat, tmp_path / catalog.DISTILL_DIR_NAME, tmp_path / "06_工作区" / "SourcePrepare")
    assert report["missing"] == []
    assert report["unregistered"] == []
    a = _asset(new_ledger, "book_0001")
    assert [f["primary"] for f in a["files"]] == [True, False]
    assert "source_container" not in a["files"][0]  # 无容器来源不虚构该字段


# ---------- H. SourcePrepare contract（真实目录 discovery + metadata schema） ----------

def _write_sp_metadata(sp_dir: Path, book_id: str, status: str, sha: str,
                       suffix: str = "_Alpha", meta_book_id: str | None = None) -> Path:
    """按 SourcePrepare 正式合同写入 metadata.json：<book_id>_<书名>/metadata.json。"""
    d = sp_dir / f"{book_id}{suffix}"
    d.mkdir(parents=True, exist_ok=True)
    meta = {
        "status": status,
        "book_id": meta_book_id if meta_book_id is not None else book_id,
        "selected_source": {"sha256": sha},
    }
    p = d / "metadata.json"
    p.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return p


def _sp_meta(sp_dir: Path, book_id: str):
    """真实目录 discovery：走 find_sp_metadata 读磁盘，不手搓参数。"""
    return catalog.find_sp_metadata(sp_dir, book_id)


def test_sp_contract_pass_sha_match(tmp_path):
    sp_dir = tmp_path / "06_工作区" / "SourcePrepare"
    sha = "1" * 64
    _write_sp_metadata(sp_dir, "book_0001", "PASS", sha)
    meta = _sp_meta(sp_dir, "book_0001")
    assert meta is not None and meta["status"] == "PASS"
    assert catalog.derive_purification(meta, None, {sha}) == \
        {"status": "可用", "evidence": "sourceprepare_metadata", "source_sha256": sha}


def test_sp_contract_review_sha_match(tmp_path):
    sp_dir = tmp_path / "06_工作区" / "SourcePrepare"
    sha = "2" * 64
    _write_sp_metadata(sp_dir, "book_0001", "REVIEW", sha)
    meta = _sp_meta(sp_dir, "book_0001")
    assert catalog.derive_purification(meta, None, {sha}) == \
        {"status": "需复核", "evidence": "sourceprepare_metadata", "source_sha256": sha}


def test_sp_contract_fail_sha_match(tmp_path):
    sp_dir = tmp_path / "06_工作区" / "SourcePrepare"
    sha = "3" * 64
    _write_sp_metadata(sp_dir, "book_0001", "FAIL", sha)
    meta = _sp_meta(sp_dir, "book_0001")
    assert catalog.derive_purification(meta, None, {sha}) == \
        {"status": "失败", "evidence": "sourceprepare_metadata", "source_sha256": sha}


def test_sp_contract_pass_sha_mismatch(tmp_path):
    sp_dir = tmp_path / "06_工作区" / "SourcePrepare"
    _write_sp_metadata(sp_dir, "book_0001", "PASS", "4" * 64)
    meta = _sp_meta(sp_dir, "book_0001")
    # 即使 status=PASS，source 已不属于当前 asset → 需更新，不标记可用
    assert catalog.derive_purification(meta, None, {"5" * 64}) == \
        {"status": "需更新", "evidence": "sourceprepare_metadata_sha_mismatch"}


def test_sp_contract_fail_no_selected_source(tmp_path):
    # SP 已形成正式结果但无选中来源（FAIL 无可用来源）→ 失败，而非需复核
    sp_dir = tmp_path / "06_工作区" / "SourcePrepare"
    d = sp_dir / "book_0001_Alpha"
    d.mkdir(parents=True)
    (d / "metadata.json").write_text(json.dumps(
        {"status": "FAIL", "book_id": "book_0001", "selected_source": None},
        ensure_ascii=False), encoding="utf-8")
    meta = _sp_meta(sp_dir, "book_0001")
    assert catalog.derive_purification(meta, None, {"abc"}) == \
        {"status": "失败", "evidence": "sourceprepare_metadata"}


def test_sp_contract_book_id_mismatch_reject(tmp_path):
    sp_dir = tmp_path / "06_工作区" / "SourcePrepare"
    _write_sp_metadata(sp_dir, "book_0001", "PASS", "6" * 64, meta_book_id="book_9999")
    with pytest.raises(RuntimeError, match="book_id"):
        catalog.find_sp_metadata(sp_dir, "book_0001")


def test_sp_contract_ambiguity_reject(tmp_path):
    sp_dir = tmp_path / "06_工作区" / "SourcePrepare"
    sha = "7" * 64
    _write_sp_metadata(sp_dir, "book_0001", "PASS", sha, suffix="_Alpha")
    _write_sp_metadata(sp_dir, "book_0001", "REVIEW", sha, suffix="_Beta")
    with pytest.raises(RuntimeError, match="歧义"):
        catalog.find_sp_metadata(sp_dir, "book_0001")


def test_sp_contract_incomplete_metadata(tmp_path):
    sp_dir = tmp_path / "06_工作区" / "SourcePrepare"
    d = sp_dir / "book_0001_Alpha"
    d.mkdir(parents=True)
    (d / "metadata.json").write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
    meta = _sp_meta(sp_dir, "book_0001")
    # 缺 selected_source.sha256 → 不判可用，进入需复核
    assert catalog.derive_purification(meta, None, {"abc"}) == \
        {"status": "需复核", "evidence": "sourceprepare_metadata_incomplete"}


def test_future_enums_pure():
    # Phase 2B 预留枚举：schema 必须允许，但当前 ledger 不产出
    assert "LOOSE_MATERIAL" in catalog.VALID_TYPES
    assert "不适用" in catalog.PURIFICATION_STATUS
    assert "失败" in catalog.PURIFICATION_STATUS
    assert "失败" in catalog.KNOWLEDGE_STATUS
    assert "不适用" in catalog.KNOWLEDGE_STATUS
