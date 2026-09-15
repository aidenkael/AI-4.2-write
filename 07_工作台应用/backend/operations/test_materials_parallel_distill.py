# -*- coding: utf-8 -*-
"""并行 BookDistill 的发布边界 / 检索面 / 清理不变量 focused tests（任务书 §14）。

覆盖检查点：
12. supporting contract 不接受 raw/unconverged findings（只 curated 进入，raw 绝不泄漏）；
16. formal publication allowlist 仍排除全部 process artifacts（_work/leases/notes/convergence）；
17. KnowledgeRetrieve 默认 canonical cards surface 不变（cards.md 是进入 02 的权威层）；
18. cleanup 后 book_0012 SourcePrepare 完整，且不可写作/不可检索。
零模型、零网络、零真实书籍蒸馏。
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from operations import materials  # noqa: E402


def _build_stage(root: Path) -> Path:
    """A staging dir mixing formal allowlist artifacts with every process artifact."""
    stage = root / "stage"
    stage.mkdir(parents=True)
    # 正式 allowlist 根文件
    (stage / "model.md").write_text("# model\n正式模型\n", encoding="utf-8")
    (stage / "distill_manifest.json").write_text(
        json.dumps({"source_snapshot": {"book_id": "book_9001"}}), encoding="utf-8")
    (stage / "BKP_ACCEPTANCE_REPORT.md").write_text("# acceptance\n", encoding="utf-8")
    # 正式 bkp 子树（curated）
    (stage / "bkp" / "knowledge").mkdir(parents=True)
    (stage / "bkp" / "identity.json").write_text(json.dumps({"book": {"book_id": "book_9001"}}), encoding="utf-8")
    (stage / "bkp" / "knowledge" / "cards.md").write_text("## K001｜卡\nCANONICAL_CARD\n", encoding="utf-8")
    (stage / "bkp" / "knowledge" / "supporting.md").write_text(
        "## 已收敛 supporting\nCURATED_SUPPORTING_LINE\n", encoding="utf-8")
    # 过程工件（绝不进入 02）：_work / leases / batch notes / temp notes / convergence
    (stage / "_work" / "batch_notes" / ".tmp").mkdir(parents=True)
    (stage / "_work" / "reading_manifest.json").write_text("{}", encoding="utf-8")
    (stage / "_work" / "reading_ledger.json").write_text("{}", encoding="utf-8")
    (stage / "_work" / "convergence_state.md").write_text("# rolling\nRAW_CONVERGENCE\n", encoding="utf-8")
    (stage / "_work" / "batch_notes" / "B0001.md").write_text("RAW_BATCH_NOTE_FINDING_LEAK\n", encoding="utf-8")
    (stage / "_work" / "batch_notes" / ".tmp" / "B0001.tok.md").write_text("RAW_TEMP_NOTE\n", encoding="utf-8")
    (stage / "discovery").mkdir()
    (stage / "discovery" / "raw.md").write_text("RAW_DISCOVERY\n", encoding="utf-8")
    (stage / "evidence").mkdir()
    (stage / "evidence" / "ch_0001.md").write_text("RAW_EVIDENCE\n", encoding="utf-8")
    (stage / "bkp_prototype" / "knowledge").mkdir(parents=True)
    (stage / "bkp_prototype" / "knowledge" / "cards.md").write_text("PROTO\n", encoding="utf-8")
    (stage / "deepdive").mkdir()
    (stage / "deepdive" / "dd_x.md").write_text("DD\n", encoding="utf-8")
    (stage / "book_profile_initial.md").write_text("INITIAL\n", encoding="utf-8")
    return stage


def test_point16_formal_allowlist_excludes_all_process_artifacts(tmp_path):
    """检查点 16：formal publication allowlist 仍排除全部 process artifacts。"""
    stage = _build_stage(tmp_path)
    cand = tmp_path / "cand"
    res = materials._build_reference_formal_candidate(stage, cand)
    assert res["ok"], res["missing"]
    copied = set(res["copied"])
    assert {"model.md", "distill_manifest.json", "BKP_ACCEPTANCE_REPORT.md"} <= copied
    assert "bkp/identity.json" in copied and "bkp/knowledge/cards.md" in copied
    for bad in ("_work", "batch_notes", "convergence_state", "discovery", "evidence",
                "bkp_prototype", "deepdive", "book_profile_initial", ".tmp",
                "reading_manifest", "reading_ledger"):
        assert not any(bad in c for c in copied), f"process artifact leaked into allowlist: {bad}"
    on_disk = [p.relative_to(cand).as_posix() for p in cand.rglob("*") if p.is_file()]
    assert not any(f.startswith("_work") or "batch_notes" in f or "convergence_state" in f
                   or f.startswith("discovery") or f.startswith("evidence")
                   or "bkp_prototype" in f or f.startswith("deepdive") for f in on_disk), on_disk


def test_point12_supporting_is_curated_not_raw_dump(tmp_path):
    """检查点 12：supporting 只承接 curated 收敛结果；raw findings 绝不泄漏进 02。"""
    stage = _build_stage(tmp_path)
    cand = tmp_path / "cand"
    materials._build_reference_formal_candidate(stage, cand)
    sup = (cand / "bkp" / "knowledge" / "supporting.md").read_text(encoding="utf-8")
    assert "CURATED_SUPPORTING_LINE" in sup
    blob = "\n".join(p.read_text(encoding="utf-8") for p in cand.rglob("*") if p.is_file())
    for leak in ("RAW_BATCH_NOTE_FINDING_LEAK", "RAW_CONVERGENCE", "RAW_TEMP_NOTE",
                 "RAW_DISCOVERY", "RAW_EVIDENCE"):
        assert leak not in blob, f"raw/unconverged finding leaked into formal 02: {leak}"


def test_point17_canonical_cards_surface_reaches_02(tmp_path):
    """检查点 17：默认检索权威层 cards.md 进入 02；supporting 为独立非默认层；无 raw notes。"""
    stage = _build_stage(tmp_path)
    cand = tmp_path / "cand"
    materials._build_reference_formal_candidate(stage, cand)
    assert (cand / "bkp" / "knowledge" / "cards.md").is_file()
    assert "CANONICAL_CARD" in (cand / "bkp" / "knowledge" / "cards.md").read_text(encoding="utf-8")
    assert (cand / "bkp" / "knowledge" / "supporting.md").is_file()
    assert not (cand / "_work").exists()


def test_point18_book_0012_cleanup_invariants():
    """检查点 18：cleanup 后 book_0012 SourcePrepare 完整，且不可写作/不可检索。

    依赖 Local Only 的 06 SourcePrepare；缺失时（如 CI）跳过。
    """
    root = materials.get_repo_root()
    sp_root = root / "06_工作区" / "SourcePrepare"
    sp_dirs = sorted(sp_root.glob("book_0012_*")) if sp_root.is_dir() else []
    if not sp_dirs:
        pytest.skip("本地无 book_0012 SourcePrepare（Local Only），跳过真实状态守卫")
    sp = sp_dirs[0]
    meta = json.loads((sp / "metadata.json").read_text(encoding="utf-8"))
    # SourcePrepare 完整：PASS / 0.4.0 / 章节数精确一致。
    assert meta.get("status") == "PASS"
    assert meta.get("skill_version") == "0.4.0"
    chapters = [p for p in (sp / "chapters").glob("*.md")
                if p.name[:4].isdigit() and not p.name.startswith("0000_")]
    assert len(chapters) == int(meta.get("chapter_files"))
    # 02 无该中止运行产生的正式包。
    assert not list((root / "02_素材知识库").glob("book_0012_*"))
    # 不可检索（KnowledgeRetrieve 唯一 loader 发现不到该来源）→ 亦即不可写作。
    assert materials._knowledge_is_discoverable({"id": "book_0012", "type": "REFERENCE_WORK"}) is False
