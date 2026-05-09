"""院校匹配结果 Markdown 报告格式化。

输出两部分：
  1. 结构性筛选候选表（Python 计算，含 rank_ratio / 档位 / 城市 / 数据库线索）
  2. AI 评估区（空白占位，由 AI 通过 WebSearch 补充八维深度评估）

设计说明：
  Python 脚本只做"量"的工作——从数千条录取数据中过滤出 rank_ratio 合理的
  院校-专业候选池；定性的八维评估（行业血统、就业资源、学科实力等）需要
  有时效性的网络信息，由 AI 通过 WebSearch 完成。
"""
from __future__ import annotations
import json
from typing import Any, Dict, List, Optional


_SEPARATOR = "=" * 60

_TIER_LABEL = {
    "冲":   "【冲档】录取概率约 30–50%",
    "稳":   "【稳档】录取概率约 50–80%（主力区间）",
    "保":   "【保档】录取概率 80%+（兜底）",
    "极冲": "【极冲】录取概率偏低，谨慎填报",
    "极保": "【极保】录取概率极高，分数浪费明显",
    "unknown": "【无历史数据】",
}


# ── 主入口 ─────────────────────────────────────────────────────────────────────

def format_report(
    result: Dict[str, Any],
    applicant_profile: Optional[Dict[str, Any]] = None,
) -> str:
    if result.get("status") != "success":
        return _format_error(result)

    lines: List[str] = []
    recommendations = result.get("recommendations", [])
    generated_at = result.get("generated_at", "")
    input_summary = result.get("input_summary", {})

    # 标题
    lines.append("# 院校匹配候选池（第一阶段：结构性筛选）")
    lines.append("")
    if generated_at:
        lines.append(f"> 生成时间：{generated_at}")
    lines.append("")
    lines.append("> **什么是位次比（rank_ratio）？**")
    lines.append("> 位次比 = 考生当前位次 / 院校往年录取位次加权平均。")
    lines.append("> - **< 1.0**：考生位次优于历史录取位次（保档/极保，录取几率极高）。")
    lines.append("> - **1.0 - 1.2**：考生位次接近历史录取位次（稳档，主力区间）。")
    lines.append("> - **1.2 - 1.5**：考生位次差于历史录取位次（冲档，有录取机会但需搏一搏）。")
    lines.append("> - **> 1.5**：考生位次远差于历史录取位次（极冲，录取几率极低）。")
    lines.append("")
    lines.append("> **说明**：本报告为结构性筛选结果，包含通过 rank_ratio 过滤的院校-专业候选池。")
    lines.append("> **八维深度评估**（行业血统、就业资源、学科实力等）需由 AI 通过 WebSearch 完成，")
    lines.append("> 详见本报告末尾的「AI 评估待办」区。")
    lines.append("")

    # 考生信息
    if applicant_profile:
        lines.append(_SEPARATOR)
        lines.append("## 考生信息")
        lines.append(_SEPARATOR)
        lines.extend(_format_profile(applicant_profile))
        lines.append("")

    # 筛选统计
    lines.append(_SEPARATOR)
    lines.append("## 筛选统计")
    lines.append(_SEPARATOR)
    lines.extend(_format_stats(input_summary, recommendations))
    lines.append("")

    # 按专业分组输出候选表
    recommendations_by_major = _group_by_major(recommendations)
    
    for major_name, major_recs in recommendations_by_major.items():
        lines.append(_SEPARATOR)
        lines.append(f"# 专业：{major_name}")
        lines.append(_SEPARATOR)
        lines.append("")
        
        # 该专业内部按档位分组
        tiers_data = _group_by_tier(major_recs)
        for tier in ("冲", "稳", "保", "极保", "极冲", "unknown"):
            entries = tiers_data.get(tier, [])
            if not entries:
                continue
            label = _TIER_LABEL.get(tier, f"【{tier}】")
            lines.append(f"### {label} ({len(entries)}个)")
            lines.append("")
            lines.extend(_format_tier_table(entries))
            lines.append("")

    # AI 评估待办区
    lines.append(_SEPARATOR)
    lines.append("## AI 评估待办（第二阶段）")
    lines.append(_SEPARATOR)
    lines.append("")
    lines.extend(_format_ai_todo(recommendations, applicant_profile))
    lines.append("")

    # 填报建议
    lines.append(_SEPARATOR)
    lines.append("## 使用说明")
    lines.append(_SEPARATOR)
    lines.extend(_format_tips())

    # 元数据埋点 (Hidden Metadata for Downstream 模块)
    # PRD §2.4 补丁：通过隐藏 JSON 块将 硬约束过滤模块/2 的关键数据传递给 填报策略模块
    metadata = {
        "passed_majors": result.get("passed_majors", []),
        "eligible_pool": result.get("eligible_pool", []),
    }
    metadata_json = json.dumps(metadata, ensure_ascii=False)
    lines.append("")
    lines.append(f"<!-- METADATA_START {metadata_json} METADATA_END -->")

    return "\n".join(lines)


