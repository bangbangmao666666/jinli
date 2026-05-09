
"""输出格式化模块。

按照PRD要求的格式生成输出。
"""
import datetime

# 主要城市列表，用于从校名中提取城市（兜底方案）
_KNOWN_CITIES = [
    "北京", "上海", "广州", "深圳", "天津", "重庆",
    "杭州", "南京", "武汉", "成都", "西安", "沈阳",
    "大连", "哈尔滨", "长春", "青岛", "济南", "郑州",
    "长沙", "合肥", "南昌", "福州", "厦门", "南宁",
    "昆明", "贵阳", "兰州", "西宁", "乌鲁木齐", "银川",
    "太原", "石家庄", "南通", "苏州", "无锡", "宁波",
    "温州", "绍兴", "徐州", "扬州", "锦州", "湛江",
    "宜昌", "衡阳", "泸州", "雅安", "镇江", "芜湖",
]


def _extract_city_from_school_name(school_name: str) -> str:
    """从校名中提取城市名（用于 school_city 字段为空时的兜底）。"""
    for city in _KNOWN_CITIES:
        if city in school_name:
            return city
    return ""

from .errors import MatcherError
from .input_validator import validate
from .data_loader import (
    load_school_database,
    load_historical_ranks,
)
from .eight_dimension_evaluator import (
    evaluate_school_major,
    check_prerequisites,
    calculate_overall_rating,
    generate_recommendation_reason,
    generate_risk_notice,
)
from .priority_sorter import sort_recommendations


def format_output(data, warnings, data_dir=None):
    """格式化输出。

    处理流水线模式或单查询模式的输入。
    """
    try:
        # 检查是否是流水线模式
        if "eligible_pool" in data and "passed_majors" in data:
            return format_pipeline_output(data, warnings, data_dir)
        else:
            # 单查询模式
            return format_single_query_output(data, warnings, data_dir)
    except MatcherError as e:
        return e.to_response()
    except Exception as e:
        return {
            "status": "error",
            "error_code": "RUNTIME_UNEXPECTED_EXCEPTION",
            "error_category": "runtime",
            "error_message": "未预期异常：{}".format(e),
            "error_detail": {},
            "user_action_required": "请将完整错误信息反馈给维护者",
            "partial_result": None,
        }


def format_pipeline_output(data, warnings, data_dir=None):
    """格式化流水线模式输出。"""
    eligible_pool = data.get("eligible_pool", [])
    passed_majors = data.get("passed_majors", [])
    applicant_profile = data.get("applicant_profile", {})
    selected_majors = data.get("selected_majors", [])  # 新增：用户选择的专业

    # 加载数据
    school_db = load_school_database()
    province = applicant_profile.get("province", "")
    exam_year = applicant_profile.get("exam_year", 2026)
    historical_rank_data = load_historical_ranks(province, exam_year)

    # 收集所有需要评估的院校-专业组合
    school_major_combinations = extract_combinations(eligible_pool, passed_majors, selected_majors)

    # 评估每个组合
    recommendations = []
    for combo in school_major_combinations:
        rec = evaluate_combination(
            combo,
            applicant_profile,
            school_db,
            historical_rank_data,
            passed_majors,
        )
        recommendations.append(rec)

    # 统计数据覆盖情况
    coverage_stats = calculate_coverage_stats(recommendations)

    # 排序
    sorted_recommendations = sort_recommendations(recommendations, applicant_profile)

    # 生成全局警告
    global_warnings = []
    global_warnings.extend(warnings)
    global_warnings.append("⚠️ 本次推荐基于本地院校数据库，请以官方信息为准")

    # 统计输入信息
    input_summary = {
        "total_majors_from_专业评估": len(passed_majors),
        "total_school_major_combinations": len(school_major_combinations),
        "passed_prerequisite_check": sum(1 for r in recommendations if r.get("prerequisite_check", {}).get("passed", False)),
        "filtered_by_user_preference": 0,
    }

    return {
        "status": "success",
        "generated_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "data_version": "school-database-v1.0",
        "input_summary": input_summary,
        "coverage_stats": coverage_stats,
        "recommendations": sorted_recommendations,
        "passed_majors": passed_majors,  # 新增：透传专业评估结果
        "eligible_pool": eligible_pool,  # 新增：透传可填报基本盘
        "global_warnings": global_warnings,
        "urgent_todos": [],
    }


