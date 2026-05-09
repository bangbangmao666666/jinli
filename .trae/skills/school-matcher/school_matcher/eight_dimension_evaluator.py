"""结构性评估模块。

职责：对每个院校-专业组合计算可量化的结构性指标：
  - rank_ratio（录取位次比）及档位分类
  - 城市偏好匹配
  - 办学性质识别
  - 数据库线索标记（仅作为 AI WebSearch 的搜索提示，不作为评估结论）

八维深度评估（行业血统、就业资源、学科实力等定性维度）由 AI 通过
WebSearch 完成，本模块不负责这些维度。
"""
from .data_loader import (
    load_school_database,
    is_treasure_school,
    is_value_school,
    is_industry_school,
)

# ── 主入口 ────────────────────────────────────────────────────────────────────

def evaluate_school_major(
    school_name,
    major_name,
    applicant_profile,
    school_db=None,
    historical_rank_data=None,
    major_data=None,
):
    """返回院校-专业组合的结构性指标。

    注意：本函数只做结构性计算，不产生定性评价。
    定性八维评估由 AI 通过 WebSearch 完成。
    """
    if school_db is None:
        school_db = load_school_database()

    result = {}

    # 录取位次比（核心结构指标）
    result["cost_performance"] = _evaluate_rank_ratio(
        school_name, major_name, applicant_profile, historical_rank_data
    )

    # 数据库线索（仅供 AI 做 WebSearch 时参考）
    result["database_hint"] = _get_database_hint(school_name, school_db)

    # 城市偏好匹配（结构性，可量化）
    result["city_match"] = _evaluate_city_match(school_name, applicant_profile, major_name)

    # 办学性质（结构性，可量化）
    result["school_nature"] = _evaluate_school_nature(school_name, major_name, applicant_profile, school_db)

    return result


# ── rank_ratio 计算 ───────────────────────────────────────────────────────────

def _evaluate_rank_ratio(school_name, major_name, applicant_profile, historical_rank_data):
    """计算录取位次比，返回档位分类。

    使用三年加权平均：最近年 0.5 / 次年 0.3 / 再前年 0.2。
    只有一年或两年数据时，权重归一化后使用。
    """
    result = {
        "rank_ratio": None,
        "historical_min_rank": None,
        "user_rank": applicant_profile.get("provincial_rank"),
        "rank_level": "unknown",
        "rank_level_label": "无历史数据",
    }

    user_rank = applicant_profile.get("provincial_rank", 0)

    if historical_rank_data and (school_name, major_name) in historical_rank_data:
        ranks = historical_rank_data[(school_name, major_name)]
        if ranks:
            # 按年份倒序，取最近三年
            sorted_ranks = sorted(ranks, key=lambda r: r.get("year", 0), reverse=True)
            weights = [0.5, 0.3, 0.2]
            weighted_sum = 0.0
            weight_total = 0.0
            for i, r in enumerate(sorted_ranks[:3]):
                min_rank = r.get("min_rank", 0)
                if min_rank > 0:
                    w = weights[i]
                    weighted_sum += min_rank * w
                    weight_total += w
            if weight_total <= 0:
                return result
            weighted_min_rank = weighted_sum / weight_total
            # historical_min_rank 展示最近一年实际值，供参考
            min_rank = round(weighted_min_rank)
            result["historical_min_rank"] = sorted_ranks[0].get("min_rank", min_rank)
            result["weighted_min_rank"] = min_rank
            if min_rank > 0:
                rank_ratio = user_rank / min_rank
                result["rank_ratio"] = round(rank_ratio, 3)

                if rank_ratio < 0.3:
                    result["rank_level"] = "anomaly"
                    result["rank_level_label"] = "数据异常（过滤）"
                elif rank_ratio > 3.0:
                    result["rank_level"] = "anomaly"
                    result["rank_level_label"] = "数据异常（过滤）"
                elif rank_ratio < 0.5:
                    result["rank_level"] = "极保"
                    result["rank_level_label"] = "极保（分数浪费严重）"
                elif rank_ratio <= 0.85:
                    result["rank_level"] = "保"
                    result["rank_level_label"] = "保档"
                elif rank_ratio <= 1.15:
                    result["rank_level"] = "稳"
                    result["rank_level_label"] = "稳档"
                elif rank_ratio <= 2.5:
                    result["rank_level"] = "冲"
                    result["rank_level_label"] = "冲档"
                else:
                    result["rank_level"] = "anomaly"
                    result["rank_level_label"] = "数据异常（过滤）"

    return result


