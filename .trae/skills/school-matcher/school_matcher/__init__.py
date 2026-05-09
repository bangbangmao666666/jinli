
"""school-matcher: 院校匹配模块 - 院校匹配Skill。

高考志愿填报院校匹配模块，对专业+院校组合进行八维深度评估。
"""
import traceback

from .errors import MatcherError
from .input_validator import validate
from .output_formatter import format_output


def run(data, data_dir=None):
    """主入口函数。

    Args:
        data: 输入数据，可以是流水线模式或单查询模式
        data_dir: 可选的数据目录路径

    Returns:
        评估结果字典
    """
    try:
        # 输入校验
        warnings = validate(data)

        # 格式化输出
        return format_output(data, warnings, data_dir)

    except MatcherError as e:
        return e.to_response()
    except Exception as e:
        # 兜底异常处理
        return {
            "status": "error",
            "error_code": "RUNTIME_UNEXPECTED_EXCEPTION",
            "error_category": "runtime",
            "error_message": "未预期异常：{}".format(e),
            "error_detail": {"traceback": traceback.format_exc()},
            "user_action_required": "请将完整错误信息反馈给维护者",
            "partial_result": None,
        }

