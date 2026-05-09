"""MD 文件解析模块。

解析 硬约束过滤模块 (constraint-filter) 和 专业评估模块 (major-evaluator) 的 Markdown 输出，
转换为 school-matcher 可直接使用的输入结构。
"""
import re
from pathlib import Path


def parse_硬约束过滤_md(filepath):
    """解析 硬约束过滤模块 输出的 Markdown 文件。

    Args:
        filepath: MD文件路径（str 或 Path）

    Returns:
        dict: {
            "applicant_profile": {...},
            "eligible_pool": [...]  # 按院校分组，含 major_groups
        }

    Raises:
        ValueError: 如果文件格式无法解析
    """
    text = Path(filepath).read_text(encoding="utf-8")
    lines = text.splitlines()

    applicant_profile = _parse_applicant_profile(lines)
    eligible_pool = _parse_eligible_pool(lines)

    if not applicant_profile.get("province"):
        raise ValueError(f"无法从 {filepath} 解析考生省份，请确认文件是 硬约束过滤模块 的输出")

    return {
        "applicant_profile": applicant_profile,
        "eligible_pool": eligible_pool,
    }


def parse_专业评估_md(filepath):
    """解析 专业评估模块 输出的 Markdown 文件，提取绿灯/黄灯专业清单。

    Args:
        filepath: MD文件路径（str 或 Path）

    Returns:
        list: passed_majors，每项 {"major_name": "...", "traffic_light": "green|yellow", "prerequisites": []}
    """
    text = Path(filepath).read_text(encoding="utf-8")
    lines = text.splitlines()
    return _parse_passed_majors(lines)


# ──────────────────────────────────────────────────────
# 内部解析函数
# ──────────────────────────────────────────────────────

def _parse_applicant_profile(lines):
    """从考生画像部分提取考生信息。

    容错处理：字段行可能带有"- "前缀、全角冒号或半角冒号、首尾空格。
    """
    profile = {}
    in_section = False
    section_sep_count = 0

    for line in lines:
        if "考生画像" in line:
            in_section = True
            section_sep_count = 0
            continue

        if in_section and "====" in line:
            section_sep_count += 1
            if section_sep_count >= 1 and profile:
                break
            continue

        if not in_section:
            continue

        # 去掉行首空白和"- "列表前缀，统一全角冒号为半角
        line = line.strip().lstrip("- ").replace("：", ":")

        def _val(prefix):
            """提取 'prefix:value' 中的 value，容忍冒号前后空格。"""
            if line.lower().startswith(prefix.lower()):
                return line[len(prefix):].strip().lstrip(":").strip()
            return None

        v = _val("省份")
        if v is not None:
            profile["province"] = v
            continue
        v = _val("性别")
        if v is not None:
            profile["gender"] = v
            continue
        v = _val("总分")
        if v is not None:
            score_str = re.sub(r"[分\s,，]", "", v)
            try:
                profile["total_score"] = int(score_str)
            except ValueError:
                pass
            continue
        v = _val("位次")
        if v is not None:
            rank_str = re.sub(r"[名\s,，]", "", v)
            try:
                profile["provincial_rank"] = int(rank_str)
            except ValueError:
                pass
            continue
        v = _val("选科")
        if v is not None:
            subjects = [s.strip() for s in re.split(r"[+＋+\s/／、]+", v) if s.strip()]
            profile["selected_subjects"] = subjects
            continue
        v = _val("体检")
        if v is not None:
            profile["physical_exam_note"] = v

    return profile


