"""主审核流水线。

按顺序执行输入校验 → 规则集适配 → 最终检查 → 报告生成。

入口：`run(input_data, *, data_dir=None) -> dict`
- 成功：返回 success 结构（最终志愿填报报告）
- 异常：捕获 SpecialAdvisorError，返回 error 结构
"""
from __future__ import annotations

import copy
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import (
    data_loader,
    exceptions,
    female_adapter,
    final_checker,
    low_score_adapter,
    math_physics_adapter,
    reboot_evaluator,
    report_generator,
    rule_engine,
    system_target_adapter,
)
from .exceptions import SpecialAdvisorError


def run(input_data: Dict[str, Any], *, data_dir: Optional[Path] = None) -> Dict[str, Any]:
    try:
        return _run_inner(input_data, data_dir=data_dir)
    except SpecialAdvisorError as exc:
        return exc.to_response()
    except Exception as exc:
        return {
            "status": "error",
            "error_code": "RUNTIME_UNEXPECTED_EXCEPTION",
            "error_category": "runtime",
            "error_message": f"未预期异常：{exc}",
            "error_detail": {"traceback": traceback.format_exc()},
            "user_action_required": "请将完整错误信息反馈给维护者；此类错误通常意味着代码存在漏捕获的分支。",
            "partial_result": None,
        }


def _run_inner(input_data: Dict[str, Any], *, data_dir: Optional[Path]) -> Dict[str, Any]:
    # ---------- 0. 提取上游输入 ----------
    applicant = input_data.get("applicant_profile") or {}
    eligible_pool = input_data.get("eligible_pool")
    draft_plan = input_data.get("draft_plan") or {}
    专业评估结果 = input_data.get("专业评估结果")
    院校匹配_match_cards = input_data.get("院校匹配_match_cards")

    # ---------- 1. 输入校验 ----------
    _validate_input(applicant, draft_plan)

    # ---------- 2. 初始化规则引擎 ----------
    engine = rule_engine.RuleEngine(data_dir=data_dir)
    warnings: List[Dict[str, Any]] = []
    adjustments: List[Dict[str, Any]] = []
    special_tags: List[str] = []
    special_tags_reasons: List[str] = []

    # 规则引擎加载警告
    warnings.extend([{"level": "低危", "icon": "ℹ️", "content": w, "suggestion": "", "rule_basis": "规则库加载"} for w in engine.warnings])

    # ---------- 3. 执行各规则集适配 ----------
    # 3.1 中低分段女生
    female_result = female_adapter.apply(applicant, draft_plan, 专业评估结果, engine)
    if female_result["applicable"]:
        special_tags.extend(female_result["special_tags"])
        special_tags_reasons.append("性别为女，已执行女生避坑规则")
        adjustments.extend(female_result["adjustments"])
        warnings.extend(female_result["warnings"])

    # 3.2 数理基础薄弱
    math_result = math_physics_adapter.apply(applicant, draft_plan, 专业评估结果, engine)
    if math_result["applicable"]:
        special_tags.extend(math_result["special_tags"])
        special_tags_reasons.append("数理成绩低于阈值，已执行数理基础薄弱规则")
        adjustments.extend(math_result["adjustments"])
        warnings.extend(math_result["warnings"])

    # 3.3 体制内目标
    system_result = system_target_adapter.apply(applicant, draft_plan, 院校匹配_match_cards, engine)
    if system_result["applicable"]:
        special_tags.extend(system_result["special_tags"])
        special_tags_reasons.append("考生目标为体制内，已执行体制内目标适配规则")
        adjustments.extend(system_result["adjustments"])
        warnings.extend(system_result["warnings"])

    # 3.4 低分段考生
    low_score_result = low_score_adapter.apply(applicant, draft_plan, eligible_pool, engine)
    if low_score_result["applicable"]:
        special_tags.extend(low_score_result["special_tags"])
        special_tags_reasons.append("考生为低分段，已执行低分段适配规则")
        adjustments.extend(low_score_result["adjustments"])
        warnings.extend(low_score_result["warnings"])

    # 3.5 复读评估（在所有规则执行完后评估）
    reboot_result = reboot_evaluator.apply(applicant, draft_plan, adjustments, warnings)
    if reboot_result["applicable"]:
        special_tags.extend(reboot_result["special_tags"])
        adjustments.extend(reboot_result["adjustments"])
        warnings.extend(reboot_result["warnings"])

    # 去重 special_tags
    special_tags = list(dict.fromkeys(special_tags))
    special_tags_reason = "；".join(special_tags_reasons) if special_tags_reasons else "未触发特殊适配规则"

    # ---------- 4. 最终审核检查清单 ----------
    checker_result = final_checker.run(
        applicant, draft_plan, eligible_pool, adjustments, warnings, special_tags
    )
    adjustments.extend(checker_result["new_adjustments"])
    warnings.extend(checker_result["new_warnings"])

    # ---------- 5. 生成报告 ----------
    must_confirm_items = report_generator.build_must_confirm_items(applicant, draft_plan)
    final_checklist = report_generator.build_final_checklist(checker_result)

    backup_plan = draft_plan.get("backup_plan")
    if not backup_plan:
        # 根据 special_tags 生成简单备选
        backup_plan = _build_default_backup(special_tags, female_result if female_result["applicable"] else {})

    report_metadata = {
        "data_sources": ["本地特殊适配规则库v1.0"],
        "rule_applied": _collect_applied_rules(special_tags),
        "upstream_modules": ["constraint-filter", "major-evaluator", "school-matcher", "strategy-planner"],
    }

    report = report_generator.generate(
        applicant=applicant,
        draft_plan=draft_plan,
        special_tags=special_tags,
        special_tags_reason=special_tags_reason,
        adjustments=adjustments,
        warnings=warnings,
        must_confirm_items=must_confirm_items,
        backup_plan=backup_plan,
        final_checklist=final_checklist,
        report_metadata=report_metadata,
        eligible_pool=eligible_pool,
        专业评估结果=专业评估结果,
        院校匹配_match_cards=院校匹配_match_cards,
    )

    return {
        "status": "success",
        **report,
    }


