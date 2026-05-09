
"""测试输入校验模块。"""
import unittest

from school_matcher.errors import InputMissingRequiredFieldError, InputUpstreamEmptyError, InputInvalidFieldValueError
from school_matcher.input_validator import validate


class TestInputValidator(unittest.TestCase):
    """测试输入校验。"""

    def test_validate_empty_data(self):
        """测试空数据。"""
        with self.assertRaises(InputUpstreamEmptyError):
            validate({})

    def test_validate_single_query(self):
        """测试单查询模式。"""
        data = {
            "school_name": "东北电力大学",
            "major_name": "电气工程及其自动化",
            "applicant_profile": {
                "province": "河南",
                "total_score": 550,
                "provincial_rank": 50000,
            },
        }
        warnings = validate(data)
        self.assertIsInstance(warnings, list)

    def test_validate_pipeline_mode_empty_pool(self):
        """测试流水线模式——基本盘为空。"""
        data = {
            "eligible_pool": [],
            "passed_majors": [],
            "applicant_profile": {
                "province": "河南",
                "total_score": 550,
                "provincial_rank": 50000,
            },
        }
        with self.assertRaises(InputUpstreamEmptyError):
            validate(data)

    def test_validate_pipeline_mode_missing_field(self):
        """测试流水线模式——缺失必填字段。"""
        data = {
            "eligible_pool": [{"school_name": "测试"}],
            "passed_majors": [{"major_name": "测试"}],
        }
        with self.assertRaises(InputMissingRequiredFieldError):
            validate(data)

    def test_validate_query_mode_missing_both(self):
        """测试查询模式——同时缺少school_name和major_name。"""
        data = {
            "applicant_profile": {
                "province": "河南",
            },
        }
        with self.assertRaises(InputInvalidFieldValueError):
            validate(data)


if __name__ == "__main__":
    unittest.main()
