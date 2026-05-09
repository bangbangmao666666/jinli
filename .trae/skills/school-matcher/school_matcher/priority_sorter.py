
"""优先级排序模块。

对院校-专业组合进行排序，优先推荐高价值、匹配度高的院校。
"""


_TIER_ORDER = {"冲": 0, "稳": 1, "保": 2, "极保": 3, "极冲": 4, "unknown": 5}

# 常见行业方向 → 对应专业关键词映射
_DIRECTION_KEYWORD_MAP = {
    "IT":     ["计算机", "软件工程", "信息工程", "网络工程", "数据科学", "人工智能", "大数据", "网络安全", "电子信息"],
    "互联网": ["计算机", "软件工程", "信息工程", "网络工程", "数据科学", "人工智能"],
    "计算机": ["计算机", "软件", "信息工程", "网络"],
    "软件":   ["软件工程", "计算机", "信息"],
    "电力":   ["电气", "电力", "输变电", "能源工程", "电机", "电力系统"],
    "电网":   ["电气", "电力", "输变电", "电机", "电力系统"],
    "电子":   ["电子", "通信工程", "信息工程", "微电子", "光电"],
    "通信":   ["通信工程", "电子信息", "信息与通信"],
    "机械":   ["机械工程", "机械设计", "制造", "车辆工程", "工业工程"],
    "土木":   ["土木工程", "建筑工程", "道路桥梁", "工程管理"],
    "工科":   ["计算机", "软件", "电气", "机械", "土木", "化工", "材料", "电子", "通信", "信息", "自动化"],
    "金融":   ["金融学", "金融工程", "会计", "财务管理", "经济学", "银行"],
    "法律":   ["法学", "法律"],
    "医学":   ["医学", "临床医学", "护理", "药学", "口腔"],
}

# 有行业偏好时，以下专业关键词视为"明显不相关"（按行业分类）
_CLEARLY_IRRELEVANT_BY_DIRECTION = {
    "IT":     ["水土保持", "草坪科学", "园艺", "植物保护", "动物科学", "畜牧", "汉语国际教育", "历史学", "哲学"],
    "互联网": ["水土保持", "草坪科学", "园艺", "植物保护", "动物科学", "汉语国际教育"],
    "计算机": ["水土保持", "草坪科学", "园艺", "汉语国际教育"],
    "电力":   ["水土保持", "草坪科学", "园艺", "汉语国际教育", "历史学", "哲学"],
    "电网":   ["水土保持", "草坪科学", "园艺", "汉语国际教育"],
    "工科":   ["水土保持", "草坪科学", "汉语国际教育", "历史学", "哲学", "社会学"],
}


def sort_recommendations(
    recommendations,
    applicant_profile,
):
    """对推荐列表进行排序。

    排序策略：先按档位分层（冲→稳→保），层内按质量从高到低。
    档位不参与质量打分，避免保档院校因档位惩罚沉底。
    """
    scored = []
    for rec in recommendations:
        tier = rec.get("rank_level", "unknown")
        tier_rank = _TIER_ORDER.get(tier, 99)
        quality = calculate_quality_score(rec, applicant_profile)
        scored.append((tier_rank, -quality, rec))

    scored.sort(key=lambda x: (x[0], x[1]))
    return [item[2] for item in scored]


def calculate_quality_score(rec, applicant_profile):
    """计算院校-专业组合的质量分（不含档位因素）。

    权重分配（2026年优化版：专业评估优先）：
    1. 专业评估标签（40分）— 绿灯(40) > 黄灯(20) > 未知(0)
    2. 专业方向匹配度（20分）— 考生意向行业
    3. 地域适配度（20分）— 考生意向城市/就业地
    4. 整体推荐星级（10分）— 综合结构指标
    5. 经济适配度（5分）— 公办/民办/中外合作
    6. 前置检查（5分）— 用于剔除极端情况
    """
    score = 0.0

    # 1. 专业评估标签（40分）
    light = rec.get("traffic_light", "unknown")
    if light == "green":
        score += 40.0
    elif light == "yellow":
        score += 20.0

    # 2. 专业方向匹配度（20分）
    score += _calculate_direction_score(rec, applicant_profile) * 20.0

    # 3. 地域适配度（20分）
    score += _calculate_region_score(rec, applicant_profile) * 20.0

    # 4. 整体推荐星级（10分）
    star_str = rec.get("overall_rating", "⭐⭐⭐")
    stars = star_str.count("⭐")
    score += stars * 2.0  # 1星2分，5星10分

    # 5. 经济适配度（5分）
    score += _calculate_economic_score(rec) * 5.0

    # 6. 前置检查（5分）
    if rec.get("prerequisite_check", {}).get("passed", True):
        score += 5.0
    else:
        score -= 100.0  # 不通过前置检查直接严重惩罚

    return score


