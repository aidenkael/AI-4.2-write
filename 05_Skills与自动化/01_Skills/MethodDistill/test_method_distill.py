# -*- coding: utf-8 -*-
"""MethodDistill 确定性合同测试（tmp_path fixture；无语义模型调用）。

覆盖验收：
  - 拒绝非 PASS 的 MethodPrepare 输入；
  - 拒绝重复卡 id / 空 statement / 非法 method_kind；
  - 拒绝断裂证据引用（不存在分节 / 行号越界 / 格式非法）；
  - 拒绝过期来源指纹（与 MethodPrepare 不一致）；
  - 拒绝仍是模板/空的卡文件；
  - 定稿包可被统一 KnowledgeRetrieve 机械加载并参与混合检索；
  - capability_candidate=true 绝不创建 05_Skills与自动化 下任何文件。
"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import method_distill as md  # noqa: E402

_KR_DIR = Path(__file__).resolve().parent.parent / "KnowledgeRetrieve"
sys.path.insert(0, str(_KR_DIR))


ASSET_ID = "book_9201"
ASSET_NAME = "叙事方法书"
SOURCE_SHA = hashlib.sha256(b"method source").hexdigest()
CONTENT_FP = hashlib.sha256(b"method full content").hexdigest()


def _make_mp_package(root: Path, *, status="PASS", content_fp=CONTENT_FP,
                     source_sha=SOURCE_SHA) -> Path:
    """构造一个 MethodPrepare 包（full.md + sections + structure.json + metadata）。"""
    mp_dir = root / "06_工作区" / "MethodPrepare" / f"{ASSET_ID}_{ASSET_NAME}"
    (mp_dir / "sections").mkdir(parents=True, exist_ok=True)
    (mp_dir / "full.md").write_text(
        "# 开场方法\n开场要先给问题。\n再给行动。\n# 章末钩子方法\n钩子要落在行动上。\n",
        encoding="utf-8", newline="\n")
    (mp_dir / "sections" / "S0001.md").write_text(
        "# 开场方法\n开场要先给问题。\n再给行动。\n", encoding="utf-8", newline="\n")
    (mp_dir / "sections" / "S0002.md").write_text(
        "# 章末钩子方法\n钩子要落在行动上。\n", encoding="utf-8", newline="\n")
    (mp_dir / "structure.json").write_text(json.dumps({
        "heading_structure_known": True, "section_count": 2,
        "sections": [
            {"id": "S0001", "file": "sections/S0001.md", "title": "开场方法", "level": 1,
             "order": 1, "start_line": 1, "line_count": 3, "parent": None},
            {"id": "S0002", "file": "sections/S0002.md", "title": "章末钩子方法", "level": 1,
             "order": 2, "start_line": 4, "line_count": 2, "parent": None},
        ],
    }, ensure_ascii=False), encoding="utf-8")
    (mp_dir / "metadata.json").write_text(json.dumps({
        "skill_version": "method_prepare/v1", "asset_id": ASSET_ID, "asset_name": ASSET_NAME,
        "type": "METHOD_SOURCE", "status": status,
        "selected_source": {"path": f"02_研究资料/{ASSET_NAME}/{ASSET_NAME}.txt",
                            "format": ".txt", "sha256": source_sha},
        "input_fingerprint": "ifp", "content_fingerprint": content_fp,
        "structure_fingerprint": "sfp", "parser": "txt:encoding=utf-8",
        "section_count": 2, "limitations": [],
    }, ensure_ascii=False), encoding="utf-8")
    return mp_dir


def _method_dir(root: Path) -> Path:
    return root / "02_素材知识库" / f"{ASSET_ID}_{ASSET_NAME}" / "method"


def _scaffold(root: Path, mp_dir: Path) -> Path:
    out = _method_dir(root)
    md.prepare_scaffold(mp_dir, out)
    return out


def _write_cards(method_dir: Path, cards_md: str) -> None:
    (method_dir / "knowledge" / "cards.md").write_text(cards_md, encoding="utf-8", newline="\n")


VALID_CARDS = """# 方法卡

## M0001｜开场先给可跟随的问题
- statement: 开场必须先给读者一个可跟随的具体问题，再展开背景。
- method_kind: principle
- dimension: 开场设计
- conditions: 第一场景
- scope: 长篇小说开场
- boundary: 不适用于纯氛围短篇
- confidence: 高
- use_stages: 构思, 写作
- problem_types: 开场乏力
- tags: 开场
- evidence:
  - sections/S0001.md#L2-L3
- capability_candidate: false

## M0002｜章末钩子落在行动上
- statement: 章末钩子应落在人物的行动或决定上，而不是情绪总结。
- method_kind: procedure
- dimension: 叙事节奏
- steps:
  - 找到本章最后一个人物决定
  - 让该决定打开下一场
- checks:
  - 下一场是否因该决定必须发生
- failure_modes:
  - 以情绪总结收尾导致读者动力归零
- scope: 章节结尾
- boundary: 不强制每章悬念
- confidence: 高
- use_stages: 写作, 检查
- problem_types: 章末乏力
- tags: 钩子
- evidence:
  - sections/S0002.md#L2-L2