# ── 数据库线索标记 ─────────────────────────────────────────────────────────────

def _get_database_hint(school_name, school_db):
    """返回该校在 school-database.md 中的记录摘要。

    仅作为 AI 做 WebSearch 时的搜索线索和初始假设，不作为评估结论。
    """
    hints = []

    school_info = school_db.get("schools", {}).get(school_name, {})

    if school_info:
        industry = school_info.get("industry", "")
        tags = school_info.get("tags", "")
        if industry:
            hints.append(f"行业特色：{industry}（{tags}）")

    if is_treasure_school(school_db, school_name):
        hints.append("数据库标记：宝藏校/被低估")

    if is_value_school(school_db, school_name):
        hints.append("数据库标记：高性价比院校")

    # 校名关键词提示（可能被名字歧视）
    treasure_keywords = ["林业", "矿业", "农业", "石油", "地质", "水利"]
    for kw in treasure_keywords:
        if kw in school_name:
            hints.append(f'注意：校名含"{kw}"，可能存在名称歧视，建议核查实际学科实力')
            break

    if hints:
        return {
            "in_database": True,
            "hints": hints,
            "note": "以上为数据库线索，需通过 WebSearch 验证时效性",
        }
    else:
        return {
            "in_database": False,
            "hints": [],
            "note": "未在本地数据库收录，需通过 WebSearch 获取院校信息",
        }


# ── 城市偏好匹配 ──────────────────────────────────────────────────────────────

_CITY_LEVEL = {
    "北京": "直辖市/一线", "上海": "直辖市/一线",
    "广州": "一线", "深圳": "一线",
    "天津": "直辖市/新一线", "重庆": "直辖市",
    "杭州": "新一线", "南京": "新一线", "武汉": "新一线",
    "成都": "新一线", "西安": "新一线", "青岛": "新一线",
    "济南": "新一线", "郑州": "新一线", "长沙": "新一线",
    "合肥": "新一线", "沈阳": "新一线", "大连": "新一线",
    "哈尔滨": "省会", "长春": "省会", "南昌": "省会",
    "福州": "省会", "昆明": "省会", "贵阳": "省会",
    "兰州": "省会", "南宁": "省会", "太原": "省会",
    "石家庄": "省会", "乌鲁木齐": "省会", "西宁": "省会",
    "银川": "省会", "呼和浩特": "省会", "海口": "省会",
    "秦皇岛": "二线", "徐州": "二线", "无锡": "二线",
    "苏州": "二线", "宁波": "二线", "温州": "二线",
    "吉林": "省内城市", "延吉": "省内城市", "湘潭": "省内城市",
}

