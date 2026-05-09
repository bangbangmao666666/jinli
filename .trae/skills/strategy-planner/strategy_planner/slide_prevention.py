"""滑档预案生成模块。

生成滑档后的应急处理方案。
"""
from __future__ import annotations

from typing import Any, Dict, List


def generate_slide_prevention_plan(
    province: str,
    eligible_pool: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """生成滑档预案。"""
    # 从基本盘中筛选出往年有缺额的院校作为备选
    backup_schools = _extract_backup_schools(eligible_pool)
    
    plan = {
        "description": "如果所有志愿均未录取的应急方案",
        "plan_steps": [
            "1. 出分后提前了解本省征集志愿时间安排和填报规则",
            "2. 提前整理本批次录取分数较低、往年有缺额的院校专业清单，作为补录备选",
            "3. 一旦滑档，立即在征集志愿时间内填报，优先选择有缺额的公办院校好专业",
            "4. 如本批次无合适征集志愿，可考虑下一批次或复读，根据家庭情况决定",
        ],
        "backup_schools": backup_schools,
        "province": province,
    }
    
    return plan


def _extract_backup_schools(eligible_pool: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """从基本盘中提取备选院校。"""
    # 这里简化处理，实际应该根据历史缺额数据筛选
    backup = []
    for school in eligible_pool:
        # 优先选择录取概率高的、省内的、公办的
        prob = school.get("admission_probability_num", 0)
        if prob >= 0.9:
            backup.append({
                "school_name": school.get("school_name", ""),
                "major_name": school.get("major_name", ""),
                "admission_probability": school.get("admission_probability", "未知"),
            })
    
    # 限制数量
    return backup[:20]


def generate_final_checklist(volunteer_count: int) -> List[str]:
    """生成最终确认清单。"""
    return [
        "☐ 所有志愿的招生章程已核查（单科成绩要求、体检限制、专业级差、外语语种要求等）",
        "☐ 每个专业组的所有专业都已逐一确认，无不可接受的天坑专业",
        "☐ 服从调剂按钮已按上述建议设置，没有在不干净的专业组误勾",
        "☐ 志愿顺序已严格按冲→稳→保排列，没有排反",
        "☐ 保段+补充志愿合计达到45个左右，重点是依据筛选结果提供高质量保底选项（rank_ratio 低意味着录取概率高，如 0.90, 0.85 完全符合要求）",
        "☐ 填报完成后已再次核对所有志愿的院校代码、专业组代码、专业代码，确保没有填错",
    ]
