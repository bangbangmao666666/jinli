"""五层过滤主流水线（PRD §四）。

严格按顺序：省份招生计划 → 分数位次 → 选科 → 体检 → 政审。
前一层未通过则直接排除，不再进入下一层。

入口：`run(applicant, data_dir=None) -> dict`
- 成功：返回 success 结构
- 异常：捕获 FilterError，返回 error 结构；其它异常兜底为 RUNTIME_UNEXPECTED_EXCEPTION
"""
from __future__ import annotations

import copy
import datetime as _dt
import logging
import re
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import data_loader, data_validator, input_validator, physical_filter, rank_tier, subject_parser
from .errors import DataIntegrityViolatedError, FilterError

logger = logging.getLogger(__name__)

# ── 专业评估预判数据（前置自 major-evaluator） ───────────────────────────────────
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


def _get_preliminary_advice(major_name: str) -> Optional[str]:
    base_name = re.sub(r'[\(（].*?[\)）]', '', major_name).strip()
    return _MAJOR_ADVICE.get(base_name)


def run(applicant: Dict[str, Any], *, data_dir: Optional[Path] = None) -> Dict[str, Any]:
    try:
        return _run_inner(applicant, data_dir=data_dir)
    except FilterError as exc:
        return exc.to_response()
    except Exception as exc:  # noqa: BLE001 - 兜底必须宽
        return {
            "status": "error",
            "error_code": "RUNTIME_UNEXPECTED_EXCEPTION",
            "error_category": "runtime",
            "error_message": f"未预期异常：{exc}",
            "error_detail": {"traceback": traceback.format_exc()},
            "user_action_required": "请将完整错误信息反馈给维护者；此类错误通常意味着代码存在漏捕获的分支。",
            "partial_result": None,
        }


