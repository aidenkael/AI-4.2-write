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
    use_stages: list = field(default_factory=list)
    problem_types: list = field(default_factory=list)
    scale: Optional[str] = None
    function: Optional[str] = None
    conditions: Optional[str] = None
    mechanism: Optional[str] = None
    effect: Optional[str] = None

    @property
    def searchable_text(self) -> str:
        """All text fields joined for search matching."""
        parts = [self.text, self.dimension, " ".join(self.use_stages),
                 " ".join(self.problem_types), " ".join(self.tags)]
        for value in (self.scale, self.function, self.conditions, self.mechanism, self.effect):
            if value:
                parts.append(value)
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
    source_anchor: str
    evidence: list
    scope: Optional[str]
    boundary: Optional[str]
    counterevidence: Optional[str]
    confidence: Optional[str]
    dimension: str
    use_stages: list = field(default_factory=list)
    problem_types: list = field(default_factory=list)
    scale: Optional[str] = None
    function: Optional[str] = None
    conditions: Optional[str] = None
    mechanism: Optional[str] = None
    effect: Optional[str] = None
    raw_score: float = 0.0

    def to_dict(self) -> dict:
        d = {
            "rank": self.rank,
            "book": self.book_title,
            "book_id": self.book_id,
            "knowledge_level": self.knowledge_level,
            "dimension": self.dimension,
            "use_stages": self.use_stages,
            "problem_types": self.problem_types,
            "scale": self.scale if self.scale else "absent",
            "function": self.function if self.function else "absent",
            "conditions": self.conditions if self.conditions else "absent",
            "mechanism": self.mechanism if self.mechanism else "absent",
            "effect": self.effect if self.effect else "absent",
            "statement": self.statement,
            "relevance_reason": self.relevance_reason,
            "source": self.source,
            "source_anchor": self.source_anchor,
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