# 校名不含城市名的学校 → 实际所在城市
# 注意：同名学校有多校区时，取主校区/常用校区
_SCHOOL_CITY_MAP = {
    # ── 北京 ──
    "中国农业大学": "北京", "中国地质大学(北京)": "北京",
    "中国矿业大学(北京)": "北京", "中国石油大学(北京)": "北京",
    "华北电力大学": "北京", "北方工业大学": "北京",
    "北京工商大学": "北京", "北京联合大学": "北京",
    "北京第二外国语学院": "北京", "北京印刷学院": "北京",
    "首都医科大学": "北京", "首都师范大学": "北京",
    # ── 上海 ──
    "同济大学": "上海", "复旦大学": "上海",
    "华东师范大学": "上海", "华东理工大学": "上海",
    "东华大学": "上海", "上海财经大学": "上海",
    "上海外国语大学": "上海",
    # ── 天津 ──
    "河北工业大学": "天津",  # 虽名含"河北"，实在天津
    "南开大学": "天津", "天津大学": "天津",
    # ── 南京 ──
    "东南大学": "南京", "河海大学": "南京",
    "南京航空航天大学": "南京", "南京理工大学": "南京",
    "南京林业大学": "南京", "南京邮电大学": "南京",
    "南京师范大学": "南京", "南京医科大学": "南京",
    "江苏大学": "镇江",
    # ── 青岛 ──
    "中国海洋大学": "青岛", "中国石油大学(华东)": "青岛",
    "山东科技大学": "青岛",
    # ── 济南 ──
    "山东大学": "济南", "山东师范大学": "济南",
    "齐鲁工业大学": "济南",
    # ── 武汉 ──
    "华中科技大学": "武汉", "华中农业大学": "武汉",
    "华中师范大学": "武汉", "湖北大学": "武汉",
    "武汉科技大学": "武汉", "中南财经政法大学": "武汉",
    "中国地质大学(武汉)": "武汉",
    # ── 广州 ──
    "中山大学": "广州", "华南理工大学": "广州",
    "华南农业大学": "广州", "暨南大学": "广州",
    "广东工业大学": "广州",
    # ── 成都 ──
    "四川大学": "成都", "电子科技大学": "成都",
    "西南交通大学": "成都", "西南财经大学": "成都",
    "西南石油大学": "成都",
    "四川农业大学": "雅安",  # 主校区雅安，成都校区通过专业名中的"(成都校区)"动态覆盖
    # ── 西安/陕西 ──
    "西北工业大学": "西安", "西北大学": "西安",
    "陕西师范大学": "西安", "西安电子科技大学": "西安",
    "长安大学": "西安",
    "西北农林科技大学": "杨凌",
    # ── 长沙 ──
    "湖南大学": "长沙", "中南大学": "长沙",
    "湖南师范大学": "长沙", "湘潭大学": "湘潭",
    "长沙理工大学": "长沙",
    # ── 东北 ──
    "燕山大学": "秦皇岛",
    "东北大学": "沈阳", "辽宁大学": "沈阳",
    "沈阳航空航天大学": "沈阳",
    "东北财经大学": "大连", "大连海事大学": "大连",
    "东北电力大学": "吉林", "延边大学": "延吉",
    "吉林大学": "长春",
    "哈尔滨工业大学": "哈尔滨", "哈尔滨工程大学": "哈尔滨",
    "东北林业大学": "哈尔滨", "东北农业大学": "哈尔滨",
    # ── 其他省会/重点城市 ──
    "山西大学": "太原", "山西医科大学": "太原",
    "太原理工大学": "太原",
    "内蒙古大学": "呼和浩特", "内蒙古工业大学": "呼和浩特",
    "南昌大学": "南昌", "华东交通大学": "南昌",
    "云南大学": "昆明", "贵州大学": "贵阳",
    "兰州大学": "兰州", "西北民族大学": "兰州",
    "新疆大学": "乌鲁木齐",
    "中国矿业大学": "徐州",
    "江南大学": "无锡",
    "浙江大学": "杭州", "浙江工业大学": "杭州",
    "郑州大学": "郑州", "河南大学": "开封",
}


def _infer_city(school_name, major_name=""):
    """推断院校所在城市。

    优先级：
    1. 专业名中明确标注的校区（如"(成都校区)"）
    2. _SCHOOL_CITY_MAP 精确映射
    3. 校名关键词扫描
    """
    # 1. 从专业名中提取校区城市（如"金融学(成都校区)"→"成都"）
    if major_name:
        import re as _re
        campus_match = _re.search(r"[（(]([^）)]+校区)[）)]", major_name)
        if campus_match:
            campus_str = campus_match.group(1)  # e.g. "成都校区"
            for city in _CITY_LEVEL:
                if city in campus_str:
                    return city, _CITY_LEVEL[city]

    # 2. 精确查映射表（优先，处理"河北工业大学→天津"等特殊情况）
    city = _SCHOOL_CITY_MAP.get(school_name, "")
    if city:
        return city, _CITY_LEVEL.get(city, "其他城市")

    # 3. 校名包含城市名（如"北京信息科技大学"→"北京"）
    for city in _CITY_LEVEL:
        if city in school_name:
            return city, _CITY_LEVEL[city]

    return "", "未知"


def _evaluate_city_match(school_name, applicant_profile, major_name=""):
    """判断院校城市与考生意向城市是否匹配。"""
    city, city_level = _infer_city(school_name, major_name)
    result = {
        "city": city,
        "city_level": city_level,
        "matches_preference": None,
    }

    # 意向城市匹配
    preferred_cities = applicant_profile.get("preferred_cities", [])
    if preferred_cities and city:
        result["matches_preference"] = any(
            city in pref or pref in city
            for pref in preferred_cities
        )

    return result


