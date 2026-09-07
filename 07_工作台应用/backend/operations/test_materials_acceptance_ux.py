# -*- coding: utf-8 -*-
"""Focused author-acceptance regressions for Materials diagnostics and folders."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from operations import materials  # noqa: E402


def _asset(asset_id="book_0001", *, asset_type="REFERENCE_WORK", path="01_原著/样例/样例.epub",
           purification="未处理", knowledge="未开始", sha="a" * 64):
    return {
        "id": asset_id, "name": "样例", "type": asset_type, "author": "",
        "files": [{"path": path, "sha256": sha, "primary": True}],
        "purification": {"status": purification}, "knowledge": {"status": knowledge},
    }


@pytest.fixture()
def root(tmp_path, monkeypatch):
    repo = tmp_path / "root"
    (repo / "01_原始素材").mkdir(parents=True)
    (repo / "02_素材知识库").mkdir()
    (repo / "06_工作区" / "SourcePrepare").mkdir(parents=True)
    (repo / "06_工作区" / "MethodPrepare").mkdir(parents=True)
    monkeypatch.setattr(materials, "get_repo_root", lambda: repo)
    monkeypatch.setattr(materials, "_knowledge_is_discoverable", lambda asset: True)
    return repo


def _write_ledger(root: Path, assets):
    (root / "01_原始素材" / "素材资产.json").write_text(json.dumps({
        "schema_version": "1.0", "assets": assets, "containers": [],
    }, ensure_ascii=False), encoding="utf-8")


def _prepare(root: Path, asset, *, status="PASS", metadata=None, complete=True):
    branch = "MethodPrepare" if asset["type"] == "METHOD_SOURCE" else "SourcePrepare"
    required = "sections" if asset["type"] == "METHOD_SOURCE" else "chapters"
    package = root / "06_工作区" / branch / f'{asset["id"]}_{asset["name"]}'
    package.mkdir()
    (package / "full.md").write_text("正文", encoding="utf-8")
    if complete:
        (package / required).mkdir()
    payload = metadata if metadata is not None else {
        "status": status, "selected_source": {"sha256": asset["files"][0]["sha256"]},
    }
    (package / "metadata.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return package


def test_prepare_reason_projects_real_structured_warning(root):
    asset = _asset(purification="需复核")
    _prepare(root, asset, status="REVIEW", metadata={
        "status": "REVIEW", "selected_source": {"sha256": "a" * 64},
        "candidates": [{"warnings": ["未可靠识别章节边界（需 ≥ 3 个）"]}],
    })
    reason = materials._prepare_package_current(asset)["reason"]
    assert reason == "未识别到足够的正文或章节。"


def test_method_prepare_reason_uses_limitations(root):
    asset = _asset(asset_type="METHOD_SOURCE", path="02_技巧类/样例/样例.pdf", purification="需复核")
    _prepare(root, asset, status="REVIEW", metadata={
        "status": "REVIEW", "selected_source": {"sha256": "a" * 64},
        "limitations": ["conversion_unavailable: PDF 无可用文本层（不做 OCR）"],
    })
    assert materials._prepare_package_current(asset)["reason"] == "PDF 没有可读取的文字层。"


def test_prepare_stale_and_incomplete_reasons(root):
    stale = _asset()
    _prepare(root, stale, metadata={"status": "PASS", "selected_source": {"sha256": "b" * 64}})
    assert materials._prepare_package_current(stale)["reason"] == "提纯结果与当前来源文件不一致，需要重新提纯。"

    incomplete = _asset("book_0002", path="01_原著/缺页/缺页.epub")
    _prepare(root, incomplete, complete=False)
    assert materials._prepare_package_current(incomplete)["reason"] == "提纯结果文件不完整。"


def test_historical_no_detail_fallback_never_leaks_internal_text(root):
    asset = _asset(purification="需复核")
    package = _prepare(root, asset, status="REVIEW", metadata={
        "status": "REVIEW", "notes": ["traceback C:\\private PRECHECK DIRTY_WORKTREE deadbeef"],
    })
    (package / "conversion_report.md").write_text("旧记录没有可识别说明", encoding="utf-8")
    reason = materials._prepare_package_current(asset)["reason"]
    assert reason == "历史提纯记录未保存具体失败原因，请重新提纯以生成新的检查结果。"
    for forbidden in ("traceback", "private", "PRECHECK", "DIRTY_WORKTREE", "deadbeef"):
        assert forbidden not in reason


def test_historical_report_is_used_only_for_known_reason_sections(root):
    asset = _asset(purification="需复核")
    package = _prepare(root, asset, status="REVIEW", metadata={"status": "REVIEW"})
    (package / "conversion_report.md").write_text(
        "- Pandoc：转换器存在\n## 需要注意\n- PDF 无可用文本层，或缺少转换工具\n",
        encoding="utf-8",
    )
    assert materials._prepare_package_current(asset)["reason"] == "PDF 没有可读取的文字层。"


def test_open_folder_routes_by_real_stage(root, monkeypatch):
    new = _asset("book_new", path="01_原著/新增/新增.epub")
    reference = _asset("book_ref", path="01_原著/原著/原著.epub", purification="可用")
    method = _asset("book_method", asset_type="METHOD_SOURCE", path="02_技巧类/方法/方法.txt", purification="可用")
    writing = _asset("book_write", path="01_原著/写作/写作.epub", purification="可用", knowledge="可用")
    other = _asset("book_other", asset_type="LOOSE_MATERIAL", path="03_其他/其他/其他.pdf", purification="不适用")
    assets = [new, reference, method, writing, other]
    for asset in assets:
        source = root / "01_原始素材" / asset["files"][0]["path"]
        source.parent.mkdir(parents=True)
        source.write_bytes(b"source")
    ref_package = _prepare(root, reference)
    method_package = _prepare(root, method)
    writing_package = root / "02_素材知识库" / "book_write_写作"
    writing_package.mkdir()
    _write_ledger(root, assets)
    opened = []
    monkeypatch.setattr(materials, "_launch_folder", lambda path: opened.append(path))

    for asset in assets:
        assert materials.open_material_folder(asset["id"])["opened"] is True

    assert opened == [
        (root / "01_原始素材" / "01_原著" / "新增").resolve(),
        ref_package.resolve(), method_package.resolve(), writing_package.resolve(),
        (root / "01_原始素材" / "03_其他" / "其他").resolve(),
    ]


def test_open_folder_missing_and_escape_are_rejected(root, tmp_path, monkeypatch):
    monkeypatch.setattr(materials, "_launch_folder", lambda path: pytest.fail("Explorer must not launch"))
    missing = _asset("book_missing", path="01_原著/缺失/缺失.epub")
    _write_ledger(root, [missing])
    with pytest.raises(materials.MaterialsError, match="找不到这份资料对应的文件夹"):
        materials.open_material_folder("book_missing")

    outside = tmp_path / "outside" / "escape.epub"
    outside.parent.mkdir()
    outside.write_bytes(b"outside")
    escaped = _asset("book_escape", path="../../outside/escape.epub")
    _write_ledger(root, [escaped])
    with pytest.raises(materials.MaterialsError, match="找不到这份资料对应的文件夹"):
        materials.open_material_folder("book_escape")
