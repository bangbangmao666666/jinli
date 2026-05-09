#!/usr/bin/env python3
"""为山东567分考生运行 special-advisor 最终审核。"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from special_advisor import run

# 1. 构建 applicant_profile
applicant_profile = {
    "province": "山东",
    "total_score": 567,
    "provincial_rank": 39691,
    "subject_category": "物理类",
    "selected_subjects": ["物理", "化学", "生物"],
    "gender": "男",
    "exam_year": 2026,
    "math_score": 120,
    "physics_score": 90,
    "target_system": "体制外",
    "family_economy_level": "普通",
    "tuition_budget_yearly": 10000,
    "political_review_clean": True,
    "physical_exam_note": "色觉正常，视力正常，身高175，无限制",
    "preferred_cities": [],
    "parent_child_consensus": "一致"
}

# 2. 解析硬约束过滤结果构建 eligible_pool
cf_text = Path("/sessions/69f7196913380806cd05b6a2/workspace/outputs/硬约束过滤结果_山东.md").read_text(encoding="utf-8")
cf_lines = cf_text.splitlines()

current_tier = None
school_order = []
schools = {}
seen_combinations = set()
in_table = False

tier_keywords = {"冲档": "冲档", "稳档": "稳档", "保档": "保档"}

for line in cf_lines:
    for key, val in tier_keywords.items():
        if f"【{key}】" in line:
            current_tier = val
            in_table = False
            break
    if "| 学校 |" in line and "| 专业 |" in line:
        in_table = True
        continue
    if in_table and re.match(r"^\|[-| ]+\|$", line):
        continue
    if in_table and line.startswith("|") and current_tier:
        cols = [c.strip() for c in line.split("|")]
        if len(cols) >= 5:
            school_name = cols[1]
            major_name = cols[2]
            if not school_name or not major_name:
                continue
            dedup_key = (school_name, major_name)
            if dedup_key in seen_combinations:
                continue
            seen_combinations.add(dedup_key)
            ratio_str = cols[3] if len(cols) > 3 else ""
            rank_ratio_value = None
            try:
                if ratio_str and ratio_str != "—":
                    rank_ratio_value = float(ratio_str)
            except ValueError:
                pass
            hist_str = cols[4] if len(cols) > 4 else ""
            historical_min_rank = None
            if hist_str and hist_str != "—":
                hist_num = re.sub(r"[（(].*", "", hist_str).strip()
                try:
                    historical_min_rank = int(hist_num)
                except ValueError:
                    pass
            if school_name not in schools:
                schools[school_name] = {
                    "school_name": school_name,
                    "school_city": "",
                    "major_groups": [{"majors": []}],
                }
                school_order.append(school_name)
            schools[school_name]["major_groups"][0]["majors"].append({
                "major_name": major_name,
                "rank_ratio_tier": current_tier,
                "rank_ratio_value": rank_ratio_value,
                "historical_min_rank": historical_min_rank,
            })
    elif in_table and not line.startswith("|"):
        in_table = False

eligible_pool = [schools[name] for name in school_order]

# 3. 解析专业评估结论构建 passed_majors
me_text = Path("/sessions/69f7196913380806cd05b6a2/workspace/outputs/专业评估结论_山东.md").read_text(encoding="utf-8")
me_lines = me_text.splitlines()

passed_majors = []
current_light = None
in_table = False

for line in me_lines:
    line_stripped = line.strip()
    if not line_stripped:
        continue
    if "🟢" in line_stripped or "绿灯" in line_stripped:
        current_light = "green"
        in_table = False
        continue
    elif "🟡" in line_stripped or "黄灯" in line_stripped:
        current_light = "yellow"
        in_table = False
        continue
    elif "🔴" in line_stripped or "红灯" in line_stripped:
        current_light = "red"
        in_table = False
        continue
    if "|" in line_stripped:
        if "专业" in line_stripped and ("宽度" in line_stripped or "前提条件" in line_stripped or "红灯理由" in line_stripped):
            in_table = True
            continue
        if re.match(r"^\|[-| ]+\|$", line_stripped):
            continue
        if in_table and line_stripped.startswith("|") and current_light:
            cols = [c.strip() for c in line_stripped.split("|")]
            if len(cols) >= 2:
                major_str = cols[1]
                major_str = major_str.replace("**", "").strip()
                if not major_str or "专业" in major_str:
                    continue
                if current_light in ["green", "yellow"]:
                    parts = re.split(r"\s*/\s*|／", major_str)
                    for name in parts:
                        name = name.strip()
                        if name:
                            passed_majors.append({
                                "major_name": name,
                                "traffic_light": current_light,
                                "prerequisites": [],
                            })
    else:
        if not line_stripped.startswith("|") and not line_stripped.startswith(">"):
            in_table = False

# 4. 解析最终版策略报告构建 draft_plan
strategy_text = Path("/sessions/69f7196913380806cd05b6a2/workspace/outputs/志愿填报策略_山东_567_school_matcher_最终版.md").read_text(encoding="utf-8")
strategy_lines = strategy_text.splitlines()

volunteer_list = []
for line in strategy_lines:
    if not line.startswith("|") or "学校名称" in line or "—" in line:
        continue
    cols = [c.strip() for c in line.split("|")]
    if len(cols) < 5:
        continue
    try:
        serial = int(cols[1])
    except (ValueError, IndexError):
        continue
    school = cols[2]
    major = cols[3]
    rr_str = cols[4]
    if not school or not major or school == "学校名称":
        continue
    rank_ratio = None
    try:
        if rr_str and rr_str != "—":
            rank_ratio = float(rr_str)
    except ValueError:
        pass
    # 确定档位
    positioning = "稳"
    if rank_ratio:
        if rank_ratio > 1.2:
            positioning = "冲"
        elif rank_ratio < 1.0:
            positioning = "保"
    volunteer_list.append({
        "serial_number": serial,
        "school_name": school,
        "major_name": major,
        "positioning": positioning,
        "admission_probability": f"约{int((2.0 - (rank_ratio or 1.0)) / 2.0 * 100)}%" if rank_ratio else "未知",
        "rank_ratio": rank_ratio,
        "major_group_cleanliness": "🟢 干净",
    })

# 按序号排序
volunteer_list.sort(key=lambda x: x["serial_number"])

# 5. 构建 专业评估结果
专业评估结果 = {
    "green_majors": [m["major_name"] for m in passed_majors if m["traffic_light"] == "green"],
    "yellow_majors": [m["major_name"] for m in passed_majors if m["traffic_light"] == "yellow"],
    "all_passed": [m["major_name"] for m in passed_majors],
}

# 6. 构建输入
data = {
    "applicant_profile": applicant_profile,
    "eligible_pool": eligible_pool,
    "passed_majors": passed_majors,
    "draft_plan": {
        "volunteer_list": volunteer_list,
        "strategy_config": {
            "chong_count": len([v for v in volunteer_list if v["positioning"] == "冲"]),
            "wen_count": len([v for v in volunteer_list if v["positioning"] == "稳"]),
            "bao_count": len([v for v in volunteer_list if v["positioning"] == "保"]),
        },
    },
    "专业评估结果": 专业评估结果,
    "院校匹配_match_cards": {},
}

# 7. 运行 special-advisor
print("Running special-advisor pipeline...")
result = run(data)

# 8. 输出结果
out_path = Path("/sessions/69f7196913380806cd05b6a2/workspace/outputs/special_advisor_山东_567_result.json")
with out_path.open("w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f"Result written to {out_path}")
print(f"Status: {result.get('status')}")
if result.get('status') == 'success':
    print(f"Special tags: {result.get('special_tags', [])}")
    print(f"Warning count: {len(result.get('warnings', []))}")
    print(f"Adjustment count: {len(result.get('adjustments', []))}")
