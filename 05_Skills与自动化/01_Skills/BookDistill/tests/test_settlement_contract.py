# -*- coding: utf-8 -*-
"""BookDistill settlement contract tests（Phase 2B2 第 51 节 + 2B2.1 动态收窄）。

FINALIZED settlement output allowlist 验证（BD_SETTLEMENT_CURRENT_BOOK_ONLY）：
  - 当前作品 subtree（02_原著蒸馏/<book_id>_<work_name>/ 下 bkp / knowledge / meta）→ 允许
  - 01_原始素材 三份 material state files → 允许
  - sibling 作品目录（book_0002_Beta）→ 禁止
  - 伪造前缀（book_00010_Fake / book_0001_Alpha_evil）→ 禁止
  - 01 原著全文（raw 源文件）→ 禁止
  - 06_工作区（SP/BD 工作副本）→ 禁止
  - 其他作品目录 / 伪装前缀文件 → 禁止
  - 非法 book_id / 绝对路径 / .. / 非 02_原著蒸馏 路径 → ValueError

运行：
  python -m pytest tests/test_settlement_contract.py -v
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / ".." / "scripts"))
import settlement_contract as sc  # noqa: E402


def _al() -> list[str]:
    """当前 settlement target：book_0001_Alpha。"""
    return sc.build_settlement_allowlist("book_0001", "Alpha")


def _al_dir() -> list[str]:
    """从蒸馏目录相对路径构建（同语义，验证 from_dir 路径）。"""
    return sc.build_settlement_allowlist_from_dir("02_原著蒸馏/book_0001_Alpha")


# ---------- 允许面 ----------

def test_current_book_subtree_allowed():
    for al in (_al(), _al_dir()):
        assert sc.is_settlement_allowed("02_原著蒸馏/book_0001_Alpha/bkp/identity.json", al) is True
        assert sc.is_settlement_allowed("02_原著蒸馏/book_0001_Alpha/knowledge/世界观.md", al) is True
        assert sc.is_settlement_allowed("02_原著蒸馏/book_0001_Alpha/metadata.json", al) is True


def test_material_state_files_allowed():
    for al in (_al(), _al_dir()):
        for rel in ("01_原始素材/素材资产.json",
                    "01_原始素材/素材清单.csv",
                    "01_原始素材/素材总索引.md"):
            assert sc.is_settlement_allowed(rel, al) is True
            assert sc.is_settlement_never_stage(rel) is False


def test_allowlist_shape_has_no_whole_distill_dir():
    """allowlist 绝不含整个 02_原著蒸馏/ 目录授权。"""
    for al in (_al(), _al_dir()):
        assert "02_原著蒸馏/" not in al
        assert "02_原著蒸馏" not in al
        assert any(a.startswith("02_原著蒸馏/") for a in al)  # 但含当前作品前缀


# ---------- 禁止面 ----------

def test_sibling_book_not_allowed():
    """BD_SIBLING_BOOK_CHANGE_UNEXPECTED：sibling 蒸馏目录绝不放行。"""
    for al in (_al(), _al_dir()):
        assert sc.is_settlement_allowed("02_原著蒸馏/book_0002_Beta/bkp/identity.json", al) is False
        assert sc.is_settlement_allowed("02_原著蒸馏/book_0002_Beta/metadata.json", al) is False


def test_prefix_spoof_not_allowed():
    """伪造前缀（book_00010 / book_0001_Alpha_evil）不得放行。"""
    for al in (_al(), _al_dir()):
        assert sc.is_settlement_allowed("02_原著蒸馏/book_00010_Fake/bkp/identity.json", al) is False
        assert sc.is_settlement_allowed("02_原著蒸馏/book_0001_Alpha_evil/bkp/x.md", al) is False


def test_whole_distill_dir_default_not_allowed():
    """模块默认 allowlist（不带参数）不含任何蒸馏目录授权。"""
    assert sc.is_settlement_allowed("02_原著蒸馏/book_0001_Alpha/bkp/identity.json") is False
    assert sc.is_settlement_allowed("02_原著蒸馏/anything.md") is False


def test_raw_source_never_allowed():
    rel = "01_原始素材/01_网络小说/Alpha/Alpha.epub"
    assert sc.is_settlement_allowed(rel, _al()) is False
    assert sc.is_settlement_never_stage(rel) is True


def test_workspace_never_allowed():
    rel = "06_工作区/SourcePrepare/book_0001_Alpha/full.md"
    assert sc.is_settlement_allowed(rel, _al()) is False
    assert sc.is_settlement_never_stage(rel) is True


def test_other_work_dirs_not_allowed():
    for rel in ("03_作品工程/00_历史作者资料/x.md",
                "04_写作知识库/01_写作方法/y.md",
                "99_归档/z.md"):
        assert sc.is_settlement_allowed(rel, _al()) is False


def test_spoofed_prefix_files_not_allowed():
    # 伪装文件名（前缀相似但非精确 metadata）不得放行
    assert sc.is_settlement_allowed("01_原始素材/素材资产.json.backup", _al()) is False
    assert sc.is_settlement_allowed("01_原始素材/素材资产.json2", _al()) is False
    # 相似目录名不得放行（非 02_原著蒸馏 前缀）
    assert sc.is_settlement_allowed("02_原著蒸馏x/book_0001/x.md", _al()) is False


def test_mixed_allowed_and_never_stage_consistency():
    # 允许面与 never-stage 不重叠：允许的都必须能通过第二道过滤
    for al in (_al(), _al_dir()):
        for rel in ("02_原著蒸馏/book_0001_Alpha/bkp/identity.json",
                    "01_原始素材/素材资产.json"):
            assert sc.is_settlement_allowed(rel, al) is True
            assert sc.is_settlement_never_stage(rel) is False


# ---------- path validation（第 13 节） ----------

def test_invalid_book_id_rejected():
    for bad in ("book_1", "book_12345", "book_x001", "1", "alpha", "BOOK_0001"):
        with pytest.raises(ValueError):
            sc.build_settlement_allowlist(bad, "Alpha")


def test_work_name_injection_rejected():
    # .. / 绝对路径 / 路径分隔符 注入 → sanitize 后不再逃逸 02_原著蒸馏
    al = sc.build_settlement_allowlist("book_0001", "../../evil")
    prefix = next(a for a in al if a.startswith("02_原著蒸馏/"))
    assert prefix.startswith("02_原著蒸馏/book_0001_")
    assert ".." not in prefix
    # 结构恰为 02_原著蒸馏/<book_id>_<safe>/（2 个 /：目录层级 + 结尾），无跨目录注入
    assert prefix.count("/") == 2
    # 绝对路径 work_name 同样被 sanitize
    al2 = sc.build_settlement_allowlist("book_0001", "C:/Windows/evil")
    assert any(a.startswith("02_原著蒸馏/book_0001_") for a in al2)


def test_from_dir_path_validation():
    # 绝对路径 / .. / 非 02_原著蒸馏 / 多层 / 非法 book_id 前缀 → ValueError
    for bad in ("/02_原著蒸馏/book_0001_Alpha",
                "02_原著蒸馏/../book_0001_Alpha",
                "03_作品工程/book_0001_Alpha",
                "02_原著蒸馏/book_0001_Alpha/deep",
                "02_原著蒸馏/book_1_Alpha",
                "02_原著蒸馏/alpha_Alpha"):
        with pytest.raises(ValueError):
            sc.build_settlement_allowlist_from_dir(bad)
    # 合法输入可正常构建
    al = sc.build_settlement_allowlist_from_dir("02_原著蒸馏/book_0035_长安十二时辰")
    assert "02_原著蒸馏/book_0035_长安十二时辰/" in al
    assert len(al) == 4