- capability_candidate: true
"""


# ---------- 输入门 ----------

def test_validate_rejects_non_pass_prepare(tmp_path):
    mp_dir = _make_mp_package(tmp_path, status="REVIEW")
    with pytest.raises(md.MethodDistillError):
        md.validate_input(mp_dir)
    with pytest.raises(md.MethodDistillError):
        md.finalize(mp_dir, _method_dir(tmp_path))


def test_validate_rejects_missing_full_or_sections(tmp_path):
    mp_dir = _make_mp_package(tmp_path)
    (mp_dir / "full.md").unlink()
    with pytest.raises(md.MethodDistillError):
        md.validate_input(mp_dir)


# ---------- prepare 脚手架 ----------

def test_prepare_scaffold_is_draft_and_idempotent(tmp_path):
    mp_dir = _make_mp_package(tmp_path)
    out = _scaffold(tmp_path, mp_dir)
    identity = json.loads((out / "identity.json").read_text(encoding="utf-8"))
    assert identity["schema_version"] == "gowrite_method_knowledge/v1"
    assert identity["schema_status"] == "DRAFT"
    assert identity["source_kind"] == "method_source"
    assert identity["source_id"] == ASSET_ID
    assert identity["maturity"] == "source_bound"
    assert identity["source_snapshot"]["source_sha256"] == SOURCE_SHA
    assert (out / "method_profile.md").exists()
    assert (out / "evidence.md").exists()
    assert (out / "knowledge" / "cards.md").exists()


# ---------- finalize 定稿 ----------

def test_finalize_success_marks_retrieval_ready(tmp_path):
    mp_dir = _make_mp_package(tmp_path)
    out = _scaffold(tmp_path, mp_dir)
    _write_cards(out, VALID_CARDS)
    manifest = md.finalize(mp_dir, out)
    assert manifest["status"] == "FINALIZED"
    assert manifest["card_count"] == 2
    assert manifest["capability_candidate_count"] == 1
    identity = json.loads((out / "identity.json").read_text(encoding="utf-8"))
    assert identity["schema_status"] == "FINALIZED_RETRIEVAL_READY"
    assert (out / "distill_manifest.json").exists()


def test_finalize_rejects_template_cards(tmp_path):
    mp_dir = _make_mp_package(tmp_path)
    out = _scaffold(tmp_path, mp_dir)
    with pytest.raises(md.MethodDistillError, match="模板|空"):
        md.finalize(mp_dir, out)


def test_finalize_rejects_duplicate_card_ids(tmp_path):
    mp_dir = _make_mp_package(tmp_path)
    out = _scaffold(tmp_path, mp_dir)
    dup = VALID_CARDS.replace("## M0002｜", "## M0001｜")
    _write_cards(out, dup)
    with pytest.raises(md.MethodDistillError, match="重复"):
        md.finalize(mp_dir, out)


def test_finalize_rejects_empty_statement(tmp_path):
    mp_dir = _make_mp_package(tmp_path)
    out = _scaffold(tmp_path, mp_dir)
    _write_cards(out, VALID_CARDS.replace(
        "- statement: 开场必须先给读者一个可跟随的具体问题，再展开背景。", "- statement:"))
    with pytest.raises(md.MethodDistillError, match="statement"):
        md.finalize(mp_dir, out)


def test_finalize_rejects_invalid_method_kind(tmp_path):
    mp_dir = _make_mp_package(tmp_path)
    out = _scaffold(tmp_path, mp_dir)
    _write_cards(out, VALID_CARDS.replace("- method_kind: principle", "- method_kind: style"))
    with pytest.raises(md.MethodDistillError, match="method_kind"):
        md.finalize(mp_dir, out)


def test_finalize_rejects_broken_evidence_refs(tmp_path):
    cases = [
        "sections/S9999.md#L1-L2",          # 不存在的分节
        "sections/S0001.md#L90-L99",        # 行号越界
        "chapters/0001.md#L1",              # 非法格式（必须指向 MethodPrepare sections）
    ]
    for bad_ref in cases:
        case_root = tmp_path / hashlib.md5(bad_ref.encode()).hexdigest()
        mp_dir = _make_mp_package(case_root)
        out = _scaffold(case_root, mp_dir)
        _write_cards(out, VALID_CARDS.replace("sections/S0001.md#L2-L3", bad_ref))
        with pytest.raises(md.MethodDistillError):
            md.finalize(mp_dir, out)


def test_finalize_rejects_stale_source_fingerprint(tmp_path):
    mp_dir = _make_mp_package(tmp_path)
    out = _scaffold(tmp_path, mp_dir)
    _write_cards(out, VALID_CARDS)
    # 来源内容指纹过期（MethodPrepare 重跑后内容变化）
    meta = json.loads((mp_dir / "metadata.json").read_text(encoding="utf-8"))
    meta["content_fingerprint"] = hashlib.sha256(b"changed").hexdigest()
    (mp_dir / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(md.MethodDistillError, match="指纹过期"):
        md.finalize(mp_dir, out)


def test_finalize_rejects_stale_source_sha(tmp_path):
    mp_dir = _make_mp_package(tmp_path)
    out = _scaffold(tmp_path, mp_dir)
    _write_cards(out, VALID_CARDS)
    meta = json.loads((mp_dir / "metadata.json").read_text(encoding="utf-8"))
    meta["selected_source"]["sha256"] = hashlib.sha256(b"other source").hexdigest()
    (mp_dir / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(md.MethodDistillError, match="指纹过期"):
        md.finalize(mp_dir, out)


# ---------- capability_candidate 绝不产生 05 侧文件 ----------

def test_capability_candidate_never_writes_skill_files(tmp_path):
    mp_dir = _make_mp_package(tmp_path)
    out = _scaffold(tmp_path, mp_dir)
    _write_cards(out, VALID_CARDS)  # M0002 capability_candidate=true
    md.finalize(mp_dir, out)
    created = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert all("05_Skills与自动化" not in p.parts for p in created)
    # 产物只落在 method/ 包内
    for p in created:
        if _method_dir(tmp_path) in p.parents:
            continue
        assert "MethodPrepare" in p.parts or p.name == "metadata.json" or "06_工作区" in p.parts


# ---------- 定稿包可被统一 KnowledgeRetrieve 加载（混合检索证明） ----------

def test_finalized_package_retrievable_mixed_with_bkp_and_validated(tmp_path):
    mp_dir = _make_mp_package(tmp_path)
    out = _scaffold(tmp_path, mp_dir)
    _write_cards(out, VALID_CARDS)
    md.finalize(mp_dir, out)

    # 参考作品 BKP（现有格式）
    bkp = tmp_path / "02_素材知识库" / "book_9001_参考小说" / "bkp"
    (bkp / "knowledge").mkdir(parents=True)
    (bkp / "identity.json").write_text(json.dumps({
        "schema_status": "FINALIZED",
        "book": {"book_id": "book_9001", "title": "参考小说", "author": "甲"},
        "source_snapshot": {"source_sha256": "0" * 64}, "bkp_contents": {},
    }, ensure_ascii=False), encoding="utf-8")
    (bkp / "knowledge" / "cards.md").write_text(
        "## K001｜开场观察卡\n- knowledge_level: Work-specific Pattern\n- dimension: 开场设计\n"
        "- statement: 该参考作品的开场先给可跟随的问题，再给背景。\n- confidence: 高\n"
        "- evidence:\n  - chapters/0001.md#L3\n", encoding="utf-8")

    # 已验证知识包（04）
    val = tmp_path / "04_写作知识库" / "pkg_opening"
    (val / "knowledge").mkdir(parents=True)
    (val / "identity.json").write_text(json.dumps({
        "schema_version": "gowrite_validated_knowledge/v1",
        "schema_status": "FINALIZED_VALIDATED",
        "source_kind": "validated_knowledge", "source_id": "pkg_opening",
        "title": "开场检查单", "maturity": "validated", "provenance": [],
    }, ensure_ascii=False), encoding="utf-8")
    (val / "knowledge" / "cards.md").write_text(
        "## V0001｜开场问题验证规则\n- statement: 多作品验证：开场先给可跟随的问题。\n"
        "- dimension: 开场设计\n- confidence: 高\n- evidence:\n  - validation.md#L1-L2\n",
        encoding="utf-8")

    # 统一 KnowledgeRetrieve：一次 retrieve 得到三类来源混合包
    import importlib.util
    spec = importlib.util.spec_from_file_location("kr_runtime_for_md_test", _KR_DIR / "run.py")
    kr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(kr)
    kr.BASE_DIR = str(tmp_path)
    kr.reset_catalog()
    try:
        pkg = kr.retrieve("开场怎样先给可跟随的问题", top_k=15)
        kinds = {h.source_kind for h in pkg.hits}
        assert kinds == {"reference_bkp", "method_source", "validated_knowledge"}, \
            [h.selection_ref for h in pkg.hits]
        refs = {h.selection_ref for h in pkg.hits}
        assert f"method_source/{ASSET_ID}/M0001" in refs
        assert f"method_source/{ASSET_ID}/M0002" in refs or len(refs) >= 3
        method_hit = next(h for h in pkg.hits if h.source_kind == "method_source")
        assert method_hit.maturity == "source_bound"
        assert method_hit.source_title == ASSET_NAME
    finally:
        kr.reset_catalog()


def test_draft_method_package_not_retrievable(tmp_path):
    mp_dir = _make_mp_package(tmp_path)
    out = _scaffold(tmp_path, mp_dir)  # 仅脚手架（DRAFT），未 finalize
    _write_cards(out, VALID_CARDS)

    import importlib.util
    spec = importlib.util.spec_from_file_location("kr_runtime_for_md_test2", _KR_DIR / "run.py")
    kr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(kr)
    kr.BASE_DIR = str(tmp_path)
    kr.reset_catalog()
    try:
        sources = kr.discover_sources(str(tmp_path))
        assert sources == [], "DRAFT 方法包不得进入可检索目录"
    finally:
        kr.reset_catalog()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
