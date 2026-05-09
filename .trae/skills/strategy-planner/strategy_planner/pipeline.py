"""主流水线模块。

整合所有步骤，生成完整志愿填报方案。
"""
from __future__ import annotations

from typing import Any, Dict, List

from .errors import (
    StrategyPlannerError,
    InputUpstreamEmptyError,
    DataRuleNotFoundError,
)
from .input_validator import validate
from .data_loader import load_province_application_rules, get_province_rule_or_default
from .rule_matcher import match_province_rules
from .ratio_allocator import allocate_ratio
from .cleanliness_checker import (
    check_all_groups,
    extract_red_flag_majors,
    extract_yellow_flag_majors,
)
from .hidden_threshold_checker import check_all_thresholds
from .volunteer_sorter import sort_volunteers, rank_ratio_to_probability
from .adjustment_guide import generate_all_adjustment_advice
from .slide_prevention import generate_slide_prevention_plan, generate_final_checklist
from .output_formatter import (
    format_volunteer_list,
    format_volunteer_table,
    format_volunteer_segments,
    format_strategy_summary_table,
    format_warnings,
    format_basic_info,
)


def run(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """主入口函数。

    Args:
        input_data: 输入数据，包含：
            - applicant_profile: 考生信息
            - passed_majors: 专业评估模块 输出的专业评估结果
            - recommended_schools: 院校匹配模块 输出的推荐院校
            - eligible_pool: 硬约束过滤模块 输出的可填报基本盘
            - risk_preference: 风险偏好（可选）
            - accept_adjustment: 调剂意愿（可选）
            - target_sprint_schools: 冲刺目标院校（可选）

    Returns:
        完整的志愿填报方案
    """
    try:
        # 1. 输入校验
        input_warnings = validate(input_data)
        
        # 2. 提取输入
        applicant_profile = input_data["applicant_profile"]
        passed_majors = input_data["passed_majors"]
        recommended_schools = input_data["recommended_schools"]
        eligible_pool = input_data["eligible_pool"]
        
        risk_preference = input_data.get("risk_preference", "保守型")
        accept_adjustment = input_data.get("accept_adjustment", "仅接受干净组调剂")
        target_sprint_schools = input_data.get("target_sprint_schools", [])
        
        # 3. 匹配省份规则
        province = applicant_profile["province"]
        application_rules, is_default_rule = get_province_rule_or_default(province)
        
        # 4. 分配冲稳保比例
        max_volunteer_count = application_rules.get("max_volunteer_count", 45)
        strategy_config = allocate_ratio(risk_preference, max_volunteer_count)
        strategy_config["adjustment_strategy"] = "只在干净的专业组勾选服从调剂；不干净的专业组除非分数有绝对优势，否则不要勾选服从调剂"
        
        # 5a. 用 rank_ratio_value 补齐 admission_probability_num（当上游未填或为0时）
        for school in recommended_schools:
            if not school.get("admission_probability_num") and school.get("rank_ratio_value") is not None:
                prob = rank_ratio_to_probability(school["rank_ratio_value"])
                school["admission_probability_num"] = prob
                if not school.get("admission_probability") or school.get("admission_probability") == "未知":
                    school["admission_probability"] = f"约{int(prob * 100)}%"

        # 5b. 冲段数据完整性校验：无 rank_ratio 支撑（或 ratio < 1.20）的"冲"志愿自动降为"稳"
        for school in recommended_schools:
            if school.get("positioning") == "冲":
                ratio = school.get("rank_ratio_value")
                if ratio is None or ratio < 1.20:
                    school["positioning"] = "稳"
                    ratio_str = "无数据" if ratio is None else str(ratio)
                    input_warnings.append(
                        f"⚠️ {school.get('school_name', '')}·{school.get('major_name', '')} "
                        f"标记为冲档但 rank_ratio={ratio_str}（需>1.20），已自动降为稳档"
                    )

        # 5. 检查专业组干净度
        red_flag_majors = extract_red_flag_majors(passed_majors)
        yellow_flag_majors = extract_yellow_flag_majors(passed_majors)
        checked_volunteers = check_all_groups(recommended_schools, red_flag_majors, yellow_flag_majors)
        
        # 6. 核查隐藏门槛
        checked_volunteers = check_all_thresholds(checked_volunteers, applicant_profile)
        
        # 7. 排序志愿
        sorted_volunteers = sort_volunteers(
            checked_volunteers,
            strategy_config,
            target_sprint_schools,
        )
        
        # 8. 生成调剂建议
        adjustment_guide = generate_all_adjustment_advice(
            sorted_volunteers,
            accept_adjustment,
        )
        
        # 9. 生成滑档预案
        slide_prevention_plan = generate_slide_prevention_plan(province, eligible_pool)
        
        # 10. 生成最终确认清单
        final_checklist = generate_final_checklist(max_volunteer_count)
        
        # 11. 格式化输出
        formatted_volunteers = format_volunteer_list(sorted_volunteers)
        volunteer_table = format_volunteer_table(sorted_volunteers)
        volunteer_segments = format_volunteer_segments(sorted_volunteers, strategy_config)
        strategy_summary_table = format_strategy_summary_table(volunteer_segments, strategy_config)
        is_radical = (risk_preference == "激进型")
        warnings = format_warnings(input_warnings, is_default_rule, is_radical)
        
        strategy_tone = "保专业为主" if risk_preference == "保守型" else "冲好学校与保专业兼顾" if risk_preference == "适中型" else "冲好学校为主"
        
        basic_info = format_basic_info(applicant_profile, application_rules, strategy_tone)
        
        # 12. 组装最终结果
        result = {
            "status": "success",
            "basic_info": basic_info,
            "strategy_config": strategy_config,
            "strategy_summary_table": strategy_summary_table,
            "volunteer_list": formatted_volunteers,
            "volunteer_table": volunteer_table,
            "volunteer_segments": volunteer_segments,
            "adjustment_guide": adjustment_guide,
            "slide_prevention_plan": slide_prevention_plan,
            "final_checklist": final_checklist,
            "warnings": warnings,
        }
        
        return result
    
    except StrategyPlannerError as e:
        return {
            "status": "error",
            "error_code": e.error_code,
            "error_message": e.message,
            "user_action_required": e.user_action,
            "error_detail": e.detail,
        }
    except Exception as e:
        return {
            "status": "error",
            "error_code": "RUNTIME_UNEXPECTED_EXCEPTION",
            "error_message": f"生成方案时发生意外错误：{str(e)}",
            "user_action_required": "请将错误信息反馈给维护者",
            "error_detail": {},
        }
