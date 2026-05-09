import unittest

from tests._helpers import henan_physics_applicant  # noqa: F401  (sys.path side-effect)
from constraint_filter import run


class InputValidatorTests(unittest.TestCase):
    def test_missing_required_field_returns_error(self):
        applicant = henan_physics_applicant()
        applicant.pop("provincial_rank")
        res = run(applicant)
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error_code"], "INPUT_MISSING_REQUIRED_FIELD")
        self.assertIn("provincial_rank", res["error_detail"]["missing_fields"])

    def test_negative_rank_returns_invalid_field_value(self):
        applicant = henan_physics_applicant(provincial_rank=-5)
        res = run(applicant)
        self.assertEqual(res["error_code"], "INPUT_INVALID_FIELD_VALUE")
        self.assertEqual(res["error_detail"]["field"], "provincial_rank")

    def test_invalid_subject_combination_new_gaokao_312_both_phys_hist(self):
        applicant = henan_physics_applicant(
            selected_subjects=["物理", "历史", "化学"],
            subject_category="物理类",
        )
        res = run(applicant)
        self.assertEqual(res["error_code"], "INPUT_INVALID_SUBJECT_COMBINATION")

    def test_invalid_subject_combination_wrong_count(self):
        applicant = henan_physics_applicant(selected_subjects=["物理", "化学"])
        res = run(applicant)
        self.assertEqual(res["error_code"], "INPUT_INVALID_SUBJECT_COMBINATION")

    def test_province_not_in_list(self):
        applicant = henan_physics_applicant(province="火星")
        res = run(applicant)
        self.assertEqual(res["error_code"], "INPUT_INVALID_FIELD_VALUE")
        self.assertEqual(res["error_detail"]["field"], "province")

    def test_total_score_over_limit(self):
        applicant = henan_physics_applicant(total_score=999)
        res = run(applicant)
        self.assertEqual(res["error_code"], "INPUT_INVALID_FIELD_VALUE")
        self.assertEqual(res["error_detail"]["field"], "total_score")


if __name__ == "__main__":
    unittest.main()
