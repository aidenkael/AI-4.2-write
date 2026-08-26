"""Data classes for KnowledgeRetrieve（通用多源检索模型）。

公共检索模型不再是 book-specific：所有可检索条目归一化为通用身份
（source_kind / source_id / source_title / source_anchor / selection_ref /
maturity / knowledge_level ...）。内部参考作品适配器仍可理解 legacy
book 身份，但公共 RetrievalPackage/hit 合同与全部消费者使用通用身份。

来源种类（source_kind）：
  reference_bkp       02_素材知识库/*/bkp（参考作品 BKP）
  method_source       02_素材知识库/*/method（方法/技巧资料知识包）
  validated_knowledge 04_写作知识库/**（经多作品验证的知识包）
"""

from dataclasses import dataclass, field
from typing import Optional

SOURCE_KINDS = ("reference_bkp", "method_source", "validated_knowledge")


def make_selection_ref(source_kind: str, source_id: str, source_anchor: str) -> str:
    """canonical selection ref：<source_kind>/<source_id>/<source_anchor>"""
    return f"{source_kind}/{source_id}/{source_anchor}"


@dataclass
class KnowledgeItem:
    """A single knowledge item from any searchable knowledge store."""
    source_kind: str              # reference_bkp | method_source | validated_knowledge
    source_id: str                # canonical source/package id（参考作品 = book_id）
    source_title: str             # human-facing source title
    maturity: str                 # source_bound | validated
    knowledge_level: str          # BKP 等级 / 方法等级（方法卡按 method_kind 映射）/ 已验证知识
    dimension: str                # e.g. 信息控制, 世界观, 结构, 人物构建
    text: str                     # full knowledge text / statement
    source_file: str              # relative path within the knowledge package
    source_anchor: str            # item identifier or section
    evidence: list = field(default_factory=list)
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
    # method-specific optional fields（方法知识包特有；其余来源为空）
    method_kind: Optional[str] = None
    steps: list = field(default_factory=list)
    checks: list = field(default_factory=list)
    failure_modes: list = field(default_factory=list)
    capability_candidate: bool = False

    @property
    def selection_ref(self) -> str:
        return make_selection_ref(self.source_kind, self.source_id, self.source_anchor)

    @property
    def searchable_text(self) -> str:
        """All text fields joined for search matching."""
        parts = [self.text, self.dimension, " ".join(self.use_stages),
                 " ".join(self.problem_types), " ".join(self.tags), self.source_title]
        for value in (self.scale, self.function, self.conditions, self.mechanism,
                      self.effect, self.scope, self.boundary, self.counterevidence,
                      self.method_kind):
            if value:
                parts.append(value)
        parts.extend(self.steps)
        parts.extend(self.checks)
        parts.extend(self.failure_modes)
        for e in self.evidence:
            parts.append(e)
        return " ".join(parts)


@dataclass
class KnowledgeHit:
    """A knowledge item with retrieval metadata（通用身份；非 book-specific）。"""
    rank: int
    source_kind: str
    source_id: str
    source_title: str
    maturity: str
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
    # method-specific optional fields when present
    method_kind: Optional[str] = None
    steps: list = field(default_factory=list)
    checks: list = field(default_factory=list)
    failure_modes: list = field(default_factory=list)
    capability_candidate: bool = False
    raw_score: float = 0.0

    @property
    def selection_ref(self) -> str:
        return make_selection_ref(self.source_kind, self.source_id, self.source_anchor)

    def to_dict(self) -> dict:
        d = {
            "rank": self.rank,
            "selection_ref": self.selection_ref,
            "source_kind": self.source_kind,
            "source_id": self.source_id,
            "source_title": self.source_title,
            "maturity": self.maturity,
            "knowledge_level": self.knowledge_level,
            "dimension": self.dimension,
            "use_stages": self.use_stages,
            "problem_types": self.problem_types,
            "scale": self.scale,
            "function": self.function,
            "conditions": self.conditions,
            "mechanism": self.mechanism,
            "effect": self.effect,
            "statement": self.statement,
            "relevance_reason": self.relevance_reason,
            "source": self.source,
            "source_anchor": self.source_anchor,
            "evidence": self.evidence,
            "scope": self.scope,
            "boundary": self.boundary,
            "counterevidence": self.counterevidence,
            "confidence": self.confidence,
            "raw_score": self.raw_score,
        }
        if self.method_kind:
            d.update({
                "method_kind": self.method_kind,
                "steps": self.steps,
                "checks": self.checks,
                "failure_modes": self.failure_modes,
                "capability_candidate": self.capability_candidate,
            })
        return d


@dataclass
class RetrievalPackage:
    """Complete retrieval result（单一混合多源包；不按知识库路由）。"""
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
