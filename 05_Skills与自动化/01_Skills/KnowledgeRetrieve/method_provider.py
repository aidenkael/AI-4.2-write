"""方法知识包 / 已验证知识包加载器（与 MethodDistill 定稿校验共享同一卡语法）。

卡语法（canonical，method 与 validated 共用）：

    ## M0001｜卡片标题
    - statement: 一句话陈述
    - method_kind: principle|diagnostic|procedure|checklist|failure_mode
    - dimension: ...
    - conditions: ...
    - steps:            （列表：缩进 "- " 行）
    - checks:
    - failure_modes:
    - scope: ...
    - boundary: ...
    - confidence: 高|中|低
    - use_stages: a, b
    - problem_types: ...
    - tags: ...
    - evidence:
      - sections/S0001.md#L1-L10
    - capability_candidate: true|false
    - knowledge_level: （可选；缺省按来源类型映射）
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from models import KnowledgeItem

CARD_HEADER_RE = re.compile(r"^##\s+([A-Za-z][A-Za-z0-9_-]*)\s*[｜|]\s*(.+?)\s*$")
FIELD_RE = re.compile(r"^-\s+([a-z_]+)\s*:\s*(.*)$")
LIST_FIELDS = ("steps", "checks", "failure_modes", "use_stages", "problem_types", "tags", "evidence")
COMMA_LIST_FIELDS = ("use_stages", "problem_types", "tags")

METHOD_LEVEL = {
    "principle": "方法原则",
    "diagnostic": "方法诊断",
    "procedure": "方法程序",
    "checklist": "方法检查单",
    "failure_mode": "方法失效模式",
}


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def parse_cards_generic(cards_path: Path) -> tuple[list[dict], list[str]]:
    """解析规范知识卡。返回 (cards, errors)；errors 覆盖结构性阻断（空/仍是模板）。

    卡级语义校验（重复 id、空 statement、证据引用有效性、来源指纹）属于
    MethodDistill 定稿合同，不在此处重复实现。
    """
    text = _read(Path(cards_path))
    errors: list[str] = []
    if not text.strip() or "<!-- 每张卡必须填写" in text:
        errors.append("knowledge/cards.md 仍是脚手架模板或为空")
        return [], errors

    cards: list[dict] = []
    current: dict | None = None
    active_list: str | None = None
    for raw in text.splitlines():
        header = CARD_HEADER_RE.match(raw)
        if header:
            if current is not None:
                cards.append(current)
            current = {
                "id": header.group(1), "title": header.group(2),
                "steps": [], "checks": [], "failure_modes": [],
                "use_stages": [], "problem_types": [], "tags": [], "evidence": [],
            }
            active_list = None
            continue
        if current is None:
            continue
        field = FIELD_RE.match(raw)
        if field:
            key, value = field.group(1), field.group(2).strip()
            if key in LIST_FIELDS:
                active_list = key
                if value:
                    if key in COMMA_LIST_FIELDS:
                        current[key] = [v.strip() for v in re.split(r"[,，]", value) if v.strip()]
                    else:
                        current[key] = [value]
            else:
                active_list = None
                current[key] = value
            continue
        item = re.match(r"^\s{2,}-\s+(.+?)\s*$", raw)
        if item and active_list:
            current[active_list].append(item.group(1).strip())
    if current is not None:
        cards.append(current)
    return cards, errors


def _load_identity(package_dir: Path) -> dict:
    identity_path = package_dir / "identity.json"
    if not identity_path.exists():
        raise ValueError(f"缺少 identity.json：{identity_path}")
    return json.loads(identity_path.read_text(encoding="utf-8"))


def _cards_to_items(cards: list[dict], *, source_kind: str, source_id: str,
                    source_title: str, maturity: str, default_level: str) -> list[KnowledgeItem]:
    items: list[KnowledgeItem] = []
    for c in cards:
        method_kind = c.get("method_kind") or None
        level = c.get("knowledge_level") or (
            METHOD_LEVEL.get(method_kind or "", default_level) if method_kind else default_level
        )
        cc = str(c.get("capability_candidate", "")).strip().lower() == "true"
        items.append(KnowledgeItem(
            source_kind=source_kind,
            source_id=source_id,
            source_title=source_title,
            maturity=maturity,
            knowledge_level=level,
            dimension=c.get("dimension", ""),
            text=c.get("statement", ""),
            source_file="knowledge/cards.md",
            source_anchor=c["id"],
            evidence=list(c.get("evidence", [])),
            scope=c.get("scope") or None,
            boundary=c.get("boundary") or None,
            confidence=c.get("confidence") or None,
            tags=list(c.get("tags", [])) + [c.get("title", "")],
            use_stages=list(c.get("use_stages", [])),
            problem_types=list(c.get("problem_types", [])),
            conditions=c.get("conditions") or None,
            method_kind=method_kind,
            steps=list(c.get("steps", [])),
            checks=list(c.get("checks", [])),
            failure_modes=list(c.get("failure_modes", [])),
            capability_candidate=cc,
        ))
    return items


def load_method_package(method_dir: Path) -> list[KnowledgeItem]:
    """加载一个已定稿（FINALIZED_*）方法知识包为通用知识条目。"""
    method_dir = Path(method_dir)
    identity = _load_identity(method_dir)
    if not str(identity.get("schema_status", "")).startswith("FINALIZED"):
        raise ValueError(f"方法包未定稿（{identity.get('schema_status')!r}），不可加载")
    cards, errors = parse_cards_generic(method_dir / "knowledge" / "cards.md")
    if errors:
        raise ValueError(f"方法包知识卡不可解析：{errors}")
    return _cards_to_items(
        cards,
        source_kind="method_source",
        source_id=str(identity.get("source_id") or ""),
        source_title=identity.get("title") or "",
        maturity="source_bound",
        default_level="方法知识",
    )


def load_validated_package(package_dir: Path) -> list[KnowledgeItem]:
    """加载一个 FINALIZED_VALIDATED 已验证知识包为通用知识条目。"""
    package_dir = Path(package_dir)
    identity = _load_identity(package_dir)
    if identity.get("schema_status") != "FINALIZED_VALIDATED":
        raise ValueError(f"已验证知识包未定稿（{identity.get('schema_status')!r}），不可加载")
    cards, errors = parse_cards_generic(package_dir / "knowledge" / "cards.md")
    if errors:
        raise ValueError(f"已验证知识包知识卡不可解析：{errors}")
    return _cards_to_items(
        cards,
        source_kind="validated_knowledge",
        source_id=str(identity.get("source_id") or ""),
        source_title=identity.get("title") or "",
        maturity="validated",
        default_level="已验证知识",
    )
