"""输入校验。

原则：字段缺失就停下来要求用户补，不允许"估算位次"这类补默认值的操作（PRD §2.4）。
"""
from __future__ import annotations

from typing import Any, Dict, List

from .errors import (
    InvalidFieldValueError,
    InvalidSubjectCombinationError,
    MissingRequiredFieldError,
)

REQUIRED_FIELDS = [
    "province",
    "total_score",
    "provincial_rank",
    "subject_category",
    "selected_subjects",
    "gender",
]

PROVINCES_31 = {
    "北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江",
    "上海", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南",
    "湖北", "湖南", "广东", "广西", "海南", "重庆", "四川", "贵州",
    "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆",
}

VALID_SUBJECTS = {"物理", "化学", "生物", "政治", "历史", "地理", "技术"}

SUBJECT_CATEGORY_OPTIONS = {"物理类", "历史类", "理科", "文科", "综合改革"}

GENDER_OPTIONS = {"男", "女"}


def validate(applicant: Dict[str, Any], province_mode_table: Dict[str, Any]) -> List[str]:
    """执行输入校验，返回非致命的 warnings 列表。

    致命错误直接抛异常（由 pipeline 转为结构化 error 响应）；
    非致命（如分数/位次轻微矛盾）通过返回列表透传。
    """
    # 1. 必填字段存在性
    missing = [f for f in REQUIRED_FIELDS if f not in applicant or applicant[f] in (None, "")]
    # selected_subjects 特殊：允许空列表，但新高考省份后续会再校验
    if "selected_subjects" in applicant and applicant["selected_subjects"] == []:
        # 先从 missing 里去掉；是否真的缺失取决于该省高考模式
        if "selected_subjects" in missing:
            missing.remove("selected_subjects")

    if missing:
        raise MissingRequiredFieldError(
            f"必填字段缺失：{', '.join(missing)}",
            user_action=(
                "请补全这些字段后重新运行。"
                "位次比分数更重要——如缺失位次，请务必查一分一段表补全，严禁用分数估算。"
            ),
            detail={"missing_fields": missing},
        )

    province = applicant["province"]
    if province not in PROVINCES_31:
        raise InvalidFieldValueError(
            f"省份 '{province}' 不在 31 个省级行政区列表内",
            user_action="请核对考生报名所在省份（不含港澳台）。",
            detail={"field": "province", "value": province},
        )

    # 2. 类型与范围
    warnings: List[str] = []
    total_score = applicant["total_score"]
    provincial_rank = applicant["provincial_rank"]
    if not isinstance(total_score, int) or total_score < 0:
        raise InvalidFieldValueError(
            f"total_score 必须是非负整数，实际: {total_score!r}",
            user_action="请核对总分后重新运行。",
            detail={"field": "total_score", "value": total_score},
        )
    if not isinstance(provincial_rank, int) or provincial_rank < 1:
        raise InvalidFieldValueError(
            f"provincial_rank 必须是正整数，实际: {provincial_rank!r}",
            user_action="请核对一分一段表查询到的省内位次。",
            detail={"field": "provincial_rank", "value": provincial_rank},
        )

    # 总分省份上限（上海660、海南900、其他750）
    score_limit_table = province_mode_table.get("total_score_limits", {})
    score_limit = score_limit_table.get(province) or score_limit_table.get(
        province_mode_table["provinces"][province]["exam_mode"], 750
    )
    if total_score > score_limit:
        raise InvalidFieldValueError(
            f"total_score={total_score} 超过 {province} 总分上限 {score_limit}",
            user_action="请核对输入的总分。",
            detail={"field": "total_score", "value": total_score, "limit": score_limit},
        )

    # 3. 科类 + 选科 合法性
    subject_category = applicant["subject_category"]
    if subject_category not in SUBJECT_CATEGORY_OPTIONS:
        raise InvalidFieldValueError(
            f"subject_category '{subject_category}' 不合法",
            user_action="请使用：物理类 / 历史类 / 理科 / 文科 / 综合改革 之一。",
            detail={"field": "subject_category", "value": subject_category},
        )

    if applicant["gender"] not in GENDER_OPTIONS:
        raise InvalidFieldValueError(
            f"gender 必须是'男'或'女'，实际: {applicant['gender']!r}",
            user_action="请核对性别字段。",
            detail={"field": "gender", "value": applicant["gender"]},
        )

    _validate_subject_combination(
        applicant["selected_subjects"],
        subject_category,
        province,
        province_mode_table,
    )

    # 4. 轻量一致性提示
    #   注：真实校验需要一分一段表；这里只给出粗粒度告警。
    if total_score > 700 and provincial_rank > 50000:
        warnings.append(
            f"分数与位次可能矛盾（total_score={total_score}, provincial_rank={provincial_rank}），"
            "请对照一分一段表核对，避免录入错误。"
        )

    return warnings


