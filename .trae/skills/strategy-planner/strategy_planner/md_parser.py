"""将 school-matcher 输出的 Markdown 报告解析为 strategy-planner 所需的 JSON 结构。

方案B补丁：MD 是人类可读报告，此模块负责将其转为结构化数据。
缺失的评分字段（major_match_score 等）用默认值 0.5 填充，
稳档/保档内部排序退化为按录取概率排序，不影响最终志愿清单生成。
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from .volunteer_sorter import rank_ratio_to_probability

_APPLICANT_RE = re.compile(
    r'>\s*\*\*考生\*\*：'
    r'(?P<province>[^·]+?)\s*·\s*'
    r'(?P<score>\d+)分\s*·\s*位次(?P<rank>\d+)\s*·\s*'
    r'(?P<subjects>[^·]+?)\s*·\s*'
    r'(?P<gender>[男女])'
)

_CARD_RE = re.compile(r'^###\s+评估卡\s+\d+：(?P<title>.+)$')
_TIER_RE = re.compile(r'^###\s+【(?P<tier>冲|稳|保)档】')
_RANK_RATIO_RE = re.compile(r'rank_ratio\s*=\s*(?P<ratio>[0-9]+\.?[0-9]*)')
_TABLE_ROW_RE = re.compile(
    r'^\|\s*(?P<school>[^|]+?)\s*\|\s*(?P<major>[^|]+?)\s*\|\s*(?P<ratio>[0-9]+\.[0-9]+)\s*\|'
)

# 元数据提取正则
_METADATA_RE = re.compile(r'<!-- METADATA_START (.*?) METADATA_END -->')


def parse_school_matcher_md(md_text: str) -> Dict[str, Any]:
    """将 school-matcher 输出的 MD 解析为 strategy-planner 输入结构。"""
    applicant_profile = _parse_applicant(md_text)
    schools = _parse_schools(md_text)
    
    # 尝试提取隐藏元数据 (硬约束过滤模块/2 透传的数据)
    passed_majors = []
    eligible_pool = list(schools) # 兜底
    
    meta_m = _METADATA_RE.search(md_text)
    if meta_m:
        try:
            meta_data = json.loads(meta_m.group(1))
            passed_majors = meta_data.get("passed_majors", [])
            eligible_pool = meta_data.get("eligible_pool", [])
        except Exception:
            pass

    return {
        "applicant_profile": applicant_profile,
        "passed_majors": passed_majors,
        "recommended_schools": schools,
        "eligible_pool": eligible_pool,
    }


def _parse_applicant(md_text: str) -> Dict[str, Any]:
    m = _APPLICANT_RE.search(md_text)
    if not m:
        # 兜底：尝试解析更新后的格式
        # - 省份：山东
        # - 总分：569分  位次：50519
        province = "未知"
        score = 0
        rank = 0
        subjects = []
        gender = "未知"
        
        for line in md_text.splitlines():
            if "- 省份：" in line:
                province = line.split("：")[-1].strip()
            elif "- 总分：" in line:
                parts = line.split("：")
                if len(parts) > 1:
                    sub_parts = parts[1].split("分")
                    score = int(sub_parts[0].strip())
                    if "位次：" in line:
                        rank = int(line.split("位次：")[-1].strip())
            elif "- 性别：" in line:
                parts = line.split("：")
                if len(parts) > 1:
                    gender_part = parts[1].split("选科：")[0].strip()
                    gender = gender_part
                    if "选科：" in line:
                        subjects_part = line.split("选科：")[-1].strip()
                        subjects = [s.strip() for s in re.split(r'[+＋、]', subjects_part) if s.strip()]
        
        return {
            "province": province,
            "total_score": score,
            "provincial_rank": rank,
            "subject_category": "物理类" if "物理" in subjects else "历史类",
            "selected_subjects": subjects,
            "gender": gender,
        }

    subjects = [s.strip() for s in re.split(r'[+＋、]', m.group("subjects").strip()) if s.strip()]
    return {
        "province": m.group("province").strip(),
        "total_score": int(m.group("score")),
        "provincial_rank": int(m.group("rank")),
        "subject_category": "物理类" if "物理" in subjects else "历史类",
        "selected_subjects": subjects,
        "gender": m.group("gender"),
    }


def _parse_schools(md_text: str) -> List[Dict[str, Any]]:
    schools: List[Dict[str, Any]] = []

    current_positioning: Optional[str] = None
    current_school: Optional[str] = None
    current_major: Optional[str] = None
    current_rank_ratio: Optional[float] = None
    in_table = False
    in_summary_section = False

    for line in md_text.splitlines():
        line = line.strip()
        
        # 停止解析区
        if line.startswith("## AI 评估待办") or line.startswith("## 使用说明"):
            _flush(schools, current_school, current_major, current_rank_ratio, current_positioning)
            current_school = None
            in_summary_section = True
            continue
        if in_summary_section:
            continue

        # 检测档位
        tier_m = _TIER_RE.match(line)
        if tier_m:
            _flush(schools, current_school, current_major, current_rank_ratio, current_positioning)
            current_school = current_major = None
            current_rank_ratio = None
            current_positioning = tier_m.group("tier")
            in_table = False
            continue

        # 检测表格开始
        if line.startswith("| 学校 | 专业 | 位次比 |"):
            in_table = True
            continue
        if in_table and line.startswith("|---"):
            continue

        # 解析表格行
        if in_table:
            table_m = _TABLE_ROW_RE.match(line)
            if table_m and current_positioning:
                school_name = table_m.group("school").strip()
                major_name = table_m.group("major").strip()
                try:
                    ratio = float(table_m.group("ratio"))
                    if school_name not in ("学校", ""):
                        schools.append(_build_entry(school_name, major_name, ratio, current_positioning))
                except ValueError:
                    pass
                continue
            elif not line.startswith("|"):
                in_table = False

        # 评估卡头部 (兼容旧版或详细卡)
        card_m = _CARD_RE.match(line)
        if card_m:
            _flush(schools, current_school, current_major, current_rank_ratio, current_positioning)
            current_rank_ratio = None
            current_school = current_major = None

            title = card_m.group('title').strip()
            title_clean = re.sub(r'（[^）]*）', '', title).strip()
            if '·' in title_clean:
                parts = title_clean.split('·', 1)
                current_school = parts[0].strip()
                current_major = parts[1].strip()
            continue

        # 普通卡：从表格行提取 rank_ratio
        if current_school and current_rank_ratio is None:
            rr_m = _RANK_RATIO_RE.search(line)
            if rr_m:
                current_rank_ratio = float(rr_m.group('ratio'))

    _flush(schools, current_school, current_major, current_rank_ratio, current_positioning)

    # 去重：同一（学校, 专业）只保留第一次出现的（详细卡优先于速览表）
    seen: set = set()
    deduped = []
    for s in schools:
        key = (s["school_name"], s["major_name"])
        if key not in seen:
            seen.add(key)
            deduped.append(s)
    return deduped


def _flush(
    schools: List[Dict[str, Any]],
    school_name: Optional[str],
    major_name: Optional[str],
    rank_ratio: Optional[float],
    positioning: Optional[str],
) -> None:
    if school_name and positioning:
        schools.append(_build_entry(school_name, major_name or '', rank_ratio or 1.0, positioning))


def _positioning_by_rank_ratio(rank_ratio: float) -> str:
    """用 rank_ratio 确定客观档位，消除上游 MD 章节分类偏差。

    与 rank_ratio_to_probability 的分段边界对齐：
      > 1.20 → 冲  (概率 < 60%)
      1.00–1.20 → 稳  (概率 60–80%)
      < 1.00 → 保  (概率 > 80%)
    """
    if rank_ratio > 1.20:
        return "冲"
    if rank_ratio >= 1.00:
        return "稳"
    return "保"


def _build_entry(
    school_name: str,
    major_name: str,
    rank_ratio: float,
    positioning: str,
) -> Dict[str, Any]:
    prob = rank_ratio_to_probability(rank_ratio)
    # 用 rank_ratio 客观分档，覆盖上游 MD 章节标题的主观分类
    corrected_positioning = _positioning_by_rank_ratio(rank_ratio)
    return {
        "school_name": school_name,
        "major_name": major_name,
        "positioning": corrected_positioning,
        "rank_ratio_value": rank_ratio,
        "admission_probability_num": prob,
        "admission_probability": f"约{int(prob * 100)}%",
        "major_match_score": 0.5,
        "cost_performance_score": 0.5,
        "location_preference_score": 0.5,
        "risk_desc": f"rank_ratio={rank_ratio}，录取概率估算约{int(prob * 100)}%（⚠️ 基于历史数据推算）",
    }