# ── 格式化子函数 ───────────────────────────────────────────────────────────────

def _format_error(result: Dict[str, Any]) -> str:
    code = result.get("error_code", "未知错误")
    msg = result.get("error_message", "")
    action = result.get("user_action_required", "")
    lines = [
        "# 院校匹配失败",
        "",
        f"**错误码**：`{code}`",
        f"**错误信息**：{msg}",
    ]
    if action:
        lines.append(f"**建议操作**：{action}")
    return "\n".join(lines)


def _format_profile(profile: Dict[str, Any]) -> List[str]:
    province = profile.get("province", "未知")
    score = profile.get("total_score", "未知")
    rank = profile.get("provincial_rank", "未知")
    gender = profile.get("gender", "未知")
    subjects = profile.get("selected_subjects", [])
    subject_str = " + ".join(subjects) if subjects else profile.get("subject_category", "未知")
    preferred_cities = profile.get("preferred_cities", [])
    target_system = profile.get("target_system", "")

    lines = [
        f"- 省份：{province}",
        f"- 总分：{score}分  位次：{rank}",
        f"- 性别：{gender}  选科：{subject_str}",
    ]
    if preferred_cities:
        lines.append(f"- 意向城市：{'、'.join(preferred_cities)}")
    if target_system:
        lines.append(f"- 就业倾向：{target_system}")
    return lines


def _format_stats(input_summary: Dict[str, Any], recommendations: List[Dict[str, Any]]) -> List[str]:
    total = input_summary.get("total_school_major_combinations", len(recommendations))
    tier_counts: Dict[str, int] = {}
    for r in recommendations:
        t = r.get("rank_level", "unknown")
        tier_counts[t] = tier_counts.get(t, 0) + 1

    lines = [
        f"- 候选院校-专业组合：{total} 个",
        f"- 推荐结果：{len(recommendations)} 个",
        "",
        "**档位分布**：",
    ]
    for tier, label in [("冲", "冲档"), ("稳", "稳档"), ("保", "保档"),
                         ("极冲", "极冲"), ("极保", "极保"), ("unknown", "无历史数据")]:
        cnt = tier_counts.get(tier, 0)
        if cnt:
            lines.append(f"  - {label}：{cnt} 个")
    return lines


def _group_by_tier(recommendations: List[Dict[str, Any]]) -> Dict[str, List]:
    groups: Dict[str, List] = {}
    for rec in recommendations:
        tier = rec.get("rank_level", "unknown")
        groups.setdefault(tier, []).append(rec)
    return groups


def _group_by_major(recommendations: List[Dict[str, Any]]) -> Dict[str, List]:
    """按专业分组。"""
    groups: Dict[str, List] = {}
    for rec in recommendations:
        major = rec.get("major_name", "未知专业")
        groups.setdefault(major, []).append(rec)
    return groups