def calculate_score(rec, applicant_profile):
    """兼容旧调用，内部使用质量分。"""
    return calculate_quality_score(rec, applicant_profile)


def _expand_direction_keywords(preferred_industries):
    """将行业名称展开为专业关键词列表。"""
    keywords = set()
    for industry in preferred_industries:
        industry = industry.strip()
        if industry in _DIRECTION_KEYWORD_MAP:
            keywords.update(_DIRECTION_KEYWORD_MAP[industry])
        else:
            # 直接用行业名作为关键词（兜底）
            keywords.add(industry)
    return keywords


def _is_clearly_irrelevant(major_name, preferred_industries):
    """判断专业是否与所有偏好行业都明显不相关。"""
    for industry in preferred_industries:
        industry = industry.strip()
        irrelevant_list = _CLEARLY_IRRELEVANT_BY_DIRECTION.get(industry, [])
        for kw in irrelevant_list:
            if kw in major_name:
                return True
    return False


def _calculate_direction_score(rec, applicant_profile):
    """计算专业方向匹配度（0.0 - 1.0）。

    1.0 = 专业明确匹配考生意向行业
    0.5 = 无偏好设置，中性
    0.3 = 有偏好但未匹配到（方向模糊或无数据）
    0.0 = 专业明确与意向行业不相关
    """
    preferred_industries = applicant_profile.get("preferred_industries", [])
    if not preferred_industries:
        return 0.5

    major_name = rec.get("major_name", "")
    db_hint = rec.get("eight_dimension_evaluation", {}).get("database_hint", {})
    hint_text = " ".join(db_hint.get("hints", []))
    check_text = major_name + " " + hint_text

    direction_keywords = _expand_direction_keywords(preferred_industries)
    for kw in direction_keywords:
        if kw in check_text:
            return 1.0

    if _is_clearly_irrelevant(major_name, preferred_industries):
        return 0.0

    return 0.3


def _calculate_region_score(rec, applicant_profile):
    """计算地域适配度评分。从 city_match.matches_preference 读取。"""
    preferred_cities = applicant_profile.get("preferred_cities", [])
    if not preferred_cities:
        return 0.5

    matches = rec.get("eight_dimension_evaluation", {}).get("city_match", {}).get("matches_preference")
    if matches is True:
        return 1.0
    if matches is False:
        return 0.0
    # None = 城市未知，给中性分
    return 0.4


def _calculate_economic_score(rec):
    """计算经济适配度评分。公办=1.0，民办=0.4，中外合作=0.0。"""
    school_type = rec.get("eight_dimension_evaluation", {}).get("school_nature", {}).get("type", "公办")
    if school_type == "公办":
        return 1.0
    if school_type == "民办":
        return 0.4
    if school_type == "中外合作":
        return 0.0
    return 0.7  # 未知，给中偏上


def get_sort_explanation(rec, applicant_profile):
    """生成排序理由解释。"""
    explanations = []

    rank_level = rec.get("rank_level", "unknown")
    if rank_level != "unknown":
        explanations.append(f"档位：{rank_level}档")

    light = rec.get("traffic_light", "unknown")
    if light == "green":
        explanations.append("专业评估：🟢推荐")
    elif light == "yellow":
        explanations.append("专业评估：🟡有条件推荐")

    preferred_industries = applicant_profile.get("preferred_industries", [])
    if preferred_industries:
        direction_score = _calculate_direction_score(rec, applicant_profile)
        if direction_score >= 1.0:
            explanations.append(f"方向匹配：{rec.get('major_name', '')}")
        elif direction_score == 0.0:
            explanations.append("⚠️ 方向不匹配")

    city_match = rec.get("eight_dimension_evaluation", {}).get("city_match", {})
    city = city_match.get("city", "")
    matches = city_match.get("matches_preference")
    if matches is True and city:
        explanations.append(f"意向城市：{city}")
    elif matches is False and city:
        explanations.append(f"非意向城市：{city}")

    school_type = rec.get("eight_dimension_evaluation", {}).get("school_nature", {}).get("type", "公办")
    if school_type != "公办":
        explanations.append(f"办学性质：{school_type}")

    if not explanations:
        return "综合评估排序"

    return "；".join(explanations)

