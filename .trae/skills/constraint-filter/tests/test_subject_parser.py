import unittest

from tests import _helpers  # noqa: F401
from constraint_filter.subject_parser import parse, satisfies
from constraint_filter.data_loader import load_subject_requirement_keywords
from constraint_filter.errors import SubjectRequirementParseFailed


class SubjectParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kw = load_subject_requirement_keywords()

    def test_parse_none(self):
        self.assertEqual(parse("不限", self.kw), {"logic": "NONE", "subjects": []})
        self.assertEqual(parse("不提科目要求", self.kw), {"logic": "NONE", "subjects": []})

    def test_parse_and(self):
        self.assertEqual(parse("物理+化学", self.kw), {"logic": "AND", "subjects": ["物理", "化学"]})
        self.assertEqual(
            parse("物理和化学", self.kw), {"logic": "AND", "subjects": ["物理", "化学"]}
        )

    def test_parse_or(self):
        self.assertEqual(parse("物理或化学", self.kw), {"logic": "OR", "subjects": ["物理", "化学"]})

    def test_parse_single(self):
        self.assertEqual(parse("物理", self.kw), {"logic": "AND", "subjects": ["物理"]})

    def test_parse_forbidden_english_or(self):
        # 英文 "or" 必须抛错而非推断
        with self.assertRaises(SubjectRequirementParseFailed):
            parse("物理or化学", self.kw)

    def test_parse_forbidden_slash(self):
        with self.assertRaises(SubjectRequirementParseFailed):
            parse("物理/化学", self.kw)

    def test_parse_unknown_subject_raises(self):
        with self.assertRaises(SubjectRequirementParseFailed):
            parse("物理+烹饪", self.kw)

    def test_parse_mixed_and_or_raises(self):
        with self.assertRaises(SubjectRequirementParseFailed):
            parse("物理+化学或生物", self.kw)

    def test_satisfies_and(self):
        req = {"logic": "AND", "subjects": ["物理", "化学"]}
        self.assertTrue(satisfies(req, ["物理", "化学", "生物"]))
        self.assertFalse(satisfies(req, ["物理", "生物"]))

    def test_satisfies_or(self):
        req = {"logic": "OR", "subjects": ["物理", "化学"]}
        self.assertTrue(satisfies(req, ["历史", "化学", "地理"]))
        self.assertFalse(satisfies(req, ["历史", "地理", "政治"]))

    def test_satisfies_none(self):
        self.assertTrue(satisfies({"logic": "NONE", "subjects": []}, []))


if __name__ == "__main__":
    unittest.main()
