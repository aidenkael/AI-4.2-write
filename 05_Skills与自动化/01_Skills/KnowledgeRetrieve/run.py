"""KnowledgeRetrieve — minimal cross-book retrieval prototype (G3-C).

Usage:
    python run.py "创作问题"
    python run.py --list-books
    python run.py --stats

No external dependencies. No vector DB. No embedding. No KG.
"""

import json
import os
import sys
from pathlib import Path

# Add current dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from models import KnowledgeItem, KnowledgeHit, RetrievalPackage
from registry import discover_bkps
from adapter import load_bkp
from retrieve import score_candidates


# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

BASE_DIR = str(Path(__file__).parent.parent.parent.parent)  # e:\AI-Write
CATALOG = None  # Lazy-loaded


def _load_catalog():
    """Load all BKPs into a unified in-memory catalog."""
    global CATALOG
    if CATALOG is not None:
        return CATALOG

    bkps = discover_bkps(BASE_DIR)
    if not bkps:
        print("[ERROR] No BKPs found under 02_原著蒸馏/*/bkp/")
        sys.exit(1)

    all_items = []
    book_registry = {}
    for bkp in bkps:
        items = load_bkp(bkp)
        all_items.extend(items)
        book_registry[bkp["book_id"]] = {
            "title": bkp["title"],
            "author": bkp["author"],
            "item_count": len(items),
        }
        print(f"[INFO] Loaded {bkp['title']} ({bkp['book_id']}): {len(items)} items")

    CATALOG = {
        "items": all_items,
        "books": book_registry,
        "total": len(all_items),
    }
    print(f"[INFO] Total catalog: {CATALOG['total']} items from {len(book_registry)} books")
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
    """Full retrieval pipeline: candidate recall → structured output.

    Note: Semantic selection (Agent 语义判断) is done externally
    by the calling agent, not by this script.
    """
    catalog = _load_catalog()
    understanding = understand_query(query)

    # Step 1: Candidate recall
    candidates = score_candidates(query, catalog["items"], top_k=top_k)

    if not candidates:
        return RetrievalPackage(
            query=query,
            query_understanding=understanding,
            status="INSUFFICIENT_BKP",
            gaps=["关键词召回为零：当前两个 BKP（一九八四、三体）中没有匹配的知识条目"],
        )

    # Step 2: Build hits
    hits = []
    for rank, (item, score, matched_kw) in enumerate(candidates, 1):
        hit = KnowledgeHit(
            rank=rank,
            book_id=item.book_id,
            book_title=item.book_title,
            knowledge_level=item.knowledge_level,
            statement=item.text,
            relevance_reason=f"关键词匹配 {len(matched_kw)} 个，原始得分 {score:.3f}",
            source=item.source_file,
            evidence=item.evidence,
            scope=item.scope,
            boundary=item.boundary,
            counterevidence=item.counterevidence,
            confidence=item.confidence,
            dimension=item.dimension,
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
            status="INSUFFICIENT_BKP",
            gaps=[
                "候选召回得分极低，当前两个 BKP 中可能没有真正相关的知识",
                "建议：检查 BKP 是否覆盖该创作维度，或补充新的参考作品",
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

def cmd_list_books():
    catalog = _load_catalog()
    for bid, info in catalog["books"].items():
        print(f"  {bid}: {info['title']} ({info['author']}) — {info['item_count']} items")


def cmd_stats():
    catalog = _load_catalog()
    from collections import Counter
    levels = Counter(item.knowledge_level for item in catalog["items"])
    dims = Counter(item.dimension for item in catalog["items"])
    print(f"\nTotal items: {catalog['total']}")
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

    if arg == "--list-books":
        cmd_list_books()
    elif arg == "--stats":
        cmd_stats()
    else:
        cmd_retrieve(arg)


if __name__ == "__main__":
    main()
