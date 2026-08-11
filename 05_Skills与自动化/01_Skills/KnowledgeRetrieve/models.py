"""Data classes for KnowledgeRetrieve."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class KnowledgeItem:
    """A single knowledge item from a BKP."""
    book_id: str
    book_title: str
    knowledge_level: str          # Observation | Inference | Work-specific Pattern | Deep Dive Knowledge
    dimension: str                # e.g. 信息控制, 世界观, 结构
    text: str                     # full knowledge text
    source_file: str              # relative path within BKP
    source_anchor: str            # item identifier or section
    evidence: list = field(default_factory=list)    # chapter/line refs
    scope: Optional[str] = None
    boundary: Optional[str] = None
    counterevidence: Optional[str] = None
    confidence: Optional[str] = None
    tags: list = field(default_factory=list)

    @property
    def searchable_text(self) -> str:
        """All text fields joined for search matching."""
        parts = [self.text, self.dimension]
        if self.scope:
            parts.append(self.scope)
        if self.boundary:
            parts.append(self.boundary)
        if self.counterevidence:
            parts.append(self.counterevidence)
        for e in self.evidence:
            parts.append(e)
        return " ".join(parts)


@dataclass
class KnowledgeHit:
    """A knowledge item with retrieval metadata."""
    rank: int
    book_id: str
    book_title: str
    knowledge_level: str
    statement: str
    relevance_reason: str
    source: str
    evidence: list
    scope: Optional[str]
    boundary: Optional[str]
    counterevidence: Optional[str]
    confidence: Optional[str]
    dimension: str
    raw_score: float = 0.0

    def to_dict(self) -> dict:
        d = {
            "rank": self.rank,
            "book": self.book_title,
            "book_id": self.book_id,
            "knowledge_level": self.knowledge_level,
            "dimension": self.dimension,
            "statement": self.statement,
            "relevance_reason": self.relevance_reason,
            "source": self.source,
            "evidence": self.evidence,
            "scope": self.scope if self.scope else "absent",
            "boundary": self.boundary if self.boundary else "absent",
            "counterevidence": self.counterevidence if self.counterevidence else "absent",
            "confidence": self.confidence if self.confidence else "absent",
            "raw_score": self.raw_score,
        }
        return d


@dataclass
class RetrievalPackage:
    """Complete retrieval result."""
    query: str
    query_understanding: str
    hits: list = field(default_factory=list)
    gaps: list = field(default_factory=list)
    status: str = "OK"
    candidate_count: int = 0

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "query_understanding": self.query_understanding,
            "status": self.status,
            "candidate_count": self.candidate_count,
            "hit_count": len(self.hits),
            "hits": [h.to_dict() for h in self.hits],
            "gaps": self.gaps,
        }
