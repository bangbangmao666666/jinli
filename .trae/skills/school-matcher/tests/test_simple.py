
"""简单的测试脚本"""
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from school_matcher import run


def test_simple():
    """简单测试"""
    data = {
        "school_name": "东北电力大学",
        "major_name": "电气工程及其自动化",
        "applicant_profile": {
            "province": "河南",
            "total_score": 550,
            "provincial_rank": 50000,
            "preferred_cities": ["吉林"]
        }
    }

    try:
        result = run(data)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return

    print("测试结果:")
    print(f"状态: {result.get('status')}")
    if result.get('status') == 'success':
        print(f"推荐数量: {len(result.get('recommendations', []))}")
        if result.get('recommendations'):
            rec = result['recommendations'][0]
            print(f"学校: {rec.get('school_name')}")
            print(f"专业: {rec.get('major_name')}")
            print(f"星级: {rec.get('overall_rating')}")
    else:
        print(f"错误码: {result.get('error_code')}")
        print(f"错误信息: {result.get('error_message')}")
        print(f"用户操作建议: {result.get('user_action_required')}")


if __name__ == "__main__":
    test_simple()

