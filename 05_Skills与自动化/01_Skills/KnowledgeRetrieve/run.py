"""KnowledgeRetrieve — 统一多源知识检索（单一入口，不按知识库路由）。

一次 `retrieve(query)` 调用加载并搜索全部已启用来源（参考作品 BKP /
方法知识包 / 已验证知识包），返回一个混合多源 RetrievalPackage；每个命中
保留来源身份（source_kind / source_id / source_title / selection_ref）。
模型不需要、也不允许选择"先查哪个库"：相关命中在同一包内共存。

Usage:
    python run.py "创作问题"
    python run.py --list-sources
    python run.py --stats

No external dependencies. No vector DB. No embedding. No KG. No model call.
"""

import json
import sys
from collections import Counter
from pathlib import Path

# Add current dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from models import KnowledgeHit, RetrievalPackage  # noqa: E402
from registry import discover_sources  # noqa: E402
from adapter import load_bkp  # noqa: E402
from method_provider import (  # noqa: E402,F401  （MethodDistill 复用 parse_cards_generic）
    load_method_package,
    load_validated_package,
    parse_cards_generic,
)
from retrieve import score_candidates  # noqa: E402


# ---------------------------------------------------------------------------
# Globals
# --------------------------------------------------------------------------- #

BASE_DIR = str(Path(__file__).parent.parent.parent.parent)  # e:\AI-Write
CATALOG = None  # Lazy-loaded


def reset_catalog() -> None:
    """丢弃缓存目录（测试/来源变化后重建）。"""
    global CATALOG
    CATALOG = None


def _load_source(source: dict) -> list:
    kind = source["source_kind"]
    if kind == "reference_bkp":
        return load_bkp(source)
    if kind == "method_source":
        try:
            return load_method_package(source["package_dir"])
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            print(f"[WARN] 方法知识包不可加载（跳过）：{source['package_dir']}：{exc}")
            return []
    if kind == "validated_knowledge":
        try:
            return load_validated_package(source["package_dir"])
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            print(f"[WARN] 已验证知识包不可加载（跳过）：{source['package_dir']}：{exc}")
            return []
    print(f"[WARN] 未知 source_kind（跳过）：{kind}")
    return []


def _load_catalog():
    """Load all searchable knowledge sources into a unified in-memory catalog."""
    global CATALOG
    if CATALOG is not None:
        return CATALOG

    sources = discover_sources(BASE_DIR)
    all_items = []
    source_registry = {}
    for source in sources:
        items = _load_source(source)
        all_items.extend(items)
        key = f"{source['source_kind']}/{source['source_id']}"
        source_registry[key] = {
            "source_kind": source["source_kind"],
            "source_id": source["source_id"],
            "title": source["title"],
            "author": source.get("author", ""),
            "item_count": len(items),
        }
        if items:
            print(f"[INFO] Loaded {source['title'] or source['source_id']} "
                  f"({key}): {len(items)} items")

    CATALOG = {
        "items": all_items,
        "sources": source_registry,
        "total": len(all_items),
    }
    print(f"[INFO] Total catalog: {CATALOG['total']} items from {len(source_registry)} sources")
    return CATALOG


# ---------------------------------------------------------------------------
# Query understanding
# ---------------------------------------------------------------------------

