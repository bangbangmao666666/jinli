"""major-evaluator CLI 入口。

用法：
    python main.py 硬约束过滤结果.json              # 流水线模式（读取 硬约束过滤模块 输出）
    python main.py 硬约束过滤结果.json --pretty     # 中文友好输出
    python main.py --major "电气工程及其自动化"     # 单专业查询模式
    python main.py --major "电气工程" --school "郑州大学"  # 学校+专业查询模式
    python main.py -                               # 从 stdin 读取 硬约束过滤模块 输出

v1.1 新增参数：
    --interest "电力系统" --interest "稳定工作"    # 考生感兴趣的方向（可重复）
    --reject "医学" --reject "化学"               # 明确排斥的方向（可重复）
    --personality 偏稳定                          # 性格倾向（偏稳定/偏拼搏/未定）
    --economy 普通                                # 家庭经济条件（宽裕/普通/紧张）
    --family-resources                            # 家庭有行业资源/人脉（flag）
    --interest-source 考生本人表达                 # 意愿信息来源（考生本人表达/家长代述/未区分）

退出码：
    0  success 或 pending_evaluation（等待 AI 执行）
    2  任何 error 响应
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SKILL_ROOT = Path(__file__).resolve().parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

from major_evaluator import run  # noqa: E402


def _load_json(src: str) -> dict:
    if src == "-":
        return json.loads(sys.stdin.read())
    with Path(src).open("r", encoding="utf-8") as f:
        return json.load(f)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="major-evaluator: 专业评估模块（专业五维深度评估）的命令行入口"
    )

    # 输入来源（二选一）
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "input",
        nargs="?",
        help="硬约束过滤模块 输出的 JSON 文件路径（流水线模式），使用 - 表示从 stdin 读取",
    )
    group.add_argument(
        "--major",
        help="直接指定专业名称（单专业查询模式）",
    )

    parser.add_argument(
        "--school",
        help="指定学校名称（与 --major 组合使用，变为学校+专业查询模式）",
        default="",
    )

    # 硬件信息参数（v1.0 已有）
    parser.add_argument(
        "--math-score",
        type=int,
        help="考生数学单科成绩（0-150）",
        dest="math_score",
    )
    parser.add_argument(
        "--physics-score",
        type=int,
        help="考生物理单科成绩（0-150）",
        dest="physics_score",
    )
    parser.add_argument(
        "--system-preference",
        choices=["体制内", "体制外", "未定"],
        help="考生体制内外偏好",
        dest="system_preference",
    )
    parser.add_argument(
        "--region",
        help="考生意向就业城市/区域",
        dest="preferred_region",
    )

    # v1.1 新增：意愿信息参数
    parser.add_argument(
        "--interest",
        action="append",
        help="考生感兴趣的方向（可重复，例：--interest 电力系统 --interest 稳定工作）",
        dest="interest_directions",
        metavar="方向",
    )
    parser.add_argument(
        "--reject",
        action="append",
        help="考生明确排斥的方向（可重复，例：--reject 医学 --reject 化学）",
        dest="explicit_rejections",
        metavar="方向",
    )
    parser.add_argument(
        "--personality",
        choices=["偏稳定", "偏拼搏", "未定"],
        help="考生性格倾向",
        dest="personality_tendency",
    )
    parser.add_argument(
        "--economy",
        choices=["宽裕", "普通", "紧张"],
        help="家庭经济条件",
        dest="family_economy_level",
    )
    parser.add_argument(
        "--family-resources",
        action="store_true",
        help="家庭在特定行业有资源/人脉（flag，提供则为 true）",
        dest="family_has_industry_resources",
    )
    parser.add_argument(
        "--interest-source",
        choices=["考生本人表达", "家长代述", "未区分"],
        help="意愿信息来源",
        dest="interest_source",
    )

    parser.add_argument("--pretty", action="store_true", help="按中文缩进美化输出")
    parser.add_argument(
        "--overview",
        action="store_true",
        help="生成可选专业方向概览（盲选引导模式），而不是进行全量专业评估",
    )
    parser.add_argument(
        "--output",
        help="将结果保存到指定文件路径（.json 保存 JSON，.md 保存 Markdown 摘要）",
        dest="output_path",
        metavar="PATH",
    )
    parser.add_argument(
        "--output-dir",
        help="自动生成文件名并保存到指定目录（默认文件名：专业评估报告_<省份>_<分数>_<日期>.md）",
        dest="output_dir",
        metavar="DIR",
    )

    args = parser.parse_args(argv)

    # 构造 applicant_profile（来自 CLI 参数）
    applicant_profile: dict = {}

    # 硬件信息
    if args.math_score is not None:
        applicant_profile["math_score"] = args.math_score
    if args.physics_score is not None:
        applicant_profile["physics_score"] = args.physics_score
    if args.system_preference:
        applicant_profile["system_preference"] = args.system_preference
    if args.preferred_region:
        applicant_profile["preferred_region"] = args.preferred_region

    # v1.1 意愿信息
    if args.interest_directions:
        applicant_profile["interest_directions"] = args.interest_directions
    if args.explicit_rejections:
        applicant_profile["explicit_rejections"] = args.explicit_rejections
    if args.personality_tendency:
        applicant_profile["personality_tendency"] = args.personality_tendency
    if args.family_economy_level:
        applicant_profile["family_economy_level"] = args.family_economy_level
    if args.family_has_industry_resources:
        applicant_profile["family_has_industry_resources"] = True
    if args.interest_source:
        applicant_profile["interest_source"] = args.interest_source

    # 构造输入数据
    if args.major:
        data = {
            "major_name": args.major,
            "school_name": args.school,
            "applicant_profile": applicant_profile,
        }
    elif args.input:
        data = _load_json(args.input)
        # CLI 传入的 applicant_profile 字段覆盖 硬约束过滤模块 输出中的同名字段
        if applicant_profile and isinstance(data.get("applicant_profile"), dict):
            data["applicant_profile"].update(applicant_profile)
            
        if args.overview:
            _generate_overview(data, args.output_dir)
            return 0
    else:
        parser.error("请提供 硬约束过滤模块 输出文件路径，或使用 --major 指定专业名称。")
        return 2

    result = run(data)
    indent = 2 if args.pretty else None
    output_str = json.dumps(result, ensure_ascii=False, indent=indent)
    print(output_str)

    # 保存到文件：显式指定路径时用指定路径，否则默认自动保存到 outputs/
    if args.output_path or args.output_dir:
        _save_result(result, output_str, args.output_path, args.output_dir, data)
    else:
        _save_result_default(result, output_str, data)

    status = result.get("status")
    # pending_evaluation 是正常状态（等待 Trae Solo AI 执行评估）
    return 0 if status in ("success", "pending_evaluation") else 2


def _save_result(
    result: dict,
    output_str: str,
    output_path: str | None,
    output_dir: str | None,
    input_data: dict,
) -> None:
    """将评估结果保存到文件。"""
    import datetime

    if output_path:
        dest = Path(output_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.suffix.lower() == ".md":
            dest.write_text(_to_markdown(result, input_data), encoding="utf-8")
        else:
            dest.write_text(output_str, encoding="utf-8")
        print(f"\n✅ 结果已保存：{dest}", file=sys.stderr)
        return

    if output_dir:
        today = datetime.date.today().strftime("%Y%m%d")
        # 从 input_data 推断省份和分数
        profile = input_data.get("applicant_profile", {})
        province = input_data.get("province", profile.get("province", ""))
        score = input_data.get("total_score", profile.get("total_score", ""))
        province_str = f"_{province}" if province else ""
        score_str = f"_{score}分" if score else ""
        filename = f"2选专业_专业评估报告{province_str}{score_str}_{today}.md"
        dest = Path(output_dir) / filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(_to_markdown(result, input_data), encoding="utf-8")
        print(f"\n✅ 结果已保存：{dest}", file=sys.stderr)


def _save_result_default(result: dict, output_str: str, input_data: dict) -> None:
    """默认自动保存到项目根目录 outputs/ 下，文件名：专业评估结论_<省份>.md。"""
    # 推断省份
    profile = input_data.get("applicant_profile", {})
    province = input_data.get("province", profile.get("province", ""))

    # outputs/ 位置：skill 根目录上溯三级到项目根目录
    outputs_dir = _SKILL_ROOT.parent.parent.parent / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    province_str = f"_{province}" if province else ""
    md_path = outputs_dir / f"2选专业_专业评估报告{province_str}.md"
    md_path.write_text(_to_markdown(result, input_data), encoding="utf-8")
    print(f"\n✅ 结果已保存：{md_path}", file=sys.stderr)


def _to_markdown(result: dict, input_data: dict) -> str:
    """将评估结果转为 Markdown 摘要格式。"""
    import datetime

    lines: list[str] = []
    profile = input_data.get("applicant_profile", {})
    province = input_data.get("province", profile.get("province", ""))
    score = input_data.get("total_score", profile.get("total_score", ""))
    rank = input_data.get("provincial_rank", profile.get("provincial_rank", ""))
    subjects = input_data.get("selected_subjects", profile.get("selected_subjects", []))
    gender = input_data.get("gender", profile.get("gender", ""))
    
    math_score = profile.get("math_score")
    physics_score = profile.get("physics_score")
    system_pref = profile.get("system_preference", "未提供")
    
    generated_at = result.get("generated_at", datetime.datetime.now().isoformat())

    lines.append(f"# 专业评估结论")
    
    # 页头：基本信息
    parts = []
    if province: parts.append(province)
    if score: parts.append(f"{score}分")
    if rank: parts.append(f"位次{rank}")
    if subjects: parts.append("".join(subjects) if isinstance(subjects, list) else subjects)
    if gender: parts.append(gender)
    lines.append(f"**考生**：{' · '.join(parts)}  ")
    
    # 页头：补充信息
    supp_parts = []
    math_str = str(math_score) if math_score is not None else "未提供"
    phys_str = str(physics_score) if physics_score is not None else "未提供"
    supp_parts.append(f"数学{math_str} / 物理{phys_str}")
    supp_parts.append(f"体制{system_pref}偏好")
    lines.append(f"**补充信息**：{' · '.join(supp_parts)}  ")
    
    lines.append(f"**评估时间**：{generated_at[:10]}  ")
    lines.append(f"**评估范围**：冲+稳档中的核心专业方向")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 分类汇总汇总表格
    evaluations = result.get("evaluations", [])
    if not evaluations and result.get("major_name"):
        evaluations = [result]

    for color, title in [("🟢 绿灯", "推荐"), ("🟡 黄灯", "有条件推荐"), ("🔴 红灯", "建议谨慎")]:
        filtered = [e for e in evaluations if color in e.get("traffic_light", "")]
        if not filtered:
            continue
            
        lines.append(f"## {color}专业（{title}）")
        lines.append("")
        if "🟢" in color:
            lines.append("| 专业 | 宽度 | 体制导向 | 地域性 | 核心理由（含来源） |")
            lines.append("|------|------|---------|--------|---------|")
            for e in filtered:
                name = e.get("major_name", "未知")
                width = e.get("dimension_1_width", {}).get("rating", "-")
                system = e.get("dimension_2_system_orientation", {}).get("primary_arena", "-")
                region = e.get("dimension_3_regional_dependency", {}).get("strength", "-")
                reasons = "; ".join([r.get("reason", r) if isinstance(r, dict) else r for r in e.get("traffic_light_reasons", [])])
                lines.append(f"| {name} | {width} | {system} | {region} | {reasons} |")
        else:
            lines.append("| 专业 | 前提条件/理由 | 主要风险（含来源） |")
            lines.append("|------|---------|---------|")
            for e in filtered:
                name = e.get("major_name", "未知")
                prereqs = "; ".join(e.get("traffic_light_prerequisites", [])) or "-"
                reasons = "; ".join([r.get("reason", r) if isinstance(r, dict) else r for r in e.get("traffic_light_reasons", [])])
                lines.append(f"| {name} | {prereqs if '🟡' in color else reasons} | {reasons if '🟡' in color else '-'} |")
        lines.append("")

    # 数据来源汇总
    all_refs = {}
    for e in evaluations:
        for ref in e.get("references", []):
            url = ref.get("url")
            if url:
                all_refs[url] = ref

    if all_refs:
        lines.append("## 本次评估数据来源汇总")
        lines.append("")
        lines.append("| 编号 | 来源标题 | 机构 | 年份 | 链接 | 可信级别 |")
        lines.append("|------|---------|------|------|------|---------|")
        for i, (url, ref) in enumerate(all_refs.items(), 1):
            title = ref.get("title", "未知标题")
            inst = ref.get("institution", "-")
            year = ref.get("date", "-")
            tier = ref.get("tier", "unknown")
            lines.append(f"| [{i}] | {title} | {inst} | {year} | {url} | {tier} |")
        lines.append("")

    lines.append("⚠️ **数据核实提示**：以上评估基于公开搜索数据。建议同时参考目标院校《就业质量报告》和教育部阳光高考平台。")

    return "\n".join(lines)


def _card_to_md(card: dict) -> list[str]:
    """此函数在新的 _to_markdown 中不再单独使用，保留空实现以兼容旧调用。"""
    return []


def _generate_overview(data: dict, output_dir: str | None) -> None:
    import re
    from collections import Counter
    import datetime

    all_detail = data.get("all_majors_detail", [])
    eligible_majors = [d.get("major_name", "") for d in all_detail if d.get("status") == "eligible"]
    
    if not eligible_majors and "eligible_pool" in data:
        for school in data["eligible_pool"]:
            for group in school.get("major_groups", []):
                for major in group.get("majors", []):
                    eligible_majors.append(major.get("major_name", ""))
                    
    base_majors = []
    for m in eligible_majors:
        base_name = re.sub(r'[\(（].*?[\)）]', '', m).strip()
        if base_name:
            base_majors.append(base_name)

    counter = Counter(base_majors)
    top_categories = counter.most_common(100)

    profile = data.get("applicant_profile", {})
    province = data.get("province", profile.get("province", ""))
    score = data.get("total_score", profile.get("total_score", ""))
    province_str = f"_{province}" if province else ""
    score_str = f"_{score}分" if score else ""
    today = datetime.date.today().strftime("%Y%m%d")

    filename = f"2选专业_可选专业方向概览{province_str}{score_str}_{today}.md"
    
    if output_dir:
        dest_dir = Path(output_dir)
    else:
        dest_dir = _SKILL_ROOT.parent.parent.parent / "结果"
    
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / filename

    lines = [
        f"# 可选专业方向概览",
        "",
        f"**省份**：{province} | **分数**：{score} | **生成日期**：{today}",
        "",
        "> 💡 **选专业建议**：",
        "> 此处给出的专业分类数量排名仅供参考，不代表专业好坏。",
        "> 面对几千个专业选项容易迷茫，您可以从下面的清单中结合个人兴趣：",
        "> 1. 挑选 **3-5个最感兴趣** 的方向",
        "> 2. 标出 **坚决不想去** 的方向",
        "> ",
        "> 告诉 AI 助手，它将为您启动针对性的【深度专业评估】。",
        "",
        "基于您的硬约束条件，系统从所有可报院校中提取了可填报的专业方向。以下为您汇总的 Top 100 常见专业方向（按可报院校数量排序）：",
        "",
        "| 专业大类/名称 | 可选院校数量 |",
        "|--------------|--------------|"
    ]
    
    for name, count in top_categories:
        lines.append(f"| {name} | {count}所 |")

    dest_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n✅ 概览已保存：{dest_path}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