def format_single_query_output(data, warnings, data_dir=None):
    """格式化单查询模式输出。"""
    school_name = data.get("school_name", "")
    major_name = data.get("major_name", "")
    applicant_profile = data.get("applicant_profile", {})

    # 加载数据
    school_db = load_school_database()
    province = applicant_profile.get("province", "")
    exam_year = applicant_profile.get("exam_year", 2026)
    historical_rank_data = load_historical_ranks(province, exam_year)

    # 评估单个组合
    combo = {"school_name": school_name, "major_name": major_name}
    passed_majors = [{"major_name": major_name, "traffic_light": "green", "prerequisites": []}]
    rec = evaluate_combination(
        combo,
        applicant_profile,
        school_db,
        historical_rank_data,
        passed_majors,
    )

    # 统计数据覆盖情况
    coverage_stats = calculate_coverage_stats([rec])

    # 生成输出
    return {
        "status": "success",
        "generated_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "data_version": "school-database-v1.0",
        "input_summary": {
            "total_majors_from_专业评估": 1,
            "total_school_major_combinations": 1,
            "passed_prerequisite_check": 1 if rec.get("prerequisite_check", {}).get("passed", False) else 0,
            "filtered_by_user_preference": 0,
        },
        "coverage_stats": coverage_stats,
        "recommendations": [rec],
        "passed_majors": passed_majors,
        "eligible_pool": [],  # 单查询模式无 pool
        "global_warnings": warnings,
        "urgent_todos": [],
    }


def extract_combinations(eligible_pool, passed_majors, selected_majors=None):
    """从基本盘和通过的专业中提取组合。

    Args:
        eligible_pool: 基本盘数据
        passed_majors: 专业评估模块 评估通过的专业列表
        selected_majors: 用户明确选择的专业名称列表（可选）
    """
    combinations = []
    selected_majors = selected_majors or []

    # 获取通过的专业名称集合
    passed_major_names = set()
    for major in passed_majors:
        if "major_name" in major:
            passed_major_names.add(major["major_name"])

    # 如果有用户选择的专业，以用户选择为准
    filter_set = set(selected_majors) if selected_majors else passed_major_names

    # 遍历基本盘，提取组合
    for school in eligible_pool:
        school_name = school.get("school_name", "")
        school_city = school.get("school_city", "")

        for group in school.get("major_groups", []):
            for major in group.get("majors", []):
                major_name = major.get("major_name", "")

                # 只有在过滤集合中的专业才被评估
                # 如果没有 passed_majors 也没有 selected_majors，则评估所有（兜底）
                if not filter_set or major_name in filter_set:
                    raw_tier = major.get("rank_ratio_tier", "未知")
                    # 统一映射为单字格式，与 report_formatter 期望的 key 一致
                    _TIER_MAP = {"冲档": "冲", "稳档": "稳", "保档": "保",
                                 "极冲档": "极冲", "极保档": "极保"}
                    rank_level = _TIER_MAP.get(raw_tier, raw_tier)
                    combinations.append({
                        "school_name": school_name,
                        "school_city": school_city,
                        "major_name": major_name,
                        "rank_level": rank_level,
                        "rank_ratio_value": major.get("rank_ratio_value"),
                        "historical_min_rank": major.get("historical_min_rank"),
                    })

    return combinations


