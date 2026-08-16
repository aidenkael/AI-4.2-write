# -*- coding: utf-8 -*-
"""BookDistill settlement contract（Phase 2B2 第 35-38/51 节 + 2B2.1 动态收窄）。

settlement 是 Agent 在 BKP FINALIZED + 全部验证通过后执行一次的收尾动作
（不改 book_distill.py runtime）：catalog refresh → knowledge 自动可用 →
CSV/MD 刷新 → post_action SAFE_COMMIT_PUSH。

本模块只定义 contract 常量与校验函数，供测试与 Agent 引用。

FINALIZED settlement 允许进 Git 的 tracked 面（Phase 2B2.1 起按当前作品动态构建）：
  - 02_素材知识库/<book_id>_<work_name>/  当前作品的单一 distillation subtree
    （由 build_settlement_allowlist / build_settlement_allowlist_from_dir 生成）
  - 01_原始素材 三份 material state files（素材资产.json / 素材清单.csv / 素材总索引.md）

绝不进 settlement：
  - 任何 sibling / 伪造前缀作品目录（02_素材知识库/ 整目录授权已废止）
  - 01 原著全文与 raw 源文件（Local Only；三份 metadata 由 allowlist 精确放行）
  - 06_工作区/（SP/BD 工作副本，Local Only）
  - 其他作品目录（03_作品工程/ 等）
"""
import re
from pathlib import Path

# book_id 格式：book_XXXX（XXXX 为 4 位数字），与 MaterialIntake 分配规则一致
BOOK_ID_RE = re.compile(r"^book_\d{4}$")
# 目录 basename 前缀：<book_id>_（用于蒸馏目录名校验）
BOOK_ID_PREFIX_RE = re.compile(r"^(book_\d{4})_")

# 三份 material state files（所有 settlement 的基础允许面）
MI_METADATA_NAMES = {"素材资产.json", "素材清单.csv", "素材总索引.md"}
MATERIAL_STATE_FILES = [
    "01_原始素材/素材资产.json",
    "01_原始素材/素材清单.csv",
    "01_原始素材/素材总索引.md",
]

# 绝不进 settlement 的路径标记（第二道保护）
BD_NEVER_STAGE_MARKERS = ("06_工作区/",)

# 兼容默认：不含任何蒸馏目录的静态面（禁止整个 02_素材知识库/ 授权）
BD_SETTLEMENT_ALLOW = list(MATERIAL_STATE_FILES)


def sanitize_work_name(name: str) -> str:
    """目录名安全化：去除路径分隔符 / 控制符 / 首尾空白与点；截断 80 字符。

    拒绝 `..`、绝对路径与跨目录注入（与 MaterialIntake safe_name 同语义）。
    """
    s = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "", str(name)).strip().strip(".")
    return s[:80] or "未命名"


def distill_dir_prefix(book_id: str, work_name: str) -> str:
    """构造当前作品 distillation subtree 前缀 `02_素材知识库/<book_id>_<work_name>/`。

    校验：
      - book_id 必须匹配 ^book_\\d{4}$（非法 → ValueError）
      - work_name 先 sanitize（拒绝 .. / 绝对路径注入）
    """
    if not BOOK_ID_RE.fullmatch(book_id):
        raise ValueError(f"非法 book_id: {book_id!r}（需 book_XXXX，XXXX 为 4 位数字）")
    safe = sanitize_work_name(work_name)
    return f"02_素材知识库/{book_id}_{safe}/"


def build_settlement_allowlist(book_id: str, work_name: str) -> list[str]:
    """当前作品的动态 settlement allowlist（本次动作最小必要面）。

    结果形如：
      ["02_素材知识库/book_0035_长安十二时辰/",
       "01_原始素材/素材资产.json",
       "01_原始素材/素材清单.csv",
       "01_原始素材/素材总索引.md"]

    绝不允许整个 02_素材知识库/ 目录（BD_SETTLEMENT_CURRENT_BOOK_ONLY）。
    """
    return [distill_dir_prefix(book_id, work_name), *MATERIAL_STATE_FILES]


def build_settlement_allowlist_from_dir(distill_rel: str) -> list[str]:
    """由蒸馏 subtree 相对路径（如 `02_素材知识库/book_0001_Alpha`）构建 allowlist。

    校验（BD_SIBLING_BOOK_CHANGE_UNEXPECTED）：
      - distill_rel 必须是 `02_素材知识库/` 下的相对 posix 路径（拒绝绝对路径 / .. / 其他目录）
      - 目录 basename 必须精确以合法 `<book_id>_` 开头（拒绝伪造前缀与 sibling）
    非法 → ValueError。
    """
    rel = str(distill_rel).replace("\\", "/").strip().rstrip("/")
    if rel.startswith("/") or rel.startswith("\\") or ".." in rel.split("/"):
        raise ValueError(f"非法 distill 路径: {distill_rel!r}（拒绝绝对路径 / ..）")
    parts = rel.split("/")
    if len(parts) != 2 or parts[0] != "02_素材知识库":
        raise ValueError(
            f"distill 路径必须位于 02_素材知识库/ 下且为单层目录: {distill_rel!r}")
    base = parts[1]
    m = BOOK_ID_PREFIX_RE.match(base)
    if not m:
        raise ValueError(f"distill 目录名必须以合法 <book_id>_ 开头: {base!r}")
    return [f"02_素材知识库/{base}/", *MATERIAL_STATE_FILES]


def is_settlement_allowed(rel: str, allowlist: list[str] | None = None) -> bool:
    """rel（posix）是否属于 settlement 允许面。allowlist 缺省时使用模块默认
    （仅三份 material state files；任何蒸馏目录都需要显式构建 allowlist）。"""
    rel = rel.replace("\\", "/").rstrip("/")
    for a in (allowlist if allowlist is not None else BD_SETTLEMENT_ALLOW):
        a = str(a).replace("\\", "/").rstrip("/")
        if rel == a or rel.startswith(a + "/"):
            return True
    return False


def is_settlement_never_stage(rel: str) -> bool:
    """第二道过滤：06_工作区 与 01 原著全文（非三份 metadata）绝不 staging。"""
    rel = rel.replace("\\", "/")
    if rel.startswith("01_原始素材/"):
        return Path(rel).name not in MI_METADATA_NAMES
    return any(rel == m.rstrip("/") or rel.startswith(m) for m in BD_NEVER_STAGE_MARKERS)