def _run_inner(applicant: Dict[str, Any], *, data_dir: Optional[Path]) -> Dict[str, Any]:
    warnings: List[str] = []
    excluded: List[Dict[str, str]] = []

    # ---------- 准备：加载参考数据 ----------
    province_mode_table = data_loader.load_province_exam_mode(data_dir)
    physical_rules_table = data_loader.load_physical_restrictions(data_dir)
    subject_keyword_table = data_loader.load_subject_requirement_keywords(data_dir)

    # ---------- 位次自动换算（若只给了分数）----------
    # 在校验前补全 provincial_rank，避免校验报"缺失位次"。
    # 用一分一段表精确查表，不做估算。
    province_pre = applicant.get("province", "")
    exam_year_pre = applicant.get("exam_year", 2026)
    if not applicant.get("provincial_rank") and applicant.get("total_score") and province_pre:
        province_mode_pre = (
            province_mode_table.get("provinces", {})
            .get(province_pre, {})
            .get("exam_mode", "")
        )
        auto_rank = data_loader.lookup_rank_from_score(
            score=int(applicant["total_score"]),
            province=province_pre,
            exam_year=exam_year_pre,
            exam_mode=province_mode_pre,
            subject_category=applicant.get("subject_category", ""),
            data_dir=data_dir,
        )
        if auto_rank:
            applicant = {**applicant, "provincial_rank": auto_rank}
            warnings.append(
                f"位次由一分一段表自动换算：{applicant['total_score']}分 → 全省累计位次约 {auto_rank} 名"
                f"（{province_pre} {exam_year_pre} 年合计累计）。"
                "若您已知准确位次，请直接提供 provincial_rank 字段。"
            )
        else:
            warnings.append(
                f"未能从一分一段表中查到 {applicant['total_score']} 分对应的位次，"
                "请手动提供 provincial_rank 字段。"
            )

    # ---------- 输入校验 ----------
    warnings.extend(input_validator.validate(applicant, province_mode_table))

    province = applicant["province"]
    exam_year = applicant.get("exam_year", 2026)
    applicant_rank = applicant["provincial_rank"]
    selected_subjects = applicant.get("selected_subjects") or []
    subject_category = applicant["subject_category"]
    physical_exam = applicant.get("physical_exam")
    political_review_clean = applicant.get("political_review_clean")
    aggressive_mode = bool(applicant.get("aggressive_mode", False))

    # ---------- 第一层：省份与招生计划 ----------
    plan = data_loader.load_admission_plan(province, exam_year, data_dir)
    warnings.extend(data_validator.validate_admission_plan(plan, exam_year))
    total_schools_in_plan = len(plan.get("schools", []))

    # 加载历史录取位次（文件不存在时为空字典，位次层退化为 unknown）
    historical_ranks = data_loader.load_historical_ranks(province, exam_year, data_dir)
    warnings.extend(data_validator.validate_historical_ranks(historical_ranks, province, exam_year))

    # 预解析所有选科要求（失败集中抛错）
    requirement_map, _ = subject_parser.parse_batch(plan, subject_keyword_table)

    # 体检缺失维度的全局 warnings（只加一次）
    warnings.extend(physical_filter.collect_missing_fields_warning(physical_exam))
    if political_review_clean is None:
        warnings.append(
            "政审维度未核实，涉及公安/军事/国防等专业已保留在池中，请自行核对。"
        )

    province_exam_mode = province_mode_table["provinces"][province]["exam_mode"]

    # ---------- 逐校逐专业遍历：二~五层 ----------
    eligible_schools: List[Dict[str, Any]] = []
    all_majors_detail: List[Dict[str, Any]] = []  # 全量明细：每条代表一个专业的过滤结论
    total_majors_after_filter = 0

    for school in plan.get("schools", []):
        kept_groups: List[Dict[str, Any]] = []
        for group in school.get("major_groups", []):
            raw_req = group.get("subject_requirement_raw")
            if raw_req is None:
                raise DataIntegrityViolatedError(
                    f"{school.get('school_name')} · {group.get('group_name')} 缺失 subject_requirement_raw",
                    user_action="请联系数据维护者补全该专业组的选科要求字段。",
                    detail={
                        "school_code": school.get("school_code"),
                        "group_code": group.get("group_code"),
                    },
                )
            parsed_req = requirement_map[(school["school_code"], group["group_code"])]

            # 第三层：选科 / 文理准入
            if province_exam_mode == "传统文理":
                req_met = _check_traditional_text_science(parsed_req, subject_category, group)
            else:
                req_met = subject_parser.satisfies(parsed_req, selected_subjects)

            kept_majors: List[Dict[str, Any]] = []
            for major in group.get("majors", []):
                target_label = f"{school['school_name']} · {major['major_name']}"

                # 全量明细的公共字段（每条专业都会写入）
                _detail_base: Dict[str, Any] = {
                    "school_name": school["school_name"],
                    "school_code": school["school_code"],
                    "school_city": school.get("school_city"),
                    "school_tier": school.get("school_tier", []),
                    "group_code": group["group_code"],
                    "group_name": group.get("group_name"),
                    "subject_requirement_raw": raw_req,
                    "major_code": major["major_code"],
                    "major_name": major["major_name"],
                    "major_category": major.get("major_category"),
                    "preliminary_advice": _get_preliminary_advice(major["major_name"]),
                }

                # 选科不符：记录排除，不进后续层
                if not req_met:
                    reason = (
                        f"选科维度：专业组选科要求为 '{raw_req}' "
                        f"（解析为 {parsed_req['logic']}:{parsed_req['subjects']}），"
                        f"考生选科为 {selected_subjects}"
                    )
                    excluded.append({"target": target_label, "reason": reason, "dimension": "选科"})
                    all_majors_detail.append({
                        **_detail_base,
                        "status": "excluded",
                        "exclude_dimension": "选科",
                        "exclude_reason": reason,
                        "rank_ratio": None,
                        "rank_tier": None,
                        "historical_data_missing": None,
                    })
                    continue

                # 第二层：分数位次
                yearly_data = major.get("yearly_admission_data") or []
                if not yearly_data:
                    yearly_data = data_loader.lookup_historical_rank(
                        historical_ranks, school["school_name"], major["major_name"]
                    )
                if not yearly_data:
                    logger.debug(
                        "历史位次未命中：%s · %s",
                        school["school_name"], major["major_name"],
                    )
                ratio, tier, incomplete, missing_years = rank_tier.compute(
                    yearly_data, applicant_rank
                )
                if not rank_tier.should_include(tier, aggressive_mode):
                    reason = (
                        f"分数位次维度：rank_ratio≈{ratio}，档位={tier}，"
                        f"默认模式不纳入基本盘（激进模式可启用）。"
                    )
                    excluded.append({"target": target_label, "reason": reason, "dimension": "分数位次"})
                    all_majors_detail.append({
                        **_detail_base,
                        "status": "excluded",
                        "exclude_dimension": "分数位次",
                        "exclude_reason": reason,
                        "rank_ratio": ratio,
                        "rank_tier": tier,
                        "historical_data_missing": tier == "unknown",
                        "yearly_admission_data": yearly_data,
                    })
                    continue

                # 第四层：体检
                kept, exclude_reason, verified = physical_filter.evaluate(
                    major, physical_exam, applicant["gender"], physical_rules_table
                )
                if not kept:
                    reason = exclude_reason or "体检维度：不符合"
                    excluded.append({"target": target_label, "reason": reason, "dimension": "体检"})
                    all_majors_detail.append({
                        **_detail_base,
                        "status": "excluded",
                        "exclude_dimension": "体检",
                        "exclude_reason": reason,
                        "rank_ratio": ratio,
                        "rank_tier": tier,
                        "historical_data_missing": tier == "unknown",
                        "yearly_admission_data": yearly_data,
                    })
                    continue

                # 第五层：政审
                if not _political_review_pass(school, political_review_clean):
                    reason = (
                        "政审维度：考生明确 political_review_clean=False，"
                        "公安/军校/定向类院校不予保留"
                        if political_review_clean is False
                        else "政审维度：未知信息，已按用户未提供政审处理"
                    )
                    excluded.append({"target": target_label, "reason": reason, "dimension": "政审"})
                    all_majors_detail.append({
                        **_detail_base,
                        "status": "excluded",
                        "exclude_dimension": "政审",
                        "exclude_reason": reason,
                        "rank_ratio": ratio,
                        "rank_tier": tier,
                        "historical_data_missing": tier == "unknown",
                        "yearly_admission_data": yearly_data,
                    })
                    continue

                # 全部通过：保留
                major_out = {
                    "major_code": major["major_code"],
                    "major_name": major["major_name"],
                    "major_category": major.get("major_category"),
                    "preliminary_advice": _get_preliminary_advice(major["major_name"]),
                    "yearly_admission_data": yearly_data,
                    "single_subject_requirement": major.get("single_subject_requirement"),
                    "gender_limit": major.get("gender_limit"),
                    "physical_requirement_notes": major.get("physical_requirement_notes", []),
                    "rank_ratio_value": ratio,
                    "rank_ratio_tier": tier,
                    "historical_data_missing": tier == "unknown",
                    "data_incomplete": incomplete,
                    "data_incomplete_years": missing_years,
                    "physical_check": "passed" if verified else "not_verified",
                }
                kept_majors.append(major_out)
                all_majors_detail.append({
                    **_detail_base,
                    "status": "eligible",
                    "exclude_dimension": None,
                    "exclude_reason": None,
                    "rank_ratio": ratio,
                    "rank_tier": tier,
                    "historical_data_missing": tier == "unknown",
                    "data_incomplete": incomplete,
                    "data_incomplete_years": missing_years,
                    "yearly_admission_data": yearly_data,
                    "physical_check": "passed" if verified else "not_verified",
                })

            if kept_majors:
                kept_groups.append({
                    "group_code": group["group_code"],
                    "group_name": group.get("group_name"),
                    "subject_requirement_raw": raw_req,
                    "subject_requirement_parsed": parsed_req,
                    "subject_requirement_met": req_met,
                    "majors": kept_majors,
                })

        if kept_groups:
            eligible_schools.append({
                "school_code": school["school_code"],
                "school_name": school["school_name"],
                "school_city": school.get("school_city"),
                "school_province": school.get("school_province"),
                "school_tier": school.get("school_tier", []),
                "is_public": school.get("is_public"),
                "major_groups": kept_groups,
            })
            total_majors_after_filter += sum(len(g["majors"]) for g in kept_groups)

    # ---------- 新高考改革过渡期数据降权提示 ----------
    province_info = province_mode_table["provinces"][province]
    reform_year = province_info.get("new_gaokao_reform_year")
    if reform_year and reform_year >= exam_year - 1:
        warnings.append(
            f"{province} 于 {reform_year} 年启动新高考改革，历史数据参考价值降低；"
            "rank_ratio 仅作参考，请结合本省官方口径核对。"
        )

    return {
        "status": "success",
        "generated_at": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "data_snapshot_version": plan.get("version", "unknown"),
        "applicant_profile": _sanitize_profile(applicant),
        "eligible_pool": eligible_schools,
        "excluded_summary": excluded,
        "all_majors_detail": all_majors_detail,  # 全量明细：招生计划中每个专业的过滤结论
        "warnings": warnings,
        "stats": {
            "total_schools_in_plan": total_schools_in_plan,
            "schools_after_filter": len(eligible_schools),
            "total_majors_in_plan": len(all_majors_detail),
            "total_majors_after_filter": total_majors_after_filter,
        },
    }


