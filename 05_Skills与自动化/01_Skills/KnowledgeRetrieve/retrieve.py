"""Candidate retrieval: lightweight keyword/bigram matching.

No vector DB, no embedding, no reranker.
Only simple token matching + dimension boost + confidence weight.
"""

import re
from collections import Counter
from models import KnowledgeItem


def _tokenize(text: str) -> set:
    """Extract tokens: Chinese bigrams + words (2+ chars)."""
    tokens = set()
    # Chinese bigrams
    cn_chars = re.findall(r"[\u4e00-\u9fff]", text)
    for i in range(len(cn_chars) - 1):
        tokens.add(cn_chars[i] + cn_chars[i + 1])
    # Also add single Chinese chars for short queries
    for c in cn_chars:
        tokens.add(c)
    # Alphanumeric words
    words = re.findall(r"[a-zA-Z_]{2,}", text)
    tokens.update(w.lower() for w in words)
    return tokens


def _extract_query_keywords(query: str) -> set:
    """Extract meaningful keywords from a creative question."""
    # Remove common Chinese stop words / particles
    stop = {
        "我想", "怎样", "如何", "什么", "怎么", "应该", "可以",
        "能不能", "是否", "参考", "建议", "帮我", "请问", "一个",
        "一些", "这个", "那个", "问题", "需要", "希望", "想要",
        "the", "a", "an", "is", "to", "for", "of", "and",
    }
    tokens = _tokenize(query)
    # Filter stop words
    filtered = set()
    for t in tokens:
        if t in stop:
            continue
        if len(t) < 2:
            continue
        filtered.add(t)
    return filtered


def score_candidates(query: str, items: list, top_k: int = 15) -> list:
    """Score and rank knowledge items by keyword relevance.

    Returns list of (item, score) tuples, sorted by score descending.
    """
    keywords = _extract_query_keywords(query)
    if not keywords:
        return []

    scored = []
    for item in items:
        search_text = item.searchable_text
        search_tokens = _tokenize(search_text)

        # Count keyword matches
        match_count = 0
        matched_keywords = []
        for kw in keywords:
            if kw in search_tokens:
                match_count += 1
                matched_keywords.append(kw)
            elif kw in search_text.lower():
                match_count += 1
                matched_keywords.append(kw)

        if match_count == 0:
            continue

        # Base score: match ratio
        score = match_count / max(len(keywords), 1)

        # Dimension match bonus: if a keyword matches the dimension name
        dim_tokens = _tokenize(item.dimension)
        dim_match = sum(1 for kw in keywords if kw in dim_tokens or kw in item.dimension)
        if dim_match > 0:
            score += 0.3 * dim_match

        # Knowledge level priority（按知识等级打分；绝不按 source_kind 硬编码赢家，
        # 参考 BKP / 方法知识 / 已验证知识的相关命中可在同一个包内共存）：
        # Pattern > Deep Dive Pattern > 已验证知识 > Observation > Deep Dive Knowledge
        # > 方法原则/程序/检查单 > Inference / 方法诊断·失效模式 > Boundary(负)
        level_bonus = {
            "Work-specific Pattern": 0.2,
            "Deep Dive Pattern": 0.2,
            "已验证知识": 0.15,
            "Observation": 0.1,
            "Deep Dive Observation": 0.1,
            "方法原则": 0.1,
            "方法程序": 0.1,
            "方法检查单": 0.1,
            "Deep Dive Knowledge": 0.05,
            "方法诊断": 0.05,
            "方法失效模式": 0.05,
            "Inference": 0.0,
            "Boundary": -0.1,
        }
        score += level_bonus.get(item.knowledge_level, 0)

        # Confidence bonus
        if item.confidence == "高":
            score += 0.05
        elif item.confidence == "低":
            score -= 0.05

        scored.append((item, score, matched_keywords))

    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)

    return scored[:top_k]
