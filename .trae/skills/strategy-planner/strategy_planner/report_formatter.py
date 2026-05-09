"""志愿填报策略方案 Markdown 报告格式化。"""
from __future__ import annotations

from typing import Any, Dict, List


def format_report(result: Dict[str, Any]) -> str:
    if result.get("status") != "success":
        return _format_error(result)

    lines: List[str] = []
    basic_info = result.get("basic_info", {})
    strategy_config = result.get("strategy_config", {})
    strategy_summary_table = result.get("strategy_summary_table", [])
    volunteer_table = result.get("volunteer_table", [])
    volunteer_list = result.get("volunteer_list", [])
    adjustment_guide = result.get("adjustment_guide", {})
    slide_prevention_plan = result.get("slide_prevention_plan", {})
    final_checklist = result.get("final_checklist", [])
    warnings = result.get("warnings", [])

    applicant = basic_info.get("applicant_summary", {})
    app_rule = basic_info.get("application_rule", {})
    province = applicant.get("province", "")
    score = applicant.get("total_score", "")
    rank = applicant.get("provincial_rank", "")
    subjects = "、".join(applicant.get("selected_subjects", []))

    # 标题
    lines.append("# 志愿填报策略方案")
    lines.append("")
    lines.append(f"**考生**：{province} · {score}分 · 位次{rank} · {subjects}")
    lines.append(f"**策略基调**：{strategy_config.get('risk_preference', '保守型')}（{basic_info.get('strategy_tone', '')}）")
    lines.append("")
    
    # 核心名词解释（突出显示）
    lines.append("## 核心概念说明")
    lines.append("")
    lines.append("### 1. 位次比 (rank_ratio) —— 衡量“准入难度”")
    lines.append("> **公式**：位次比 = 考生当前位次 / 院校往年录取位次加权平均")
    lines.append("> - **< 1.0**：你的位次优于平均门槛（分等人），录取极稳。")
    lines.append("> - **1.0 - 1.2**：你在门槛附近（人等分），属于主力稳档区间。")
    lines.append("> - **1.2 - 1.5**：你落后于门槛（需捡漏），属于冲刺区间。")
    lines.append("")
    lines.append("### 2. 录取概率 —— 衡量“安全程度”")
    lines.append("> **计算口径**：系统采用“分段线性插值法”，基于位次比(rank_ratio)进行阶梯映射：")
    lines.append("> - **极稳 (rank_ratio ≤ 0.70)**：录取概率固定为 **97%**。")
    lines.append("> - **稳妥 (0.70 < rank_ratio ≤ 1.00)**：概率 = 97% - (rank_ratio - 0.70) / 0.30 * 17%。 (落在 80%-97% 之间)")
    lines.append("> - **适中 (1.00 < rank_ratio ≤ 1.20)**：概率 = 80% - (rank_ratio - 1.00) / 0.20 * 20%。 (落在 60%-80% 之间)")
    lines.append("> - **冲刺 (1.20 < rank_ratio ≤ 1.50)**：概率 = 60% - (rank_ratio - 1.20) / 0.30 * 30%。 (落在 30%-60% 之间)")
    lines.append("> - **极冲 (rank_ratio > 1.50)**：概率 = 30% - (rank_ratio - 1.50) * 50% (最低不低于 5%)。")
    lines.append("> ")
    lines.append("> *注：位次比每增加 0.1，在稳档区间概率约下降 10%，在冲档区间概率约下降 10%。*")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    lines.append(f"> ⚠️ {basic_info.get('risk_warning', '')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 一、策略总配置
    lines.append("## 一、策略总配置")
    lines.append("")
    if strategy_summary_table:
        lines.append("| 志愿段 | 数量占比 | 对应志愿数 | 录取概率区间 | 核心方向 | 参考院校 |")
        lines.append("|--------|---------|----------|------------|--------|--------|")
        tier_icon = {"冲段": "🎯", "稳段": "✅", "保段": "🔒"}
        for row in strategy_summary_table:
            seg = row.get("志愿段", "")
            icon = tier_icon.get(seg, "")
            lines.append(
                f"| {icon} {seg} | {row.get('数量占比','')} | {row.get('对应志愿数','')} "
                f"| {row.get('录取概率区间','')} | {row.get('核心报考方向','')} "
                f"| {row.get('参考院校举例','')} |"
            )
    lines.append("")
    lines.append(f"**调剂策略**：{strategy_config.get('adjustment_strategy', '')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 二、完整志愿顺序
    lines.append("## 二、完整志愿顺序")
    lines.append("")
    if volunteer_table:
        lines.append("| 序号 | 志愿类型 | 学校名称 | 专业名称 | rank_ratio | 录取概率 | 专业组干净度 |")
        lines.append("|:---:|:------:|---------|--------|:----------:|---------|-----------|")
        type_icon = {"冲": "🎯冲", "稳": "✅稳", "保": "🔒保"}
        for row in volunteer_table:
            v_type = row.get("志愿类型", "")
            ratio = row.get("rank_ratio")
            ratio_str = str(ratio) if ratio is not None else "暂无数据"
            lines.append(
                f"| {row.get('序号','')} | {type_icon.get(v_type, v_type)} "
                f"| {row.get('学校名称','')} | {row.get('专业名称','')} "
                f"| {ratio_str} | {row.get('录取概率','')} | {row.get('专业组干净度','')} |"
            )
    lines.append("")
    lines.append("---")
    lines.append("")

    # 三、各志愿说明
    lines.append("## 三、各志愿风险说明")
    lines.append("")
    for v in volunteer_list:
        sn = v.get("serial_number", "")
        school = v.get("school_name", "")
        major = v.get("major_name", "")
        v_type = v.get("positioning", "")
        prob = v.get("admission_probability", "")
        risk = v.get("risk_desc", "")
        cleanliness = v.get("major_group_cleanliness", "")
        threshold = v.get("hidden_threshold_check", "")

        type_icon = {"冲": "🎯", "稳": "✅", "保": "🔒"}
        icon = type_icon.get(v_type, "")
        lines.append(f"### 志愿{sn}：{icon}{v_type} · {school} — {major}")
        lines.append("")
        lines.append(f"- **录取概率**：{prob}")
        lines.append(f"- **专业组干净度**：{cleanliness}")
        if risk:
            lines.append(f"- **风险提示**：{risk}")
        if threshold:
            lines.append(f"- **隐藏门槛核查**：{threshold}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # 四、服从调剂说明
    lines.append("## 四、服从调剂说明")
    lines.append("")
    lines.append(f"**总原则**：{adjustment_guide.get('general_principle', '')}")
    lines.append("")
    adj_list = adjustment_guide.get("adjustment_suggestion_list", [])
    if adj_list:
        lines.append("| 序号 | 学校名称 | 调剂建议 | 原因 |")
        lines.append("|:---:|---------|---------|------|")
        for item in adj_list:
            sug = item.get("suggestion", "")
            sug_icon = "✅ " if "建议勾选" in sug else "❌ "
            lines.append(
                f"| {item.get('serial_number','')} | {item.get('school_name','')} "
                f"| {sug_icon}{sug} | {item.get('reason','')} |"
            )
    lines.append("")
    lines.append("---")
    lines.append("")

    # 五、滑档预案
    lines.append("## 五、滑档预案")
    lines.append("")
    lines.append(slide_prevention_plan.get("description", ""))
    lines.append("")
    for step in slide_prevention_plan.get("plan_steps", []):
        lines.append(step)
    backup = slide_prevention_plan.get("backup_schools", [])
    if backup:
        lines.append("")
        backup_labels = [
            f"{s['school_name']}-{s['major_name']}" if isinstance(s, dict) else str(s)
            for s in backup
        ]
        lines.append("**备选兜底院校**：" + "、".join(backup_labels))
    lines.append("")
    lines.append("---")
    lines.append("")

    # 六、填报前确认清单
    lines.append("## 六、填报前最终确认清单")
    lines.append("")
    for item in final_checklist:
        lines.append(item)
    lines.append("")
    lines.append("---")
    lines.append("")

    # 七、警告
    lines.append("## ⚠️ 重要提示")
    lines.append("")
    for w in warnings:
        lines.append(f"- {w}")
    lines.append("")

    # 数据说明
    lines.append("---")
    lines.append("")
    lines.append("> **数据说明**：本方案基于历史录取数据生成，录取概率为估算值。")
    lines.append(f"> 填报规则：{app_rule.get('volunteer_mode', '')} · 最多可填 {app_rule.get('max_volunteer_count', '')} 个志愿")
    if app_rule.get("data_source"):
        lines.append(f"> 数据来源：{app_rule.get('data_source', '')}")

    return "\n".join(lines)


def _format_error(result: Dict[str, Any]) -> str:
    code = result.get("error_code", "UNKNOWN")
    msg = result.get("error_message", "未知错误")
    action = result.get("user_action_required", "")
    lines = [
        "# 填报策略生成失败",
        "",
        f"**错误码**：`{code}`",
        f"**错误信息**：{msg}",
    ]
    if action:
        lines += ["", f"**需要您做**：{action}"]
    return "\n".join(lines)
