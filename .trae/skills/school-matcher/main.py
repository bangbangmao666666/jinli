
#!/usr/bin/env python3
"""school-matcher CLI入口。

用法：
    python main.py <input.json> [--pretty] [--data-dir <path>]
    python main.py --school "东北电力大学" --major "电气工程及其自动化" [--pretty]
    python main.py -

默认行为（不指定 --output 时）：
    自动保存到项目根目录的 结果/ 文件夹，使用中文文件名：
    - 结果/院校匹配结果_<省份>_<分数>.md

退出码：
    0  success
    2  任何 error 响应
"""
import argparse
import json
import sys
from pathlib import Path

# 允许直接在skill目录下运行
_SKILL_ROOT = Path(__file__).resolve().parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

from school_matcher import run
from school_matcher.report_formatter import format_report
from school_matcher.md_parser import parse_硬约束过滤_md, parse_专业评估_md


def _load_json(src):
    """从文件或stdin加载JSON。"""
    if src == "-":
        return json.loads(sys.stdin.read())
    path = Path(src)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _load_from_md(硬约束过滤_path, 专业评估_path=None):
    """从 硬约束过滤模块/2 的 MD 输出文件构建 school-matcher 输入结构。"""
    parsed = parse_硬约束过滤_md(硬约束过滤_path)
    data = {
        "applicant_profile": parsed["applicant_profile"],
        "eligible_pool": parsed["eligible_pool"],
        "passed_majors": [],
    }

    if 专业评估_path:
        data["passed_majors"] = parse_专业评估_md(专业评估_path)

    return data


def main(argv=None):
    """主函数。"""
    parser = argparse.ArgumentParser(
        description="school-matcher: 院校匹配模块 - 院校匹配Skill",
    )

    # 输入选项组一：从文件输入
    parser.add_argument(
        "input",
        nargs="?",
        help="输入JSON文件路径，使用-表示从stdin读取",
    )

    # 输入选项组二：单查询模式
    parser.add_argument(
        "--school",
        help="院校名称（单查询模式）",
        default="",
    )
    parser.add_argument(
        "--major",
        help="专业名称（单查询模式）",
        default="",
    )

    # 考生信息参数
    parser.add_argument(
        "--province",
        help="省份",
        default="河南",
    )
    parser.add_argument(
        "--score",
        type=int,
        help="高考分数",
        default=550,
    )
    parser.add_argument(
        "--rank",
        type=int,
        help="省内排名",
        default=50000,
    )
    parser.add_argument(
        "--city",
        action="append",
        help="意向城市（可多次添加）",
        default=[],
    )
    parser.add_argument(
        "--majors",
        action="append",
        help="指定要进行院校匹配的专业名称（可多次添加）",
        default=[],
    )

    # MD 流水线模式（直接读取 硬约束过滤模块/2 的 MD 输出）
    parser.add_argument(
        "--专业评估",
        help="专业评估模块 专业评估输出的 MD 文件路径（可选，配合 .md 输入文件使用）",
        default=None,
    )

    # 通用选项
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="按中文缩进美化 JSON 输出（仅影响 stdout，不影响文件输出）",
    )
    parser.add_argument(
        "--output", "-o",
        help="将 Markdown 报告保存到指定路径；不指定时自动保存到 结果/",
        default=None,
    )
    parser.add_argument(
        "--data-dir",
        help="覆盖默认的数据目录",
        default=None,
    )

    args = parser.parse_args(argv)

    # 确定输入数据
    if args.school or args.major:
        # 单查询模式
        data = {
            "school_name": args.school,
            "major_name": args.major,
            "applicant_profile": {
                "province": args.province,
                "total_score": args.score,
                "provincial_rank": args.rank,
                "preferred_cities": args.city,
            },
            "selected_majors": args.majors,
        }
    elif args.input and str(args.input).endswith(".md"):
        # MD 流水线模式：直接解析 硬约束过滤模块/2 的 MD 输出
        print(f"检测到 MD 文件输入，从 硬约束过滤模块 输出解析数据：{args.input}", file=sys.stderr)
        data = _load_from_md(args.input, args.专业评估)
        data["selected_majors"] = args.majors
        if args.专业评估:
            print(f"同时加载 专业评估模块 专业评估结果：{args.专业评估}", file=sys.stderr)
    else:
        # 文件输入模式（JSON）
        if not args.input:
            parser.error("请提供输入文件（.json 或 .md）或使用--school/--major参数")
        data = _load_json(args.input)
        # 如果命令行提供了 --majors，覆盖 JSON 中的值
        if args.majors:
            data["selected_majors"] = args.majors

    # 运行
    result = run(data, data_dir=args.data_dir)

    # 提取考生信息（用于报告头部）
    applicant_profile = data.get("applicant_profile", {})

    # 确定输出路径：默认写入项目根目录 结果/，使用中文文件名
    _OUTPUTS_DIR = _SKILL_ROOT.parent.parent.parent / "结果"
    _OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    province = applicant_profile.get("province", "未知省份")
    score = applicant_profile.get("total_score", "")
    score_str = f"_{score}" if score else ""

    if args.output:
        md_path = Path(args.output)
    else:
        md_path = _OUTPUTS_DIR / f"3选学校_院校匹配结果_{province}{score_str}.md"

    md_text = format_report(result, applicant_profile)
    md_path.write_text(md_text, encoding="utf-8")
    print(f"Markdown 报告已保存到：{md_path}", file=sys.stderr)

    # 返回码
    return 0 if result.get("status") == "success" else 2


if __name__ == "__main__":
    raise SystemExit(main())