def understand_query(query: str) -> str:
    """Generate a brief understanding of the creative question."""
    # Simple heuristic: extract key creative concepts
    concepts = []
    concept_map = {
        "科学": "科学概念",
        "概念": "科学概念",
        "科普": "科学概念教学化",
        "剧情": "情节驱动",
        "悬念": "悬念设计",
        "张力": "叙事张力",
        "灾难": "灾难/危机",
        "避免": "不可避免性",
        "行动": "角色行动",
        "篮球": "体育/竞技",
        "战术": "战术设计",
        "挡拆": "体育战术",
        "防守": "体育战术",
        "监控": "监控/控制",
        "恐惧": "恐惧/情绪",
        "人物": "人物构建",
        "关系": "关系设计",
        "结构": "叙事结构",
        "节奏": "叙事节奏",
        "信息": "信息管理",
        "世界观": "世界观构建",
        "对话": "对白设计",
        "情绪": "情绪传递",
        "伏笔": "伏笔/悬念",
        "反转": "反转/揭示",
        "失败": "失败结局",
    }
    for key, concept in concept_map.items():
        if key in query:
            concepts.append(concept)

    if not concepts:
        return "通用创作问题，未识别到特定创作维度"

    unique = list(dict.fromkeys(concepts))  # deduplicate preserving order
    return f"涉及创作维度：{'、'.join(unique)}"


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def retrieve(query: str, top_k: int = 15) -> RetrievalPackage:
    """Full retrieval pipeline: 全源候选召回 → 归一化混合包。

    一次调用搜索全部已启用来源；不路由到单一存储，不让模型选库。
    Note: Semantic selection (Agent 语义判断) is done externally
    by the calling agent, not by this script.
    """
    catalog = _load_catalog()
    understanding = understand_query(query)

    # Step 1: Candidate recall（全源混合召回）
    candidates = score_candidates(query, catalog["items"], top_k=top_k)

    if not candidates:
        gaps = ["关键词召回为零：当前可检索知识资产中没有匹配的知识条目"]
        if not catalog["sources"]:
            gaps.append("当前没有任何已定稿的可检索知识包")
        return RetrievalPackage(
            query=query,
            query_understanding=understanding,
            status="INSUFFICIENT_KNOWLEDGE",
            gaps=gaps,
        )

    # Step 2: Build hits（通用身份；保留来源与 selection_ref）
    hits = []
    for rank, (item, score, matched_kw) in enumerate(candidates, 1):
        hit = KnowledgeHit(
            rank=rank,
            source_kind=item.source_kind,
            source_id=item.source_id,
            source_title=item.source_title,
            maturity=item.maturity,
            knowledge_level=item.knowledge_level,
            statement=item.text,
            relevance_reason=f"关键词匹配 {len(matched_kw)} 个，原始得分 {score:.3f}",
            source=item.source_file,
            source_anchor=item.source_anchor,
            evidence=item.evidence,
            scope=item.scope,
            boundary=item.boundary,
            counterevidence=item.counterevidence,
            confidence=item.confidence,
            dimension=item.dimension,
            use_stages=item.use_stages,
            problem_types=item.problem_types,
            scale=item.scale,
            function=item.function,
            conditions=item.conditions,
            mechanism=item.mechanism,
            effect=item.effect,
            method_kind=item.method_kind,
            steps=item.steps,
            checks=item.checks,
            failure_modes=item.failure_modes,
            capability_candidate=item.capability_candidate,
            raw_score=score,
        )
        hits.append(hit)

    # Step 3: Check if any hits are meaningful
    # If top score is very low, flag INSUFFICIENT
    if hits and hits[0].raw_score < 0.15:
        pkg = RetrievalPackage(
            query=query,
            query_understanding=understanding,
            hits=hits,
            status="INSUFFICIENT_KNOWLEDGE",
            gaps=[
                "候选召回得分极低，当前知识资产中可能没有真正相关的知识",
                "建议：检查知识资产是否覆盖该创作维度，或补充新的来源素材",
            ],
            candidate_count=len(candidates),
        )
    else:
        pkg = RetrievalPackage(
            query=query,
            query_understanding=understanding,
            hits=hits,
            status="OK",
            candidate_count=len(candidates),
        )

    return pkg


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_list_sources():
    catalog = _load_catalog()
    for key, info in catalog["sources"].items():
        print(f"  [{info['source_kind']}] {info['source_id']}: "
              f"{info['title']}（{info['author'] or '—'}）— {info['item_count']} items")


def cmd_stats():
    catalog = _load_catalog()
    levels = Counter(item.knowledge_level for item in catalog["items"])
    dims = Counter(item.dimension for item in catalog["items"])
    kinds = Counter(item.source_kind for item in catalog["items"])
    print(f"\nTotal items: {catalog['total']}")
    print(f"\nBy source kind:")
    for sk, cnt in kinds.most_common():
        print(f"  {sk}: {cnt}")
    print(f"\nBy knowledge level:")
    for kl, cnt in levels.most_common():
        print(f"  {kl}: {cnt}")
    print(f"\nTop dimensions:")
    for dim, cnt in dims.most_common(15):
        print(f"  {dim}: {cnt}")


def cmd_retrieve(query: str):
    pkg = retrieve(query)
    print(json.dumps(pkg.to_dict(), ensure_ascii=False, indent=2))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    arg = sys.argv[1]

    if arg in ("--list-sources", "--list-books"):
        cmd_list_sources()
    elif arg == "--stats":
        cmd_stats()
    else:
        cmd_retrieve(arg)


if __name__ == "__main__":
    main()
