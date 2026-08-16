# -*- coding: utf-8 -*-
"""BookDistill settlement contract tests（Phase 2B2 第 51 节）。

FINALIZED settlement output allowlist 验证：
  - 02_原著蒸馏 subtree（bkp / knowledge / meta）→ 允许
  - 01_原始素材 三份 material state files → 允许
  - 01 原著全文（raw 源文件）→ 禁止
  - 06_工作区（SP/BD 工作副本）→ 禁止
  - 其他作品目录 / 伪装前缀文件 → 禁止

运行：
  python -m pytest tests/test_settlement_contract.py -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".." / "scripts"))
import settlement_contract as sc  # noqa: E402


# ---------- 允许面 ----------

def test_distill_subtree_allowed():
    assert sc.is_settlement_allowed("02_原著蒸馏/book_0001_Alpha/bkp/identity.json") is True
    assert sc.is_settlement_allowed("02_原著蒸馏/book_0001_Alpha/knowledge/世界观.md") is True
    assert sc.is_settlement_allowed("02_原著蒸馏/book_0001_Alpha/metadata.json") is True


def test_material_state_files_allowed():
    for rel in ("01_原始素材/素材资产.json",
                "01_原始素材/素材清单.csv",
                "01_原始素材/素材总索引.md"):
        assert sc.is_settlement_allowed(rel) is True
        assert sc.is_settlement_never_stage(rel) is False


# ---------- 禁止面 ----------

def test_raw_source_never_allowed():
    rel = "01_原始素材/01_网络小说/Alpha/Alpha.epub"
    assert sc.is_settlement_allowed(rel) is False
    assert sc.is_settlement_never_stage(rel) is True


def test_workspace_never_allowed():
    rel = "06_工作区/SourcePrepare/book_0001_Alpha/full.md"
    assert sc.is_settlement_allowed(rel) is False
    assert sc.is_settlement_never_stage(rel) is True


def test_other_work_dirs_not_allowed():
    assert sc.is_settlement_allowed("03_作品工程/00_历史作者资料/x.md") is False
    assert sc.is_settlement_allowed("04_写作知识库/01_写作方法/y.md") is False
    assert sc.is_settlement_allowed("99_归档/z.md") is False


def test_spoofed_prefix_not_allowed():
    # 伪装文件名（前缀相似但非精确 metadata）不得放行
    assert sc.is_settlement_allowed("01_原始素材/素材资产.json.backup") is False
    assert sc.is_settlement_allowed("01_原始素材/素材资产.json2") is False
    # 相似目录名不得放行（非 02_原著蒸馏 前缀）
    assert sc.is_settlement_allowed("02_原著蒸馏x/book_0001/x.md") is False


def test_mixed_allowed_and_never_stage_consistency():
    # 允许面与 never-stage 不重叠：允许的都必须能通过第二道过滤
    for rel in ("02_原著蒸馏/book_0001_Alpha/bkp/identity.json",
                "01_原始素材/素材资产.json"):
        assert sc.is_settlement_allowed(rel) is True
        assert sc.is_settlement_never_stage(rel) is False
