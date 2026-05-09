"""选科要求字符串 → 结构化表达式 {logic, subjects}。

原则：解析不了就抛 RUNTIME_SUBJECT_REQUIREMENT_PARSE_FAILED，禁止"按常见情况推断"。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from .errors import SubjectRequirementParseFailed


def _contains_any(s: str, needles: List[str]) -> bool:
    return any(n in s for n in needles)


def _apply_special_mappings(s: str, keyword_table: Dict[str, Any]) -> str:
    """应用特殊映射，将特定字符串替换为标准化形式。"""
    for mapping in keyword_table.get("special_mappings", []):
        s = s.replace(mapping["from"], mapping["to"])
    return s


def parse(raw: str, keyword_table: Dict[str, Any]) -> Dict[str, Any]:
    """返回 `{"logic": "AND"|"OR"|"NONE", "subjects": [...]}`。

    解析流程（严格顺序）：
    1. 去除空白；若命中 none_patterns → NONE
    2. 应用特殊映射
    3. 命中 forbidden_patterns → 直接抛错（不做宽容处理）
    4. 按 AND/OR 分隔符切分，不允许 AND 和 OR 混用
    5. 切出来的每一段必须是合法的科目名，否则抛错
    """
    if not isinstance(raw, str):
        raise SubjectRequirementParseFailed(
            f"选科要求字段类型非字符串：{type(raw).__name__}",
            user_action="请反馈给数据维护者修订招生计划文件。",
            detail={"raw": raw},
        )

    s = raw.strip().replace(" ", "").replace("　", "")
    if not s:
        raise SubjectRequirementParseFailed(
            "选科要求为空字符串",
            user_action="请反馈给数据维护者补全字段。",
            detail={"raw": raw},
        )

    # 1. NONE
    for pattern in keyword_table.get("none_patterns", []):
        if pattern in s:
            return {"logic": "NONE", "subjects": []}

    # 2. 应用特殊映射
    s = _apply_special_mappings(s, keyword_table)

    # 3. 显式禁止的模糊写法 —— 严禁猜测
    for forbidden in keyword_table.get("forbidden_patterns", []):
        if re.fullmatch(forbidden["regex"], s, flags=re.IGNORECASE):
            raise SubjectRequirementParseFailed(
                f"选科要求包含歧义写法 '{raw}'：{forbidden['reason']}",
                user_action="请将此条反馈给数据维护者修订原始数据。",
                detail={"raw": raw, "reason": forbidden["reason"]},
            )

    valid = set(keyword_table["valid_subjects"])
    and_seps = keyword_table["and_separators"]
    or_seps = keyword_table["or_separators"]

    has_and = _contains_any(s, and_seps)
    has_or = _contains_any(s, or_seps)

    if has_and and has_or:
        raise SubjectRequirementParseFailed(
            f"选科要求同时包含 AND 与 OR 分隔符，优先级无法确定：'{raw}'",
            user_action="请反馈给数据维护者拆分为结构化字段。",
            detail={"raw": raw},
        )

    parts = _split(s, and_seps if has_and else (or_seps if has_or else []))
    # 去除括号等残留
    parts = [_strip_brackets(p) for p in parts if p]
    unknown = [p for p in parts if p not in valid]
    if unknown:
        raise SubjectRequirementParseFailed(
            f"选科要求包含未知科目：{unknown}，来源：'{raw}'",
            user_action="请反馈给数据维护者核查招生计划原文。",
            detail={"raw": raw, "unknown": unknown, "parsed_parts": parts},
        )

    if has_and:
        return {"logic": "AND", "subjects": parts}
    if has_or:
        return {"logic": "OR", "subjects": parts}
    # 单一科目
    return {"logic": "AND", "subjects": parts}


def _split(s: str, seps: List[str]) -> List[str]:
    if not seps:
        return [s]
    # 简单逐个分隔符 split；所有分隔符同级
    result = [s]
    for sep in seps:
        new_result: List[str] = []
        for item in result:
            new_result.extend(item.split(sep))
        result = new_result
    return [x for x in result if x]


def _strip_brackets(s: str) -> str:
    return s.strip("（）()【】[]、,，;；")


def satisfies(requirement: Dict[str, Any], selected_subjects: List[str]) -> bool:
    """判断考生选科是否满足给定选科要求。"""
    logic = requirement["logic"]
    required = requirement["subjects"]
    if logic == "NONE":
        return True
    chosen = set(selected_subjects)
    if logic == "AND":
        return all(r in chosen for r in required)
    if logic == "OR":
        return any(r in chosen for r in required)
    # 应该不可达
    raise SubjectRequirementParseFailed(
        f"未知 logic: {logic}",
        detail={"requirement": requirement},
    )


def parse_batch(
    plan: Dict[str, Any], keyword_table: Dict[str, Any]
) -> Tuple[Dict[Tuple[str, str], Dict[str, Any]], List[Dict[str, str]]]:
    """预解析整份招生计划里的所有 subject_requirement_raw，集中报错。

    返回：
    - requirement_map: {(school_code, group_code): parsed}
    - failed:          [{"target": "...", "raw": "..."}]  （目前只要有 failed 就直接抛，
                        但返回结构保留便于后续扩展批量校验）
    """
    req_map: Dict[Tuple[str, str], Dict[str, Any]] = {}
    failed: List[Dict[str, str]] = []
    for school in plan.get("schools", []):
        for group in school.get("major_groups", []):
            raw = group.get("subject_requirement_raw")
            if raw is None:
                failed.append({
                    "target": f"{school.get('school_name')} · {group.get('group_name')}",
                    "raw": "<missing>",
                })
                continue
            try:
                parsed = parse(raw, keyword_table)
            except SubjectRequirementParseFailed as exc:
                # 先收集，在循环结束后若有 failed 就合并抛出
                failed.append({
                    "target": f"{school.get('school_name')} · {group.get('group_name')}",
                    "raw": raw,
                    "error": exc.message,
                })
                continue
            req_map[(school["school_code"], group["group_code"])] = parsed
    if failed:
        raise SubjectRequirementParseFailed(
            f"共 {len(failed)} 条选科要求无法解析；详见 error_detail.failed_items",
            user_action="请反馈给数据维护者修订招生计划原文，或在 subject_requirement_keywords.json 中补充规则。",
            detail={"failed_items": failed},
        )
    return req_map, failed
