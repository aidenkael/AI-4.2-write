import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from adapter import load_bkp, parse_cards
from models import KnowledgeHit
from registry import discover_sources
from retrieve import score_candidates
import run as retrieve_run


CARD = """# Cards

## K001｜危机后保留新债

- knowledge_level: Work-specific Pattern
- dimension: 结构
- use_stages: longform_plan, chapter_plan, review
- problem_types: phase_transition, reader_promise
- scale: arc
- statement: 危机解决时同步暴露更具体的新债，避免张力归零。
- function: 维持阶段过渡的前拉。
- conditions: 旧危机已经真实兑现。
- mechanism: 解决动作同时制造下一项义务。
- effect: 满足感与新期待并存。
- scope: 本书阶段转折。
- boundary: 不能只开空泛大阴谋。
- confidence: 高
- evidence:
  - chapters/0001.md#L3
- tags: 假结局, 新债
"""


def _source_info(bkp: Path, book_id: str, title: str, identity: dict | None = None) -> dict:
    return {
        "source_kind": "reference_bkp",
        "source_id": book_id,
        "title": title,
        "author": "",
        "category": "",
        "package_dir": str(bkp),
        "identity": identity or {"bkp_contents": {}},
    }


class KnowledgeRetrieveCardsTest(unittest.TestCase):
    def test_parse_fields_search_and_hit_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            bkp = Path(tmp); (bkp / "knowledge").mkdir()
            (bkp / "knowledge" / "cards.md").write_text(CARD, encoding="utf-8")
            items = parse_cards(str(bkp), "book_x", "测试")
            self.assertEqual(len(items), 1)
            item = items[0]
            self.assertEqual(item.source_kind, "reference_bkp")
            self.assertEqual(item.source_id, "book_x")
            self.assertEqual(item.source_title, "测试")
            self.assertEqual(item.maturity, "source_bound")
            self.assertEqual(item.selection_ref, "reference_bkp/book_x/K001")
            self.assertEqual(item.use_stages, ["longform_plan", "chapter_plan", "review"])
            self.assertEqual(item.problem_types, ["phase_transition", "reader_promise"])
            self.assertEqual(item.scale, "arc")
            for value in (item.function, item.conditions, item.mechanism, item.effect, "phase_transition"):
                self.assertIn(value, item.searchable_text)
            ranked = score_candidates("危机解决后怎样避免张力归零", items)
            self.assertTrue(ranked)
            hit = KnowledgeHit(
                rank=1, source_kind=item.source_kind, source_id=item.source_id,
                source_title=item.source_title, maturity=item.maturity,
                knowledge_level=item.knowledge_level, statement=item.text,
                relevance_reason="test", source=item.source_file,
                source_anchor=item.source_anchor, evidence=item.evidence,
                scope=item.scope, boundary=item.boundary,
                counterevidence=item.counterevidence, confidence=item.confidence,
                dimension=item.dimension, use_stages=item.use_stages,
                problem_types=item.problem_types, scale=item.scale,
                function=item.function, conditions=item.conditions,
                mechanism=item.mechanism, effect=item.effect, raw_score=1.0)
            data = hit.to_dict()
            self.assertEqual(data["scale"], "arc")
            self.assertEqual(data["mechanism"], item.mechanism)
            self.assertEqual(data["source_anchor"], "K001")
            self.assertEqual(data["selection_ref"], "reference_bkp/book_x/K001")
            self.assertEqual(data["source_kind"], "reference_bkp")
            self.assertEqual(data["source_id"], "book_x")
            self.assertEqual(data["source_title"], "测试")
            self.assertEqual(data["maturity"], "source_bound")

    def test_load_bkp_prefers_cards_over_legacy_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            bkp = Path(tmp); (bkp / "knowledge").mkdir()
            (bkp / "knowledge" / "cards.md").write_text(CARD, encoding="utf-8")
            (bkp / "knowledge" / "observations.md").write_text("## 人物\n- 旧条目\n", encoding="utf-8")
            self.assertEqual(len(load_bkp(_source_info(bkp, "book_x", "测试"))), 1)

    def test_legacy_1984_and_three_body_load(self):
        root = Path(__file__).resolve().parents[3]
        for dirname in ("book_0038_一九八四", "book_0065_三体"):
            bkp = root / "02_素材知识库" / dirname / "bkp"
            identity = json.loads((bkp / "identity.json").read_text(encoding="utf-8"))
            info = _source_info(bkp, identity["book"]["book_id"], identity["book"]["title"], identity)
            self.assertGreater(len(load_bkp(info)), 0)

    def test_six_real_changan_creation_queries(self):
        """Frozen third-book cards answer six actual creation questions."""
        retrieve_run.BASE_DIR = str(Path(__file__).resolve().parents[3])
        retrieve_run.CATALOG = None
        cases = {
            "三层时钟互相接力": "K001",
            "假结局同时开出新债": "K002",
            "配给制揭示": "K004",
            "受限信息制造参与式推理": "K006",
            "章末钩子落在行动或决定": "K007",
            "从一条线索扩成完整场景": "K033",
        }
        for query, expected_anchor in cases.items():
            pkg = retrieve_run.retrieve(query, top_k=5)
            self.assertEqual(pkg.status, "OK", query)
            self.assertTrue(pkg.hits, query)
            top = pkg.hits[0]
            self.assertEqual(top.source_kind, "reference_bkp", query)
            self.assertEqual(top.source_id, "book_0035", query)
            self.assertEqual(top.selection_ref, f"reference_bkp/book_0035/{expected_anchor}", query)
            self.assertEqual(top.source, "knowledge/cards.md", query)
            self.assertEqual(top.source_anchor, expected_anchor, query)
        retrieve_run.CATALOG = None