def _format_tier_table(entries: List[Dict[str, Any]]) -> List[str]:
    """输出档位候选表格。"""
    lines = [
        "| 学校 | 专业 | 位次比 | 录取概率 | 历史最低位次 | 城市 | 数据库线索 | 风险提示 |",
        "|------|------|--------|----------|------------|------|-----------|---------|",
    ]
    for rec in entries:
        school = rec.get("school_name", "")
        major = rec.get("major_name", "")

        # 优先使用上游传入的位次比数据，不重算
        rank_ratio = rec.get("rank_ratio_value")
        ratio_str = f"{rank_ratio:.2f}" if rank_ratio is not None else "—"

        prob_str = "未知"
        if rank_ratio is not None:
            if rank_ratio < 0.5:
                prob_str = "极高(>99%)"
            elif rank_ratio <= 0.85:
                prob_str = "兜底(90%+)"
            elif rank_ratio <= 0.95:
                prob_str = "安全(80%+)"
            elif rank_ratio <= 1.05:
                prob_str = "较稳(60-80%)"
            elif rank_ratio <= 1.15:
                prob_str = "适中(50-60%)"
            elif rank_ratio <= 1.5:
                prob_str = "冲刺(30-50%)"
            else:
                prob_str = "极冲(<30%)"

        hist_rank = rec.get("historical_min_rank")
        hist_str = str(hist_rank) if hist_rank else "—"

        city_info = rec.get("eight_dimension_evaluation", {}).get("city_match", {})
        city = city_info.get("city", "") or rec.get("city", "") or "—"

        db_hint = rec.get("eight_dimension_evaluation", {}).get("database_hint", {})
        hints = db_hint.get("hints", [])
        hint_str = hints[0][:20] if hints else "—"

        risk = rec.get("risk_notice", "")
        risk_str = risk[:20] if risk and risk != "无结构性风险" else "—"

        lines.append(f"| {school} | {major} | {ratio_str} | {prob_str} | {hist_str} | {city} | {hint_str} | {risk_str} |")
    return lines