def _parse_eligible_pool(lines):
    """从冲/稳/保档表格提取院校-专业，按院校分组。

    输出格式（与 constraint-filter JSON 输出保持一致）：
    [
        {
            "school_name": "...",
            "school_city": "",
            "major_groups": [
                {
                    "majors": [
                        {"major_name": "...", "rank_ratio_tier": "冲档|稳档|保档"}
                    ]
                }
            ]
        }
    ]
    """
    current_tier = None
    # 保持院校首次出现顺序
    school_order = []
    schools = {}  # school_name -> dict
    seen_combinations = set()  # 去重：(school_name, major_name)

    in_table = False

    tier_keywords = {"冲档": "冲档", "稳档": "稳档", "保档": "保档"}

    for line in lines:
        # 检测档位标题行，如【冲档】
        for key, val in tier_keywords.items():
            if f"【{key}】" in line:
                current_tier = val
                in_table = False
                break

        # 检测表头行
        if "| 学校 |" in line and "| 专业 |" in line:
            in_table = True
            continue

        # 跳过表头分隔行
        if in_table and re.match(r"^\|[-| ]+\|$", line):
            continue

        # 解析数据行
        if in_table and line.startswith("|") and current_tier:
            cols = [c.strip() for c in line.split("|")]
            # | 学校 | 专业 | rank_ratio | 历史最低位次 |
            # cols 索引: 0=空, 1=学校, 2=专业, 3=rank_ratio, 4=历史位次, 5=空
            if len(cols) >= 5:
                school_name = cols[1]
                major_name = cols[2]

                if not school_name or not major_name:
                    continue

                # 去重：同一院校-专业组合只保留第一次出现
                dedup_key = (school_name, major_name)
                if dedup_key in seen_combinations:
                    continue
                seen_combinations.add(dedup_key)

                # 解析 rank_ratio_value
                ratio_str = cols[3] if len(cols) > 3 else ""
                rank_ratio_value = None
                try:
                    if ratio_str and ratio_str != "—":
                        rank_ratio_value = float(ratio_str)
                except ValueError:
                    pass

                # 解析历史最低位次（格式如 "26467（2024）"）
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

    return [schools[name] for name in school_order]


def _parse_passed_majors(lines):
    """从 专业评估模块 的输出中提取绿灯/黄灯专业。

    支持两种格式：
    1. 总览表格模式（含"专业方向"和"红绿灯"列）
    2. 分章节表格模式（按 🟢绿灯/🟡黄灯/🔴红灯 分章节，每章有单独表格）
    """
    passed = []
    current_light = None  # green, yellow, red
    in_table = False

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 模式2：检测章节标题
        if "🟢" in line or "绿灯" in line:
            current_light = "green"
            in_table = False
            continue
        elif "🟡" in line or "黄灯" in line:
            current_light = "yellow"
            in_table = False
            continue
        elif "🔴" in line or "红灯" in line:
            current_light = "red"
            in_table = False
            continue

        # 检测表格
        if "|" in line:
            if "专业" in line and ("宽度" in line or "前提条件" in line or "红灯理由" in line):
                in_table = True
                continue
            if re.match(r"^\|[-| ]+\|$", line):
                continue

            if in_table and line.startswith("|") and current_light:
                cols = [c.strip() for c in line.split("|")]
                if len(cols) >= 2:
                    major_str = cols[1]
                    # 去掉加粗标识 **专业名**
                    major_str = major_str.replace("**", "").strip()

                    if not major_str or "专业" in major_str:
                        continue

                    # 只有绿灯和黄灯才加入 passed
                    if current_light in ["green", "yellow"]:
                        # 展开复合名称
                        parts = re.split(r"\s*/\s*|／", major_str)
                        for name in parts:
                            name = name.strip()
                            if name:
                                passed.append({
                                    "major_name": name,
                                    "traffic_light": current_light,
                                    "prerequisites": [],
                                })
        else:
            # 离开表格
            if not line.startswith("|") and not line.startswith(">"):
                in_table = False

    # 如果上述逻辑没搜到（可能是老格式），尝试原有的总览表逻辑
    if not passed:
        passed = _parse_passed_majors_legacy(lines)

    return passed


def _parse_passed_majors_legacy(lines):
    """兼容老格式：从 专业评估模块 评估总览表格提取。"""
    passed = []
    in_summary = False
    for line in lines:
        if "| 专业方向 |" in line and ("| 红绿灯 |" in line or "红绿灯" in line):
            in_summary = True
            continue
        if in_summary and re.match(r"^\|[-| ]+\|$", line):
            continue
        if in_summary and line.startswith("|"):
            cols = [c.strip() for c in line.split("|")]
            if len(cols) >= 4:
                major_str = cols[1]
                light_str = cols[2]
                if "🔴" in light_str or "红灯" in light_str: continue
                light = "green" if ("🟢" in light_str or "绿灯" in light_str) else "yellow"
                parts = re.split(r"\s*/\s*|／", major_str)
                for name in parts:
                    name = name.strip()
                    if name:
                        passed.append({"major_name": name, "traffic_light": light, "prerequisites": []})
        elif in_summary and not line.startswith("|"):
            in_summary = False
    return passed