def _validate_subject_combination(
    selected: List[str],
    subject_category: str,
    province: str,
    province_mode_table: Dict[str, Any],
) -> None:
    province_info = province_mode_table["provinces"].get(province)
    if province_info is None:
        raise InvalidFieldValueError(
            f"省份 '{province}' 未在 province_exam_mode.json 中登记",
            user_action="请联系维护者补充该省数据。",
            detail={"field": "province", "value": province},
        )
    exam_mode = province_info["exam_mode"]

    # 非法科目（所有模式共用）
    unknown = [s for s in selected if s not in VALID_SUBJECTS]
    if unknown and exam_mode != "传统文理":
        raise InvalidSubjectCombinationError(
            f"包含未知选科科目：{unknown}",
            user_action=f"合法科目范围：{sorted(VALID_SUBJECTS)}。请核对。",
            detail={"unknown_subjects": unknown, "selected": selected},
        )

    if exam_mode == "新高考3+1+2":
        if subject_category not in {"物理类", "历史类"}:
            raise InvalidSubjectCombinationError(
                f"{province} 为 3+1+2 模式，subject_category 必须是'物理类'或'历史类'，"
                f"实际: {subject_category}",
                user_action="请改为'物理类'或'历史类'。",
                detail={"province": province, "exam_mode": exam_mode},
            )
        if len(selected) != 3:
            raise InvalidSubjectCombinationError(
                f"3+1+2 模式必须选 3 科（1 首选 + 2 再选），实际提交 {len(selected)} 科：{selected}",
                user_action="请补全考生实际选考的 3 门科目。",
                detail={"selected": selected},
            )
        if "物理" in selected and "历史" in selected:
            raise InvalidSubjectCombinationError(
                "3+1+2 模式下不允许同时选考物理和历史（二者互斥）",
                user_action="请核对：物理类则选物理，历史类则选历史，两者不能并存。",
                detail={"selected": selected},
            )
        first = "物理" if subject_category == "物理类" else "历史"
        if first not in selected:
            raise InvalidSubjectCombinationError(
                f"subject_category={subject_category} 但选科中不含'{first}'",
                user_action="首选科目必须与科类一致。",
                detail={"subject_category": subject_category, "selected": selected},
            )
        second_from = set(province_mode_table["subject_constraints"]["新高考3+1+2"]["再选_from"])
        seconds = [s for s in selected if s != first]
        if not all(s in second_from for s in seconds):
            raise InvalidSubjectCombinationError(
                f"再选科目超出合法范围：{seconds}",
                user_action=f"再选只能从 {sorted(second_from)} 中挑 2 门。",
                detail={"second_subjects": seconds},
            )

    elif exam_mode == "新高考3+3":
        if subject_category != "综合改革":
            raise InvalidSubjectCombinationError(
                f"{province} 为 3+3 模式，subject_category 必须为'综合改革'",
                user_action="请改为'综合改革'。",
                detail={"province": province, "subject_category": subject_category},
            )
        if len(selected) != 3:
            raise InvalidSubjectCombinationError(
                f"3+3 模式必须选 3 科，实际提交 {len(selected)} 科",
                user_action="请补全 3 门选考科目。",
                detail={"selected": selected},
            )
        allowed = set(province_mode_table["subject_constraints"]["新高考3+3"]["选考_from"])
        if not all(s in allowed for s in selected):
            raise InvalidSubjectCombinationError(
                f"选考科目超出合法范围：{[s for s in selected if s not in allowed]}",
                user_action=f"合法范围：{sorted(allowed)}",
                detail={"selected": selected},
            )

    else:  # 传统文理
        if subject_category not in {"理科", "文科"}:
            raise InvalidSubjectCombinationError(
                f"{province} 为传统文理模式，subject_category 必须是'理科'或'文科'",
                user_action="请改为'理科'或'文科'。",
                detail={"province": province, "subject_category": subject_category},
            )
