import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from adapter import load_bkp, parse_cards
from models import KnowledgeHit
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


class KnowledgeRetrieveCardsTest(unittest.TestCase):
    def test_parse_fields_search_and_hit_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            bkp = Path(tmp); (bkp / "knowledge").mkdir()
            (bkp / "knowledge" / "cards.md").write_text(CARD, encoding="utf-8")
            items = parse_cards(str(bkp), "book_x", "测试")
            self.assertEqual(len(items), 1)
            item = items[0]
            self.assertEqual(item.use_stages, ["longform_plan", "chapter_plan", "review"])
            self.assertEqual(item.problem_types, ["phase_transition", "reader_promise"])
            self.assertEqual(item.scale, "arc")
            for value in (item.function, item.conditions, item.mechanism, item.effect, "phase_transition"):
                self.assertIn(value, item.searchable_text)
            ranked = score_candidates("危机解决后怎样避免张力归零", items)
            self.assertTrue(ranked)
            hit = KnowledgeHit(1, item.book_id, item.book_title, item.knowledge_level,
                               item.text, "test", item.source_file, item.source_anchor, item.evidence, item.scope,
                               item.boundary, item.counterevidence, item.confidence, item.dimension,
                               item.use_stages, item.problem_types, item.scale, item.function,
                               item.conditions, item.mechanism, item.effect, 1.0)
            data = hit.to_dict()
            self.assertEqual(data["scale"], "arc")
            self.assertEqual(data["mechanism"], item.mechanism)
            self.assertEqual(data["source_anchor"], "K001")

    def test_load_bkp_prefers_cards_over_legacy_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            bkp = Path(tmp); (bkp / "knowledge").mkdir()
            (bkp / "knowledge" / "cards.md").write_text(CARD, encoding="utf-8")
            (bkp / "knowledge" / "observations.md").write_text("## 人物\n- 旧条目\n", encoding="utf-8")
            info = {"bkp_dir": str(bkp), "book_id": "book_x", "title": "测试", "identity": {"bkp_contents": {}}}
            self.assertEqual(len(load_bkp(info)), 1)

    def test_legacy_1984_and_three_body_load(self):
        root = Path(__file__).resolve().parents[3]
        for dirname in ("book_0038_一九八四", "book_0065_三体"):
            bkp = root / "02_素材知识库" / dirname / "bkp"
            identity = json.loads((bkp / "identity.json").read_text(encoding="utf-8"))
            info = {"bkp_dir": str(bkp), "book_id": identity["book"]["book_id"],
                    "title": identity["book"]["title"], "identity": identity}
            self.assertGreater(len(load_bkp(info)), 0)

    def test_six_real_changan_creation_queries(self):
        """Frozen third-book cards answer six actual creation questions."""
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
            self.assertEqual(top.book_id, "book_0035", query)
            self.assertEqual(top.source, "knowledge/cards.md", query)
            self.assertEqual(top.source_anchor, expected_anchor, query)


if __name__ == "__main__":
    unittest.main()