class KnowledgeRetrieveMultiSourceTest(unittest.TestCase):
    """统一多源目录：三类来源共存于同一个 RetrievalPackage（混合检索证明）。"""

    def _build_fixture_root(self, tmp: Path) -> Path:
        root = Path(tmp)
        # 1) reference BKP（现有格式）
        bkp = root / "02_素材知识库" / "book_9001_参考小说" / "bkp"
        (bkp / "knowledge").mkdir(parents=True)
        (bkp / "identity.json").write_text(json.dumps({
            "schema_version": "bkp/v0.2", "schema_status": "FINALIZED",
            "book": {"book_id": "book_9001", "title": "参考小说", "author": "甲"},
            "source_snapshot": {"source_sha256": "0" * 64},
            "bkp_contents": {},
        }, ensure_ascii=False), encoding="utf-8")
        (bkp / "knowledge" / "cards.md").write_text(
            "## K001｜章末钩子观察\n"
            "- knowledge_level: Work-specific Pattern\n"
            "- dimension: 叙事节奏\n"
            "- statement: 章末钩子落在人物的行动或决定上，读者动力最强。\n"
            "- confidence: 高\n"
            "- evidence:\n"
            "  - chapters/0001.md#L3\n",
            encoding="utf-8")

        # 2) FINALIZED 方法知识包（02 method/）
        method = root / "02_素材知识库" / "book_9002_方法书" / "method"
        (method / "knowledge").mkdir(parents=True)
        (method / "identity.json").write_text(json.dumps({
            "schema_version": "gowrite_method_knowledge/v1",
            "schema_status": "FINALIZED_RETRIEVAL_READY",
            "source_kind": "method_source", "source_id": "book_9002",
            "title": "方法书", "author": "乙", "maturity": "source_bound",
            "source_snapshot": {"source_sha256": "1" * 64},
        }, ensure_ascii=False), encoding="utf-8")
        (method / "knowledge" / "cards.md").write_text(
            "## M0001｜章末钩子设计程序\n"
            "- statement: 章末钩子应给出下一步行动问题而非情绪总结。\n"
            "- method_kind: procedure\n"
            "- dimension: 叙事节奏\n"
            "- steps:\n"
            "  - 找到本章最后一个人物决定\n"
            "- evidence:\n"
            "  - sections/S0001.md#L3-L9\n"
            "- capability_candidate: true\n",
            encoding="utf-8")

        # 未定稿方法包：必须不可检索
        draft = root / "02_素材知识库" / "book_9003_草稿方法书" / "method"
        (draft / "knowledge").mkdir(parents=True)
        (draft / "identity.json").write_text(json.dumps({
            "schema_version": "gowrite_method_knowledge/v1",
            "schema_status": "DRAFT",
            "source_kind": "method_source", "source_id": "book_9003",
            "title": "草稿方法书", "author": "", "maturity": "source_bound",
            "source_snapshot": {"source_sha256": "2" * 64},
        }, ensure_ascii=False), encoding="utf-8")
        (draft / "knowledge" / "cards.md").write_text(
            "## M0001｜不该出现\n- statement: 章末钩子草稿卡。\n- method_kind: principle\n"
            "- dimension: 叙事节奏\n- evidence:\n  - sections/S0001.md#L1-L2\n",
            encoding="utf-8")

        # 3) FINALIZED_VALIDATED 已验证知识包（04）
        validated = root / "04_写作知识库" / "pkg_hook_check"
        (validated / "knowledge").mkdir(parents=True)
        (validated / "identity.json").write_text(json.dumps({
            "schema_version": "gowrite_validated_knowledge/v1",
            "schema_status": "FINALIZED_VALIDATED",
            "source_kind": "validated_knowledge", "source_id": "pkg_hook_check",
            "title": "章末钩子检查单", "maturity": "validated",
            "provenance": ["reference_bkp/book_9001/K001", "method_source/book_9002/M0001"],
        }, ensure_ascii=False), encoding="utf-8")
        (validated / "knowledge" / "cards.md").write_text(
            "## V0001｜章末钩子验证规则\n"
            "- statement: 多作品验证：章末钩子优先落在行动或决定上。\n"
            "- dimension: 叙事节奏\n"
            "- confidence: 高\n"
            "- evidence:\n"
            "  - validation.md#L1-L5\n",
            encoding="utf-8")

        # 非定稿 04 包：必须不可检索
        not_final = root / "04_写作知识库" / "pkg_draft"
        (not_final / "knowledge").mkdir(parents=True)
        (not_final / "identity.json").write_text(json.dumps({
            "schema_version": "gowrite_validated_knowledge/v1",
            "schema_status": "DRAFT",
            "source_kind": "validated_knowledge", "source_id": "pkg_draft",
            "title": "草稿验证包", "maturity": "validated",
        }, ensure_ascii=False), encoding="utf-8")
        (not_final / "knowledge" / "cards.md").write_text(
            "## V0001｜不该出现\n- statement: 章末钩子草稿验证卡。\n", encoding="utf-8")
        return root

    def test_discovery_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._build_fixture_root(Path(tmp))
            sources = discover_sources(str(root))
            keys = sorted(f"{s['source_kind']}/{s['source_id']}" for s in sources)
            self.assertEqual(keys, [
                "method_source/book_9002",
                "reference_bkp/book_9001",
                "validated_knowledge/pkg_hook_check",
            ])

    def test_mixed_retrieval_one_package_three_kinds(self):
        """Acceptance #4：一次 retrieve 返回同一混合包，含三类来源、
        各自不同的合法 selection_ref。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._build_fixture_root(Path(tmp))
            retrieve_run.BASE_DIR = str(root)
            retrieve_run.CATALOG = None
            try:
                pkg = retrieve_run.retrieve("章末钩子怎么设计才有读者动力", top_k=15)
                kinds = {h.source_kind for h in pkg.hits}
                self.assertEqual(kinds, {"reference_bkp", "method_source", "validated_knowledge"},
                                 [h.to_dict() for h in pkg.hits])
                refs = [h.selection_ref for h in pkg.hits]
                self.assertIn("reference_bkp/book_9001/K001", refs)
                self.assertIn("method_source/book_9002/M0001", refs)
                self.assertIn("validated_knowledge/pkg_hook_check/V0001", refs)
                self.assertEqual(len(refs), len(set(refs)))
                for h in pkg.hits:
                    self.assertTrue(h.selection_ref.startswith(f"{h.source_kind}/{h.source_id}/"))
                    self.assertNotEqual(h.source_title, "")
                # 包指纹包含归一化混合命中数据（序列化确定性）
                d1 = pkg.to_dict()
                d2 = pkg.to_dict()
                self.assertEqual(json.dumps(d1, sort_keys=True), json.dumps(d2, sort_keys=True))
            finally:
                retrieve_run.BASE_DIR = str(Path(__file__).resolve().parents[3])
                retrieve_run.CATALOG = None

    def test_method_fields_survive_hit_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._build_fixture_root(Path(tmp))
            retrieve_run.BASE_DIR = str(root)
            retrieve_run.CATALOG = None
            try:
                pkg = retrieve_run.retrieve("章末钩子怎么设计才有读者动力", top_k=15)
                method_hits = [h for h in pkg.hits if h.source_kind == "method_source"]
                self.assertTrue(method_hits)
                data = method_hits[0].to_dict()
                self.assertEqual(data["method_kind"], "procedure")
                self.assertEqual(data["capability_candidate"], True)
                self.assertEqual(data["maturity"], "source_bound")
                validated_hits = [h for h in pkg.hits if h.source_kind == "validated_knowledge"]
                self.assertTrue(validated_hits)
                self.assertEqual(validated_hits[0].to_dict()["maturity"], "validated")
            finally:
                retrieve_run.BASE_DIR = str(Path(__file__).resolve().parents[3])
                retrieve_run.CATALOG = None


class KnowledgeRetrieveMethodGateTest(unittest.TestCase):
    """FINALIZED_RETRIEVAL_READY 精确门控：其他 FINALIZED_* 状态不可检索。"""

    def _build_method_only_fixture(self, tmp: Path, schema_status: str, source_id: str = "book_8001") -> Path:
        root = Path(tmp)
        method = root / "02_素材知识库" / f"{source_id}_方法书" / "method"
        (method / "knowledge").mkdir(parents=True)
        (method / "identity.json").write_text(json.dumps({
            "schema_version": "gowrite_method_knowledge/v1",
            "schema_status": schema_status,
            "source_kind": "method_source", "source_id": source_id,
            "title": "方法书", "author": "乙", "maturity": "source_bound",
            "source_snapshot": {"source_sha256": "a" * 64},
        }, ensure_ascii=False), encoding="utf-8")
        (method / "knowledge" / "cards.md").write_text(
            "## M0001｜测试卡\n"
            "- statement: 测试方法卡。\n"
            "- method_kind: principle\n"
            "- dimension: 叙事节奏\n"
            "- evidence:\n"
            "  - sections/S0001.md#L1-L2\n",
            encoding="utf-8")
        return root

    def test_finalized_retrieval_ready_is_searchable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._build_method_only_fixture(Path(tmp), "FINALIZED_RETRIEVAL_READY")
            sources = discover_sources(str(root))
            keys = [f"{s['source_kind']}/{s['source_id']}" for s in sources]
            self.assertIn("method_source/book_8001", keys)

    def test_finalized_bare_not_searchable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._build_method_only_fixture(Path(tmp), "FINALIZED")
            sources = discover_sources(str(root))
            method_sources = [s for s in sources if s["source_kind"] == "method_source"]
            self.assertEqual(method_sources, [])

    def test_finalized_draft_not_searchable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._build_method_only_fixture(Path(tmp), "FINALIZED_DRAFT")
            sources = discover_sources(str(root))
            method_sources = [s for s in sources if s["source_kind"] == "method_source"]
            self.assertEqual(method_sources, [])

    def test_finalized_invalid_not_searchable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._build_method_only_fixture(Path(tmp), "FINALIZED_INVALID")
            sources = discover_sources(str(root))
            method_sources = [s for s in sources if s["source_kind"] == "method_source"]
            self.assertEqual(method_sources, [])

    def test_finalized_validated_not_searchable_for_method(self):
        """FINALIZED_VALIDATED 是已验证知识包状态，不应作为方法包被接受。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._build_method_only_fixture(Path(tmp), "FINALIZED_VALIDATED")
            sources = discover_sources(str(root))
            method_sources = [s for s in sources if s["source_kind"] == "method_source"]
            self.assertEqual(method_sources, [])


class KnowledgeRetrieveInsufficientTest(unittest.TestCase):
    """INSUFFICIENT_KNOWLEDGE 统一状态：无有效知识时返回统一多源合同。"""

    def test_insufficient_knowledge_on_empty_catalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            retrieve_run.BASE_DIR = str(Path(tmp))
            retrieve_run.CATALOG = None
            try:
                pkg = retrieve_run.retrieve("任意查询", top_k=5)
                self.assertEqual(pkg.status, "INSUFFICIENT_KNOWLEDGE")
            finally:
                retrieve_run.BASE_DIR = str(Path(__file__).resolve().parents[3])
                retrieve_run.CATALOG = None


if __name__ == "__main__":
    unittest.main()
