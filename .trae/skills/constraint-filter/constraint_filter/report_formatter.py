"""过滤结果格式化输出（Markdown 报告）。

将 pipeline.run() 的结构化 JSON 转换为考生可直接阅读的 Markdown 报告。

用法：
    from constraint_filter.report_formatter import format_report
    report = format_report(result)
    print(report)

或通过 main.py --report 参数调用。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


# ── 常量 ─────────────────────────────────────────────────────────────────────

_TIER_LABEL = {
    "冲":   "【冲档】录取概率约 30-50%，建议少量填报（1-3个）",
    "稳":   "【稳档】录取概率约 50-80%，建议重点填报（4-6个）",
    "保":   "【保档】录取概率 80%+，建议必填兜底（2-4个）",
}

_SEPARATOR = "=" * 60

# ── 专业评估预判数据（前置自 major-evaluator） ───────────────────────────────────
# 基于张雪峰方法论与行业现状的初步标记
_MAJOR_ADVICE = {
    "法学": "🔴 高资源依赖专业。普通家庭在律所就业受人脉影响大，考公是主要出路。",
    "临床医学": "🔴 高资源依赖、长培养周期。三甲医院门槛极高，规培期长，需家庭经济支撑。",
    "口腔医学": "🔴 长培养周期。民办学费极高，公办竞争激烈，就业市场相对较好但入门慢。",
    "金融学": "🔴 强名校/资源依赖。非顶级名校毕业，在头部机构竞争力有限。",
    "投资学": "🔴 强名校/资源依赖。非顶级名校毕业，在头部机构竞争力有限。",
    "金融工程": "🔴 强名校/资源依赖。非顶级名校毕业，在头部机构竞争力有限。",
    "土木工程": "⚠️ 行业下行风险。建筑业收缩，工作环境艰苦，本科就业起薪及环境不乐观。",
    "生物工程": "⚠️ 就业红牌风险。本科就业对口率低，普遍需要硕博深造才有出路。",
    "生物技术": "⚠️ 就业红牌风险。本科就业对口率低，普遍需要硕博深造才有出路。",
    "软件工程": "🟢 宽口径、高起薪。虽然加班压力大，但对普通家庭是改变命运的优质通道。",
    "计算机科学与技术": "🟢 宽口径、高起薪。底层基础扎实，容错率高，就业面极广。",
    "电气工程及其自动化": "🟢 体制内导向。电网招录主战场，稳定且待遇好，地域性强。",
}


# ── 主入口 ────────────────────────────────────────────────────────────────────

def format_report(result: Dict[str, Any], max_rows_per_tier: int = 9999) -> str:
    """将 pipeline 结果转为 Markdown 格式报告。

    Args:
        result: pipeline.run() 返回的字典（status == "success"）
        max_rows_per_tier: 每个档位最多展示的行数（避免报告过长）

    Returns:
        Markdown 字符串。如果 result.status != "success"，返回错误摘要。
    """
    if result.get("status") != "success":
        return _format_error(result)

    lines: List[str] = []
    profile = result.get("applicant_profile", {})
    stats = result.get("stats", {})
    warnings = result.get("warnings", [])
    all_detail = result.get("all_majors_detail", [])
    data_version = result.get("data_snapshot_version", "未知")

    # 提取数据年份（从 version 字段）
    data_year = _extract_year(data_version) or "未知"

    # ── 数据说明 ──
    lines.append(f"⚠️ 数据说明：以下筛选基于【{data_year}年】招生录取数据，非当年官方数据。"
                 "实际填报请以当年官方发布为准。")
    lines.append("")

    # ── 考生画像 ──
    lines.append(_SEPARATOR)
    lines.append("考生画像")
    lines.append(_SEPARATOR)
    lines.extend(_format_profile(profile))
    lines.append("")

    # ── 专业方向概览（前置 logic） ──
    lines.append(_SEPARATOR)
    lines.append("可选专业方向概览")
    lines.append(_SEPARATOR)
    lines.append("基于您的硬约束条件，系统为您筛选出了以下核心专业方向（按出现频率排序）：")
    lines.append("")
    lines.extend(_format_major_overview(all_detail))
    lines.append("")
    lines.append("> 💡 **提示**：以上概览帮您快速识别“基本盘”里的热门方向。您可以选定 3-5 个感兴趣的方向，后续将进行深度评估。")
    lines.append("")

    # ── 核心逻辑说明（计算公式） ──
    lines.append(_SEPARATOR)
    lines.append("冲稳保算法说明 (rank_ratio)")
    lines.append(_SEPARATOR)
    lines.append("系统通过 **位次比 (rank_ratio)** 来判断录取概率：")
    lines.append("")
    lines.append("> **公式**：`rank_ratio = 考生位次 ÷ 历史录取最低位次加权平均`")
    lines.append("> *注：加权平均权重为：最近一年(50%)、次年(30%)、前三年(20%)。*")
    lines.append("")
    lines.append("数值含义：")
    lines.append("- **ratio ≤ 1.00 (保)**：考生位次优于/等于历史线，录取概率极高。")
    lines.append("- **1.00 < ratio ≤ 1.20 (稳)**：考生位次在历史线附近，大概率可录取。")
    lines.append("- **1.20 < ratio ≤ 1.50 (冲)**：考生位次略差于历史线，建议作为冲刺志愿尝试。")
    lines.append("- **ratio > 1.50 (极冲)**：风险极高，默认不建议填报。")
    lines.append("")

    # ── Warnings ──
    if warnings:
        lines.append(_SEPARATOR)
        lines.append("注意事项")
        lines.append(_SEPARATOR)
        for w in warnings:
            lines.append(f"⚠️  {w}")
        lines.append("")

    # ── 过滤统计 ──
    lines.append(_SEPARATOR)
    lines.append("过滤结果总览")
    lines.append(_SEPARATOR)
    lines.extend(_format_stats(stats, all_detail))
    lines.append("")

    # ── 分档展示 ──
    tiers_data = _group_by_tier(all_detail)
    for tier in ("冲", "稳", "保"):
        entries = tiers_data.get(tier, [])
        if not entries:
            continue
        label = _TIER_LABEL[tier]
        lines.append(_SEPARATOR)
        lines.append(label)
        lines.append(_SEPARATOR)
        lines.extend(_format_tier_table(entries, max_rows=max_rows_per_tier))
        lines.append("")

    # ── 体检排除 ──
    physical_excluded = [
        d for d in all_detail
        if d.get("status") == "excluded" and d.get("exclude_dimension") == "体检"
    ]
    if physical_excluded:
        lines.append(_SEPARATOR)
        lines.append(f"【体检排除】因体检条件被排除的专业（共 {len(physical_excluded)} 个）")
        lines.append(_SEPARATOR)
        lines.extend(_format_physical_excluded(physical_excluded))
        lines.append("")

    # ── Unknown ──
    unknown_entries = [d for d in all_detail if d.get("status") == "eligible" and d.get("rank_tier") == "unknown"]
    if unknown_entries:
        lines.append(_SEPARATOR)
        lines.append(f"【无历史数据档】共 {len(unknown_entries)} 个专业")
        lines.append(_SEPARATOR)
        lines.append("以下专业通过选科和体检过滤，但缺少往年录取位次数据，无法判断冲/稳/保：")
        lines.append("（多为新设专业、军校特殊专业或招生计划中名称与历史数据不一致的条目）")
        lines.append("")
        for d in unknown_entries[:30]:
            lines.append(f"- {d['school_name']} · {d['major_name'][:60]}")
        if len(unknown_entries) > 30:
            lines.append(f"... 等共 {len(unknown_entries)} 个专业")
        lines.append("")

    # ── 使用建议 ──
    lines.append(_SEPARATOR)
    lines.append("使用建议")
    lines.append(_SEPARATOR)
    lines.extend(_format_tips(profile, all_detail))

    return "\n".join(lines)


# ── 格式化子函数 ──────────────────────────────────────────────────────────────

def _format_error(result: Dict[str, Any]) -> str:
    code = result.get("error_code", "未知错误")
    msg = result.get("error_message", "")
    action = result.get("user_action_required", "")
    lines = [
        "## 过滤失败",
        f"**错误码**：`{code}`",
        f"**错误信息**：{msg}",
    ]
    if action:
        lines.append(f"**建议操作**：{action}")
    return "\n".join(lines)


def _format_profile(profile: Dict[str, Any]) -> List[str]:
    lines = []
    lines.append(f"省份：{profile.get('province', '未知')}")
    lines.append(f"性别：{profile.get('gender', '未知')}")
    lines.append(f"总分：{profile.get('total_score', '未知')}分")

    subjects = profile.get("selected_subjects") or []
    lines.append(f"选科：{' + '.join(subjects) if subjects else profile.get('subject_category', '未知')}")
    lines.append(f"位次：{profile.get('provincial_rank', '未知')} 名")

    exam = profile.get("physical_exam") or {}
    if exam:
        parts = []
        cv = exam.get("color_vision", "") or exam.get("color_blindness", "")
        if cv:
            parts.append(cv)
        vl = exam.get("vision_left")
        vr = exam.get("vision_right")
        if vl is not None and vr is not None:
            parts.append(f"视力左{vl}/右{vr}")
        h = exam.get("height_cm") or exam.get("height")
        if h:
            parts.append(f"身高{h}cm")
        if parts:
            lines.append(f"体检：{', '.join(parts)}")
    return lines


def _format_major_overview(all_detail: List[Dict[str, Any]]) -> List[str]:
    import re
    from collections import Counter
    
    eligible_majors = [d.get("major_name", "") for d in all_detail if d.get("status") == "eligible"]
    base_majors = []
    for m in eligible_majors:
        # 移除括号内容，如“计算机科学与技术(中外合作)” -> “计算机科学与技术”
        base_name = re.sub(r'[\(（].*?[\)）]', '', m).strip()
        if base_name:
            base_majors.append(base_name)
            
    counter = Counter(base_majors)
    top_categories = counter.most_common(20)
    
    if not top_categories:
        return ["暂无可选专业方向。"]
        
    lines = [
        "| 专业方向 | 院校数量 | 初步评估建议 |",
        "|---------|---------|-------------|",
    ]
    for name, count in top_categories:
        advice = _MAJOR_ADVICE.get(name, "—")
        lines.append(f"| {name} | {count}所 | {advice} |")
        
    if len(counter) > 20:
        lines.append(f"\n*共涵盖 {len(counter)} 个细分专业方向，此处仅列出 Top 20。*")
        
    return lines


def _format_stats(stats: Dict[str, Any], all_detail: List[Dict[str, Any]]) -> List[str]:
    total = stats.get("total_majors_in_plan", 0)
    passed = stats.get("total_majors_after_filter", 0)

    # 档位分布
    tier_counts: Dict[str, int] = {}
    for d in all_detail:
        if d.get("status") == "eligible":
            t = d.get("rank_tier") or "unknown"
            tier_counts[t] = tier_counts.get(t, 0) + 1

    # 排除原因
    excl_counts: Dict[str, int] = {}
    for d in all_detail:
        if d.get("status") == "excluded":
            dim = d.get("exclude_dimension", "其他")
            excl_counts[dim] = excl_counts.get(dim, 0) + 1

    lines = [
        f"招生计划总专业数：{total}",
        f"通过硬约束的专业数：{passed}",
    ]
    for tier in ("冲", "稳", "保", "unknown"):
        cnt = tier_counts.get(tier, 0)
        if cnt:
            label = {"冲": "冲档", "稳": "稳档", "保": "保档", "unknown": "无历史数据（unknown）"}.get(tier, tier)
            lines.append(f"  - {label}：{cnt} 个")
    lines.append("")
    lines.append("排除原因分布：")
    for dim, cnt in sorted(excl_counts.items(), key=lambda x: -x[1]):
        lines.append(f"  - {dim}：{cnt} 个专业")
    return lines


def _group_by_tier(all_detail: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    result: Dict[str, List[Dict[str, Any]]] = {}
    for d in all_detail:
        if d.get("status") == "eligible":
            tier = d.get("rank_tier")
            if tier and tier != "unknown":
                result.setdefault(tier, []).append(d)
    # 每个档位按 rank_ratio 降序排列（最接近门槛的排前面）
    for tier in result:
        result[tier].sort(
            key=lambda d: (d.get("rank_ratio") or 0),
            reverse=(tier in ("冲", "稳")),  # 冲/稳：ratio 越大越危险，排前
        )
    return result


def _format_tier_table(entries: List[Dict[str, Any]], max_rows: int = 25) -> List[str]:
    import re
    lines = [
        "| 学校 | 专业 | rank_ratio | 历史最低位次 | 预警/建议 |",
        "|------|------|-----------|-------------|----------|",
    ]
    for d in entries[:max_rows]:
        school = d.get("school_name", "")
        major = d.get("major_name", "")
        ratio = d.get("rank_ratio")
        ratio_str = f"{ratio:.2f}" if ratio is not None else "—"

        # 从 yearly_admission_data 取最近一年的最低位次
        yearly = d.get("yearly_admission_data") or []
        if yearly:
            latest = sorted(yearly, key=lambda r: r.get("year", 0), reverse=True)[0]
            rank_str = f"{latest.get('min_rank', '?')}（{latest.get('year', '?')}）"
        else:
            rank_str = "—"

        # 专业评估建议提取
        base_name = re.sub(r'[\(（].*?[\)）]', '', major).strip()
        advice = _MAJOR_ADVICE.get(base_name, "—")
        if advice != "—":
            # 简化建议，只取前面的标记
            advice_short = advice.split("。")[0]
        else:
            advice_short = "—"

        # 专业名截断，避免表格过宽
        major_display = major[:40] + "..." if len(major) > 40 else major
        lines.append(f"| {school} | {major_display} | {ratio_str} | {rank_str} | {advice_short} |")

    if len(entries) > max_rows:
        lines.append(f"\n... 还有 {len(entries) - max_rows} 个专业未显示")
    return lines


def _format_physical_excluded(excluded: List[Dict[str, Any]]) -> List[str]:
    lines = ["以下专业因体检限制被排除：", ""]
    seen = set()
    for d in excluded:
        key = (d.get("school_name"), d.get("major_name"))
        if key in seen:
            continue  # 去重
        seen.add(key)
        school = d.get("school_name", "")
        major = d.get("major_name", "")[:60]
        reason = d.get("exclude_reason", "")
        lines.append(f"- {school} · {major}")
        if reason:
            lines.append(f"  {reason}")
    return lines


def _format_tips(profile: Dict[str, Any], all_detail: List[Dict[str, Any]]) -> List[str]:
    lines = [
        "1. 冲稳保比例建议：冲 15% / 稳 50% / 保 35%",
    ]
    # 体检相关提示
    exam = profile.get("physical_exam") or {}
    vl = exam.get("vision_left", 99)
    vr = exam.get("vision_right", 99)
    if min(vl, vr) < 4.8:
        lines.append("2. 视力低于4.8：飞行技术、航海技术、轮机工程等专业已被自动排除")
    if exam.get("color_vision", "").startswith(("色盲", "色弱")):
        lines.append("   色觉异常：化工、医学影像、临床医学等部分专业已被排除")
    # unknown 提示
    unknown_cnt = sum(1 for d in all_detail if d.get("status") == "eligible" and d.get("rank_tier") == "unknown")
    if unknown_cnt > 0:
        lines.append(
            f"3. 无历史数据的 {unknown_cnt} 个专业需谨慎：建议查阅学校官网或致电招生办核实往年录取情况"
        )
    lines.append("4. 所有数据为历史年份，实际分数线每年有波动，请以官方发布为准")
    return lines


def _extract_year(version: str) -> Optional[str]:
    """从 version 字符串中提取四位年份。"""
    import re
    m = re.search(r"(\d{4})", version or "")
    return m.group(1) if m else None