def evaluate_combination(
    combo,
    applicant_profile,
    school_db,
    historical_rank_data,
    passed_majors,
):
    """评估单个院校-专业组合。"""
    school_name = combo.get("school_name", "")
    major_name = combo.get("major_name", "")

    # 八维评估
    evaluation = evaluate_school_major(
        school_name,
        major_name,
        applicant_profile,
        school_db,
        historical_rank_data,
    )

    # 查找该专业的数据
    major_data = {}
    for major in passed_majors:
        if major.get("major_name") == major_name:
            major_data = major
            break

    # 前置检查
    prereq_check = check_prerequisites(
        school_name,
        major_name,
        major_data,
        school_db,
    )

    # 整体评分
    overall_rating = calculate_overall_rating(evaluation, prereq_check)

    # 推荐理由
    rec_reason = generate_recommendation_reason(
        school_name,
        major_name,
        evaluation,
        prereq_check,
    )

    # 风险提示
    risk_notice = generate_risk_notice(
        school_name,
        major_name,
        evaluation,
        prereq_check,
    )

    # 确定数据覆盖情况
    data_coverage, data_coverage_detail = determine_data_coverage(evaluation)

    # 确定排名等级（从新的 cost_performance 结构读取）
    rank_level = (
        combo.get("rank_level")
        or evaluation.get("cost_performance", {}).get("rank_level", "unknown")
    )

    # 确定学校类型和学费
    school_type = evaluation.get("school_nature", {}).get("type", "公办")
    tuition = evaluation.get("school_nature", {}).get("tuition_estimate", 5000)

    # 交通灯状态（专业评估模块 评估结论）
    traffic_light = major_data.get("traffic_light", "unknown")

    # 城市：优先从 city_match 取，其次从基本盘，再从校名解析
    city = (
        evaluation.get("city_match", {}).get("city", "")
        or combo.get("school_city", "")
        or _extract_city_from_school_name(school_name)
    )

    return {
        "school_name": school_name,
        "city": city,
        "major_name": major_name,
        "school_type": school_type,
        "tuition_per_year": tuition,
        "data_coverage": data_coverage,
        "data_coverage_detail": data_coverage_detail,
        "eight_dimension_evaluation": evaluation,
        "prerequisite_check": prereq_check,
        "overall_rating": overall_rating,
        "recommendation_reason": rec_reason,
        "risk_notice": risk_notice,
        "rank_level": rank_level,
        "rank_ratio_value": combo.get("rank_ratio_value"),
        "historical_min_rank": combo.get("historical_min_rank"),
        "traffic_light": traffic_light,
    }


def determine_data_coverage(evaluation):
    """确定数据覆盖情况。"""
    detail = evaluation.get("data_coverage_detail", {})

    # 统计各维度的覆盖情况
    covered = 0
    partial = 0
    insufficient = 0
    total = len(detail)

    for key, value in detail.items():
        if value == "covered":
            covered += 1
        elif value == "partial":
            partial += 1
        else:
            insufficient += 1

    # 确定整体覆盖情况
    if total == 0:
        data_coverage = "partial"
    elif covered == total:
        data_coverage = "full"
    elif insufficient == total:
        data_coverage = "insufficient"
    else:
        data_coverage = "partial"

    return data_coverage, detail


def calculate_coverage_stats(recommendations):
    """计算数据覆盖统计。"""
    full = 0
    partial = 0
    insufficient = 0

    for rec in recommendations:
        coverage = rec.get("data_coverage", "")
        if coverage == "full":
            full += 1
        elif coverage == "partial":
            partial += 1
        else:
            insufficient += 1

    total = len(recommendations)
    coverage_rate = f"{round(full / total * 100)}%" if total > 0 else "0%"

    return {
        "full_coverage": full,
        "partial_coverage": partial,
        "no_coverage": insufficient,
        "coverage_rate": coverage_rate,
    }


def print_pretty_output(output):
    """打印友好格式的输出。"""
    import json

    print(json.dumps(output, ensure_ascii=False, indent=2))