def _validate_input(applicant: Dict[str, Any], draft_plan: Dict[str, Any]) -> None:
    """校验上游输入。"""
    if not applicant:
        raise exceptions.InputUpstreamEmptyError(
            "上游考生信息（applicant_profile）为空",
            user_action="请先运行 硬约束过滤模块（constraint-filter）获取考生基本信息后再执行本 Skill。",
        )
    if not draft_plan:
        raise exceptions.InputUpstreamEmptyError(
            "上游方案初稿（draft_plan）为空",
            user_action="请先运行 填报策略模块（strategy-planner）生成志愿方案初稿后再执行本 Skill。",
        )

    # 检查考生必填字段
    required_fields = ["province", "total_score", "provincial_rank", "subject_category", "gender"]
    missing = [f for f in required_fields if f not in applicant or applicant[f] is None]
    if missing:
        raise exceptions.InputMissingRequiredFieldError(
            f"考生必填字段缺失：{', '.join(missing)}",
            user_action="请补充完整的考生信息后再运行。",
            detail={"missing_fields": missing},
        )

    # 检查方案结构
    if "volunteer_list" not in draft_plan:
        raise exceptions.InputDraftIncompleteError(
            "填报策略模块 方案初稿缺少 volunteer_list 字段",
            user_action="请检查 填报策略模块 的输出格式是否符合规范。",
            detail={"draft_plan_keys": list(draft_plan.keys())},
        )


def _build_default_backup(special_tags: List[str], female_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """根据特殊标签生成默认备选方案。"""
    alternatives = []
    if "女生" in special_tags:
        alternatives.append({
            "scenario": "如果考生不希望读师范",
            "alternative_list": ["护理学", "财务管理", "会计学"],
            "trade_off": "师范类有编制保障，替代方向的稳定性相对较低，但就业面更广",
        })
    if "数理基础薄弱" in special_tags:
        alternatives.append({
            "scenario": "如果考生希望避开硬核工科",
            "alternative_list": ["护理学", "学前教育", "旅游管理", "社会工作"],
            "trade_off": "这些方向对数理要求较低，就业门槛不高",
        })
    if "体制内目标" in special_tags:
        alternatives.append({
            "scenario": "如果考公友好专业竞争激烈",
            "alternative_list": ["法学", "财政学", "汉语言文学", "行政管理"],
            "trade_off": "这些专业考公岗位多，但热门方向分数要求高",
        })

    if not alternatives:
        return None

    return {
        "description": "如果考生对主方案中的某些选择不满意，可考虑以下替代",
        "alternatives": alternatives,
    }


def _collect_applied_rules(special_tags: List[str]) -> List[str]:
    """收集已应用的规则列表。"""
    rules = ["通用审核规则v1.0"]
    if "女生" in special_tags:
        rules.append("女生避坑规则v1.0")
    if "数理基础薄弱" in special_tags:
        rules.append("数理基础薄弱规则v1.0")
    if "体制内目标" in special_tags:
        rules.append("体制内目标适配规则v1.0")
    if "低分段" in special_tags:
        rules.append("低分段考生适配规则v1.0")
    if "复读评估" in special_tags:
        rules.append("复读可能性评估规则v1.0")
    rules.append("专业组干净度加严规则v1.0")
    return rules
