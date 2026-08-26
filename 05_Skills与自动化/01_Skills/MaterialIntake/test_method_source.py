# -*- coding: utf-8 -*-
"""MaterialIntake METHOD_SOURCE 类型与生命周期测试（tmp_path，无真实数据依赖）。

覆盖验收：
  1. METHOD_SOURCE 在 canonical ledger 校验中合法；未知类型仍被拒绝；
  2. intake 校验接受 METHOD_SOURCE NEW_ASSET，并把它路由到现有 02_研究资料 区
     （不新增根目录、不影响既有类型）；
  3. catalog refresh：MethodPrepare metadata → purification 推导（可用/需复核/失败）；
     FINALIZED method 知识包 → knowledge 可用；来源指纹过期 → 需更新。
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog  # noqa: E402
import intake  # noqa: E402


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _write_ledger(root: Path, ledger: dict) -> None:
    catalog.write_ledger(ledger, root / catalog.MATERIAL_DIR_NAME / catalog.LEDGER_FILENAME)


def _read_ledger(root: Path) -> dict:
    return json.loads((root / catalog.MATERIAL_DIR_NAME / catalog.LEDGER_FILENAME).read_text(encoding="utf-8"))


def _asset(asset_id="book_9001", name="故事写作方法", content=b"method book content", **extra):
    sha = _sha(content)
    asset = {
        "id": asset_id, "name": name, "type": "METHOD_SOURCE", "author": "作者M",
        "tags": [], "notes": "",
        "files": [{"path": f"02_研究资料/{name}/{name}.txt", "sha256": sha, "primary": True}],
        "purification": {"status": "未处理", "evidence": None},
        "knowledge": {"status": "未开始"},
    }
    asset.update(extra)
    return asset, sha


def _make_repo(tmp_path: Path, assets=None) -> Path:
    root = tmp_path
    mat = root / catalog.MATERIAL_DIR_NAME
    (mat / intake.INBOX_DIR).mkdir(parents=True)
    (mat / "02_研究资料").mkdir(parents=True)
    _write_ledger(root, {"schema_version": "1.0", "assets": assets or [], "containers": []})
    return root


# ---------- 1. ledger 校验接受 METHOD_SOURCE ----------

def test_method_source_valid_in_ledger(tmp_path):
    asset, sha = _asset()
    root = _make_repo(tmp_path, [asset])
    (root / catalog.MATERIAL_DIR_NAME / "02_研究资料" / asset["name"]).mkdir(parents=True)
    (root / catalog.MATERIAL_DIR_NAME / asset["files"][0]["path"]).write_bytes(b"method book content")
    ledger = _read_ledger(root)
    assert catalog.validate_ledger(ledger) == []


def test_unknown_type_still_rejected(tmp_path):
    asset, _ = _asset()
    asset["type"] = "METHOD_BOOK"  # 非法类型
    root = _make_repo(tmp_path, [asset])
    errors = catalog.validate_ledger(_read_ledger(root))
    assert any("非法 type" in e for e in errors)


def test_existing_types_intact(tmp_path):
    for t in ("REFERENCE_WORK", "RESEARCH", "LOOSE_MATERIAL", "NEEDS_REVIEW"):
        assert t in catalog.VALID_TYPES
    assert "METHOD_SOURCE" in catalog.VALID_TYPES


# ---------- 2. intake 校验与路由 ----------

def test_intake_plan_accepts_method_source(tmp_path):
    root = _make_repo(tmp_path)
    inbox = root / catalog.MATERIAL_DIR_NAME / intake.INBOX_DIR
    (inbox / "method_book.txt").write_bytes(b"new method content")
    ledger = _read_ledger(root)
    plan = {"items": [{"action": "NEW_ASSET", "files": ["method_book.txt"],
                       "name": "新方法书", "type": "METHOD_SOURCE"}]}
    assert intake.validate_plan(plan, ledger, inbox) == []


def test_intake_routes_method_source_into_research_area(tmp_path):
    root = _make_repo(tmp_path)
    inbox = root / catalog.MATERIAL_DIR_NAME / intake.INBOX_DIR
    (inbox / "method_book.txt").write_bytes(b"new method content")
    ledger = _read_ledger(root)
    plan = {"items": [{"action": "NEW_ASSET", "files": ["method_book.txt"],
                       "name": "新方法书", "type": "METHOD_SOURCE"}]}
    report = intake.apply_plan(plan, ledger, root)
    assert report["ok"], report["errors"]
    assert report["new_ids"], "METHOD_SOURCE 入库必须产生新 asset"
    new = _read_ledger(root)["assets"][-1]
    assert new["type"] == "METHOD_SOURCE"
    # 物理落入现有 02_研究资料 区（不新增根目录）
    assert new["files"][0]["path"].startswith("02_研究资料/")
    assert (root / catalog.MATERIAL_DIR_NAME / new["files"][0]["path"]).is_file()
    # 语义类型 authority 是台账，不是目录名：目录名不含类型信息
    assert "METHOD_SOURCE" not in new["files"][0]["path"]


def test_intake_rejects_unknown_new_type(tmp_path):
    root = _make_repo(tmp_path)
    inbox = root / catalog.MATERIAL_DIR_NAME / intake.INBOX_DIR
    (inbox / "x.txt").write_bytes(b"x")
    ledger = _read_ledger(root)
    plan = {"items": [{"action": "NEW_ASSET", "files": ["x.txt"], "name": "x", "type": "METHOD"}]}
    errors = intake.validate_plan(plan, ledger, inbox)
    assert errors


# ---------- 3. catalog refresh：MethodPrepare / method 知识包证据 ----------

def _write_mp_metadata(root: Path, asset_id: str, name: str, status: str, sha: str) -> None:
    mp_dir = root / "06_工作区" / "MethodPrepare" / f"{asset_id}_{name}"
    mp_dir.mkdir(parents=True, exist_ok=True)
    (mp_dir / "metadata.json").write_text(json.dumps({
        "skill_version": "method_prepare/v1", "asset_id": asset_id, "asset_name": name,
        "type": "METHOD_SOURCE", "status": status,
        "selected_source": {"path": f"02_研究资料/{name}/{name}.txt", "format": ".txt", "sha256": sha},
        "input_fingerprint": "fp", "content_fingerprint": "cfp",
        "structure_fingerprint": "sfp", "parser": "txt:encoding=utf-8",
        "section_count": 2, "limitations": [],
    }, ensure_ascii=False), encoding="utf-8")


def _write_method_identity(root: Path, asset_id: str, name: str, sha: str,
                           schema_status="FINALIZED_RETRIEVAL_READY") -> None:
    method_dir = root / catalog.DISTILL_DIR_NAME / f"{asset_id}_{name}" / "method"
    method_dir.mkdir(parents=True, exist_ok=True)
    (method_dir / "identity.json").write_text(json.dumps({
        "schema_version": "gowrite_method_knowledge/v1",
        "schema_status": schema_status,
        "source_kind": "method_source", "source_id": asset_id,
        "title": name, "author": "作者M", "maturity": "source_bound",
        "source_snapshot": {"source_sha256": sha, "prepare_fingerprint": "cfp"},
    }, ensure_ascii=False), encoding="utf-8")


def _refresh(root: Path) -> dict:
    assert catalog.refresh_and_render(root, check_only=False) == 0
    return _read_ledger(root)


def test_method_prepare_pass_makes_purification_usable(tmp_path):
    asset, sha = _asset()
    root = _make_repo(tmp_path, [asset])
    (root / catalog.MATERIAL_DIR_NAME / "02_研究资料" / asset["name"]).mkdir(parents=True)
    (root / catalog.MATERIAL_DIR_NAME / asset["files"][0]["path"]).write_bytes(b"method book content")
    _write_mp_metadata(root, asset["id"], asset["name"], "PASS", sha)

    ledger = _refresh(root)
    pur = ledger["assets"][0]["purification"]
    assert pur["status"] == "可用"
    assert pur["evidence"] == "methodprepare_metadata"
    assert pur["source_sha256"] == sha


def test_method_prepare_review_and_fail_statuses(tmp_path):
    for status, expected in (("REVIEW", "需复核"), ("FAIL", "失败")):
        asset, sha = _asset()
        root = _make_repo(tmp_path / status, [asset])
        (root / catalog.MATERIAL_DIR_NAME / "02_研究资料" / asset["name"]).mkdir(parents=True)
        (root / catalog.MATERIAL_DIR_NAME / asset["files"][0]["path"]).write_bytes(b"method book content")
        _write_mp_metadata(root, asset["id"], asset["name"], status, sha)
        ledger = _refresh(root)
        assert ledger["assets"][0]["purification"]["status"] == expected


def test_finalized_method_package_makes_knowledge_callable(tmp_path):
    asset, sha = _asset()
    root = _make_repo(tmp_path, [asset])
    (root / catalog.MATERIAL_DIR_NAME / "02_研究资料" / asset["name"]).mkdir(parents=True)
    (root / catalog.MATERIAL_DIR_NAME / asset["files"][0]["path"]).write_bytes(b"method book content")
    _write_mp_metadata(root, asset["id"], asset["name"], "PASS", sha)
    _write_method_identity(root, asset["id"], asset["name"], sha)

    ledger = _refresh(root)
    know = ledger["assets"][0]["knowledge"]
    assert know["status"] == "可用", know
    assert know["path"] == f"02_素材知识库/{asset['id']}_{asset['name']}"


def test_draft_method_package_not_callable(tmp_path):
    asset, sha = _asset()
    root = _make_repo(tmp_path, [asset])
    (root / catalog.MATERIAL_DIR_NAME / "02_研究资料" / asset["name"]).mkdir(parents=True)
    (root / catalog.MATERIAL_DIR_NAME / asset["files"][0]["path"]).write_bytes(b"method book content")
    _write_method_identity(root, asset["id"], asset["name"], sha, schema_status="DRAFT")

    ledger = _refresh(root)
    assert ledger["assets"][0]["knowledge"]["status"] == "未开始"


def test_stale_source_fingerprint_marks_needs_update(tmp_path):
    asset, sha = _asset()
    root = _make_repo(tmp_path, [asset])
    (root / catalog.MATERIAL_DIR_NAME / "02_研究资料" / asset["name"]).mkdir(parents=True)
    src = root / catalog.MATERIAL_DIR_NAME / asset["files"][0]["path"]
    src.write_bytes(b"method book content")
    _write_mp_metadata(root, asset["id"], asset["name"], "PASS", sha)
    _write_method_identity(root, asset["id"], asset["name"], sha)

    # 来源文件内容变化（旧指纹过期）
    src.write_bytes(b"method book content v2")
    ledger = _refresh(root)
    a = ledger["assets"][0]
    assert a["purification"]["status"] == "需更新"
    assert a["knowledge"]["status"] == "需更新"


if __name__ == "__main__":
    import pytest as _pt
    raise SystemExit(_pt.main([__file__, "-q"]))