def _format_ai_todo(recommendations: List[Dict[str, Any]], applicant_profile) -> List[str]:
    """生成 AI WebSearch 评估待办清单。

    各档位配额：冲 5 / 稳 15 / 保 20，共 40 条；
    与 strategy-planner 的候选需求对齐（山东省 45 个志愿位）。
    某档位不足时用其他档位补足，保档优先级最低不得低于实际配额上限。
    """
    # 按档位分组，每组内已按质量排好序（sort_recommendations 保证）
    by_tier: Dict[str, List] = {}
    for rec in recommendations:
        tier = rec.get("rank_level", "unknown")
        by_tier.setdefault(tier, []).append(rec)

    # 配额与 strategy-planner 所需候选数对齐：冲 5 / 稳 15 / 保 20
    # 每档内部已由 sort_recommendations 按质量从高到低排序，相对质量好的优先出现。
    # 同一学校在整个 40 条清单中最多出现 PER_SCHOOL_CAP 次，避免单校垄断。
    PER_SCHOOL_CAP = 3
    quota = {"冲": 5, "稳": 15, "保": 20}
    top_picks: List = []
    leftover: List = []
    school_count: Dict[str, int] = {}

    def _try_add(rec) -> bool:
        school = rec.get("school_name", "")
        if school_count.get(school, 0) >= PER_SCHOOL_CAP:
            return False
        top_picks.append(rec)
        school_count[school] = school_count.get(school, 0) + 1
        return True

    for tier, limit in quota.items():
        pool = by_tier.get(tier, [])
        added = 0
        for rec in pool:
            if added >= limit:
                leftover.append(rec)
            elif _try_add(rec):
                added += 1
            else:
                leftover.append(rec)

    # 配额不足 40 条时，用剩余院校按档位顺序补足（仍受同校上限约束）
    if len(top_picks) < 40:
        leftover_sorted = sorted(
            leftover,
            key=lambda r: ({"冲": 0, "稳": 1, "保": 2}.get(r.get("rank_level", ""), 9),),
        )
        for rec in leftover_sorted:
            if len(top_picks) >= 40:
                break
            _try_add(rec)

    preferred_cities = (applicant_profile or {}).get("preferred_cities", [])
    target_system = (applicant_profile or {}).get("target_system", "")

    lines = [
        "以下为建议优先评估的院校-专业组合（按冲档→稳档→保档排序，档内按质量从高到低，取前40条）。",
        "配额：冲 5 / 稳 15 / 保 20，与 strategy-planner 生成完整志愿方案所需候选数对齐。",
        "同一档内靠前的是综合质量更高的选项（绝对优先），靠后的是该档位内相对较好的选项（相对优先）。",
        "",
        "## ⛔ 强制执行规则（违反则本次评估无效）",
        "",
        "**规则 1：输出卡片数量必须等于清单条数（约 40 条），不得减少。**",
        "strategy-planner 依赖完整候选池生成 45 个志愿位方案；候选池缩减到 10-15 条会导致",
        "志愿方案只有个位数，考生面临滑档风险。",
        "",
        "**规则 2：「与考生画像不符」不是跳过评估的理由。**",
        "每条必须输出完整八维评估表（8 行全填）。若认为某条不适合，",
        "在「综合判断」标注 ❌ 并说明原因即可——但不得用一行总结替代整张评估卡。",
        "strategy-planner 需要完整数据自行决策，school-matcher 不代替它做取舍。",
        "",
        "**规则 3：禁止自行替换或新增未在清单中的院校。**",
        "如发现清单质量差（如大量非目标专业），在报告末尾「风险提示」中说明，",
        "并建议用户重新运行第一阶段并传入专业偏好参数，而不是直接绕过清单。",
        "",
        "**规则 4：必须提供专业延展与真实信源链接。**",
        "在每张匹配卡的「综合判断」部分，必须新增两项：",
        "1. **适合报的专业列表**：结合用户的意向，列出该校同样值得该考生填报的其他相关专业。",
        "2. **参考文档链接**：将八维评估中用到的核心数据来源（如官网就业质量报告、软科学科排名页面等），以可点击的真实 URL 形式集中列出，方便用户核对。",
        "",
        "AI 需对每条执行 WebSearch，按八维框架（行业血统、性价比、名实反差、",
        "深造通道、就业资源、学科认可、办学性质、城市环境）给出有来源标注的评估结论。",
        "",
    ]
    if preferred_cities:
        lines.append(f"> 考生意向城市：{', '.join(preferred_cities)}")
    if target_system:
        lines.append(f"> 就业倾向：{target_system}")
    lines.append("")

    # ── 信源质量强制规则（嵌入文件，AI 读取时必须遵守）────────────────────────
    lines.append("### ⚠️ 信源质量规则（执行 WebSearch 前必读）")
    lines.append("")
    lines.append("**数字型数据**（就业率、薪资、升学率、学科评估等级等）来源分两级：")
    lines.append("")
    lines.append("✅ **官方来源（首选）**，须附具体可访问的 URL：")
    lines.append("1. 院校官网信息公开/就业中心发布的就业质量报告（`xxgk.<校>.edu.cn` 或 `jy.<校>.edu.cn`）")
    lines.append("2. 省级教育厅官方发布数据（`edu.<省>.gov.cn`）")
    lines.append("3. 教育部阳光高考平台（`gaokao.chsi.com.cn`）")
    lines.append("4. 软科官网（`shanghairanking.cn`）、教育部学位中心（`cdgdc.edu.cn`）")
    lines.append("5. 权威媒体（新华社/人民日报/中国教育报）引用院校官方数据的报道（需能追溯原始来源）")
    lines.append("")
    lines.append("⚠️ **参考来源（可用，必须标注不可靠信源）**：")
    lines.append("- 今日头条/头条教育、搜狐/网易/腾讯教育频道、大学生必备网、高考100、掌上高考等")
    lines.append("- 知乎/百度贴吧/小红书等 UGC 内容（口碑描述须注明「口碑参考」）")
    lines.append("- 以上来源数字必须以参考格式输出：`参考数字：约XX%（⚠️ 来源：[媒体名]，不可靠信源，仅供参考）`")
    lines.append("")
    lines.append("**信源使用规则**：")
    lines.append("1. 优先搜索官方来源，找到则以官方格式输出（含具体 URL）")
    lines.append("2. 官方来源未找到时：先标注 `⚠️ 数据不足：未找到官方就业质量报告`，然后引用参考来源数字（参考格式）")
    lines.append("3. 官方来源和参考来源都搜不到时：输出 `⚠️ 数据不足：暂无可引用数据`")
    lines.append("4. 禁止用训练知识直接给出数字——所有数字必须来自 WebSearch")
    lines.append("")
    lines.append("**格式示例**：")
    lines.append("- ✅ 官方：`就业率87.26%（🌐 [东北电力大学2024届就业质量报告](https://jy.neepu.edu.cn/...)，2024）`")
    lines.append("- ✅ 参考：`⚠️ 数据不足：未找到官方报告 URL｜参考数字：约87%（⚠️ 来源：大学生必备网，不可靠信源，仅供参考）`")
    lines.append("- ❌ 禁止：直接给出数字不标来源（用训练知识编造）")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── 待评估院校清单 ──────────────────────────────────────────────────────────
    lines.append("### 待评估院校清单（AI 必须基于此清单评估，禁止自行替换）")
    lines.append("")
    lines.append("| 优先级 | 学校 | 专业 | 档位 | 位次比 | 录取概率 | 专业评估 | 数据库线索 |")
    lines.append("|--------|------|------|------|--------|----------|----------|-----------|")
    for i, rec in enumerate(top_picks, 1):
        school = rec.get("school_name", "")
        major = rec.get("major_name", "")
        tier = rec.get("rank_level", "")
        rank_ratio = rec.get("rank_ratio_value")
        ratio_str = f"{rank_ratio:.2f}" if rank_ratio is not None else "—"

        prob_str = "未知"
        if rank_ratio is not None:
            if rank_ratio < 0.5:
                prob_str = "极高(>99%)"
            elif rank_ratio <= 0.85:
                prob_str = "兜底(90%+)"
            elif rank_ratio <= 0.95:
                prob_str = "安全(80%+)"
            elif rank_ratio <= 1.05:
                prob_str = "较稳(60-80%)"
            elif rank_ratio <= 1.15:
                prob_str = "适中(50-60%)"
            elif rank_ratio <= 1.5:
                prob_str = "冲刺(30-50%)"
            else:
                prob_str = "极冲(<30%)"

        db_hint = rec.get("eight_dimension_evaluation", {}).get("database_hint", {})
        hints = db_hint.get("hints", [])
        hint_str = " / ".join(hints)[:40] if hints else "未在数据库收录"
        tier_badge = {"冲": "🎯冲", "稳": "✅稳", "保": "🔒保"}.get(tier, tier)
        light = rec.get("traffic_light", "unknown")
        light_badge = {"green": "🟢推荐", "yellow": "🟡有条件"}.get(light, "—")
        lines.append(f"| {i} | {school} | {major} | {tier_badge} | {ratio_str} | {prob_str} | {light_badge} | {hint_str} |")

    lines.append("")
    lines.append("### 搜索词模板（优先官方来源，未找到时引用参考来源并标注）")
    lines.append("1. `site:<校名拼音>.edu.cn 就业质量报告 2024`（院校官网直搜，优先级最高）")
    lines.append("2. `<学校名> 信息公开 就业质量报告 2024`（找信息公开页面）")
    lines.append("3. `<学校名> <专业名> 学科评估 site:cdgdc.edu.cn`（教育部学位中心）")
    lines.append("4. `<学校名> 软科排名 site:shanghairanking.cn`（软科官网）")
    lines.append("5. 以上均无结果 → 搜索 `<学校名> <专业名> 就业率` 引用媒体/聚合站数据，以参考格式标注")

    return lines


def _format_tips() -> List[str]:
    return [
        "1. **本报告为第一阶段输出**：rank_ratio 过滤确保录取可行性，八维质量评估由 AI WebSearch 完成",
        "2. **数据库线索仅供参考**：标注「数据库线索」的内容来自静态知识库，可能有时效性问题，需 WebSearch 验证",
        "3. **所有位次数据为历史数据**：基于 2024 年录取数据，2026 年可能有波动，实际填报请核查近 3 年趋势",
        "4. **精选推荐卡应覆盖**：冲 5 个 / 稳 15 个 / 保 20 个，共约 40 条，供 strategy-planner 生成完整志愿方案（山东省上限 45 个）",
        "5. **务必核查官方招生计划**：以 2026 年官方发布数据为准",
    ]