def _sanitize_profile(applicant: Dict[str, Any]) -> Dict[str, Any]:
    # 直接回传所有字段的拷贝（深拷贝），便于下游 模块 使用。
    return copy.deepcopy(applicant)


def _political_review_pass(
    school: Dict[str, Any], political_review_clean: Optional[bool]
) -> bool:
    """政审第五层：
    - True  → 全保留
    - False → 公安/军校/定向排除
    - None  → 全保留，但 warnings 已提示（pipeline 上游已加）
    """
    if political_review_clean is False:
        if school.get("is_police") or school.get("is_military"):
            return False
    return True


def _check_traditional_text_science(
    parsed_req: Dict[str, Any],
    subject_category: str,
    group: Dict[str, Any],
) -> bool:
    """传统文理模式下用 group/major 的科类标签过滤（PRD §四第三层）。

    传统文理省份没有选科，选科要求字段通常为"不限"；匹配交由招生计划的
    group 原生字段（例如 group_name 含"文史类"/"理工类"）决定。MVP 阶段简
    化为：parsed=NONE 视为兼收；否则按 subject_category 对齐 group_name。
    """
    if parsed_req["logic"] == "NONE":
        name = (group.get("group_name") or "") + (group.get("group_code") or "")
        if subject_category == "理科":
            return any(t in name for t in ["理", "工", "兼"])
        if subject_category == "文科":
            return any(t in name for t in ["文", "史", "兼"])
        return True
    # 传统文理省份理论上不会出现 AND/OR 选科要求；出现则保守放行（由上游数据纠正）
    return True