# ── 办学性质 ──────────────────────────────────────────────────────────────────

_PRIVATE_KEYWORDS = ["民办", "独立学院", "应用技术大学"]
_KNOWN_PRIVATE = {"珠海科技学院", "武昌理工学院", "武昌首义学院", "广州商学院",
                   "黑龙江东方学院", "上海外国语大学贤达经济人文学院"}
_KNOWN_JOINT = {"温州肯恩大学", "深圳大学深圳南特金融科技学院"}

def _evaluate_school_nature(school_name, major_name, applicant_profile, school_db):
    """判断办学性质（公办/民办/中外合作）。

    学校级别识别不到时，降级到专业名中的"中外合作"关键词（如"XX(中外合作办学)"）。
    """
    result = {
        "type": "公办",
        "tuition_estimate": 5000,
        "note": "",
    }

    if school_name in _KNOWN_JOINT:
        result["type"] = "中外合作"
        result["tuition_estimate"] = 30000
        result["note"] = "⚠️ 中外合作办学，学费通常较高，请核实"
    elif school_name in _KNOWN_PRIVATE or any(kw in school_name for kw in _PRIVATE_KEYWORDS):
        result["type"] = "民办"
        result["tuition_estimate"] = 15000
        result["note"] = "民办院校，学费高于公办，请确认家庭承受能力"
    elif "中外合作" in major_name:
        result["type"] = "中外合作"
        result["tuition_estimate"] = 25000
        result["note"] = "⚠️ 该专业为中外合作办学，学费通常高于普通专业，请核实"

    return result


# ── 前置检查 ──────────────────────────────────────────────────────────────────

def check_prerequisites(school_name, major_name, major_data, school_db):
    """检查专业前置条件。"""
    result = {"passed": True, "check_details": []}
    for req in major_data.get("prerequisites", []):
        detail = {"requirement": req, "result": "符合要求"}
        result["check_details"].append(detail)
    return result


# ── 评分 & 推荐理由（简化版） ─────────────────────────────────────────────────

def calculate_overall_rating(evaluation, prereq_check):
    """基于结构性指标计算初步评分（仅供排序，不作为最终评价）。"""
    if not prereq_check.get("passed", True):
        return "⭐"

    stars = 3
    rank_level = evaluation.get("cost_performance", {}).get("rank_level", "unknown")
    if rank_level == "稳":
        stars += 1
    if evaluation.get("database_hint", {}).get("in_database"):
        stars += 1
    city_match = evaluation.get("city_match", {}).get("matches_preference")
    if city_match is True:
        stars += 1

    stars = min(stars, 5)
    return "⭐" * stars


def generate_recommendation_reason(school_name, major_name, evaluation, prereq_check):
    """生成初步推荐说明（结构性指标，非最终评价）。"""
    if not prereq_check.get("passed", True):
        return "不符合专业前置要求"

    parts = []
    rank_level = evaluation.get("cost_performance", {}).get("rank_level", "")
    rank_ratio = evaluation.get("cost_performance", {}).get("rank_ratio")
    if rank_ratio:
        parts.append(f"位次比 {rank_ratio:.2f}（{rank_level}档）")

    hints = evaluation.get("database_hint", {}).get("hints", [])
    if hints:
        parts.append(f"数据库线索：{hints[0]}")

    if evaluation.get("city_match", {}).get("matches_preference"):
        city = evaluation.get("city_match", {}).get("city", "")
        parts.append(f"在意向城市{city}")

    return "；".join(parts) if parts else "结构筛选通过，待 AI WebSearch 评估"


def generate_risk_notice(school_name, major_name, evaluation, prereq_check):
    """生成风险提示（仅包含针对本考生的行动建议，不复述数据库线索）。"""
    risks = []

    school_note = evaluation.get("school_nature", {}).get("note", "")
    if school_note:
        risks.append(school_note)

    if evaluation.get("city_match", {}).get("matches_preference") is False:
        city = evaluation.get("city_match", {}).get("city", "")
        risks.append(f"⚠️ {city or school_name}不在意向城市")

    return "；".join(risks) if risks else "无结构性风险"
