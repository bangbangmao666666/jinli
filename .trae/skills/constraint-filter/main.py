"""constraint-filter CLI 入口。

用法：
    python main.py <考生画像.md>          # 自动保存到 outputs/ 并打印摘要
    python main.py -                      # 从 stdin 读取 JSON
    python main.py <考生画像.md> --output /path/to/result.json  # 指定输出路径

默认行为（不指定 --output 时）：
    自动保存到项目根目录的 outputs/ 文件夹，文件名含省份：
    - outputs/硬约束过滤结果_山东.md   （供下游 模块/Skill 直接阅读）

退出码：
    0  success
    2  任何 error 响应（供 shell 脚本判断）
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 允许 `python main.py` 直接在 skill 目录下运行
_SKILL_ROOT = Path(__file__).resolve().parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

from constraint_filter import run  # noqa: E402  (import after sys.path edit)
from constraint_filter.report_formatter import format_report  # noqa: E402


def _load_applicant(src: str) -> dict:
    if src == "-":
        return json.loads(sys.stdin.read())
    path = Path(src)
    with path.open("r", encoding="utf-8") as f:
        text = f.read()
    if path.suffix == ".md":
        return _parse_applicant_md(text)
    return json.loads(text)


def _parse_applicant_md(text: str) -> dict:
    """将考生画像 MD 文件解析为 constraint-filter 所需的 dict。

    MD 格式约定（见 SKILL.md「考生画像 MD 格式」章节）：
        - 省份：山东
        - 总分：566
        - 省内位次：54147
        - 高考模式：综合改革
        - 选科：物理、化学、生物
        - 性别：男
        - 考试年份：2024
        - 政审清白：是

        ## 体检信息
        - 色觉：正常
        - 视力左：4.8
        - 视力右：4.8
        - 身高(cm)：175
        - 体重(kg)：65
        - 听力正常：是
    """
    import re

    def _val(pattern: str, default=None):
        m = re.search(pattern, text)
        return m.group(1).strip() if m else default

    def _bool_val(pattern: str) -> bool:
        v = _val(pattern, "否")
        return v in ("是", "true", "True", "1", "yes")

    selected_raw = _val(r"[-*]\s*选科[：:]\s*(.+)")
    selected_subjects = []
    if selected_raw:
        selected_subjects = [s.strip() for s in re.split(r"[、,，/]", selected_raw) if s.strip()]

    result: dict = {
        "province":          _val(r"[-*]\s*省份[：:]\s*(.+)"),
        "total_score":       int(_val(r"[-*]\s*总分[：:]\s*(\d+)", 0)),
        "provincial_rank":   int(_val(r"[-*]\s*省内位次[：:]\s*(\d+)", 0)),
        "subject_category":  _val(r"[-*]\s*高考模式[：:]\s*(.+)"),
        "selected_subjects": selected_subjects,
        "gender":            _val(r"[-*]\s*性别[：:]\s*(.+)"),
        "exam_year":         int(_val(r"[-*]\s*考试年份[：:]\s*(\d+)", 0)),
        "political_review_clean": _bool_val(r"[-*]\s*政审清白[：:]\s*(.+)"),
    }

    # 体检信息（可选）
    color = _val(r"[-*]\s*色觉[：:]\s*(.+)")
    vl    = _val(r"[-*]\s*视力左[：:]\s*([\d.]+)")
    vr    = _val(r"[-*]\s*视力右[：:]\s*([\d.]+)")
    h     = _val(r"[-*]\s*身高\s*\(?cm\)?[：:]\s*(\d+)")
    w     = _val(r"[-*]\s*体重\s*\(?kg\)?[：:]\s*(\d+)")
    hear  = _val(r"[-*]\s*听力正常[：:]\s*(.+)")

    if any([color, vl, vr, h, w, hear]):
        result["physical_exam"] = {
            "color_blindness":  color or "正常",
            "vision_left":      float(vl) if vl else None,
            "vision_right":     float(vr) if vr else None,
            "height_cm":        int(h) if h else None,
            "weight_kg":        int(w) if w else None,
            "hearing_normal":   hear in ("是", "true", "True", "1", "yes") if hear else True,
            "other_conditions": [],
        }

    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="constraint-filter: 硬约束过滤模块 (硬约束过滤) 的命令行入口"
    )
    parser.add_argument("input", help="考生画像 JSON 文件路径，使用 - 表示从 stdin 读取")
    parser.add_argument("--pretty", action="store_true", help="按中文缩进美化 JSON 输出")
    parser.add_argument("--report", action="store_true", help="输出 Markdown 格式的人类可读报告（代替 JSON）")
    parser.add_argument("--output", "-o", help="将 JSON 结果保存到指定路径（同时自动生成同名 .md 文件）；不指定时自动保存到 outputs/", default=None)
    parser.add_argument(
        "--data-dir",
        help="覆盖默认的数据目录（默认 ./data）",
        default=None,
    )
    args = parser.parse_args(argv)

    applicant = _load_applicant(args.input)
    data_dir = Path(args.data_dir) if args.data_dir else None
    result = run(applicant, data_dir=data_dir)

    if args.report:
        output_text = format_report(result)
        if args.output:
            out_path = Path(args.output)
            out_path.write_text(output_text, encoding="utf-8")
            print(f"Markdown 报告已保存到：{out_path}", file=sys.stderr)
        else:
            print(output_text)
        return 0 if result.get("status") == "success" else 2

    # 默认输出路径：项目根目录下的 outputs/，文件名含省份
    _OUTPUTS_DIR = _SKILL_ROOT.parent.parent.parent / "结果"
    # 优先从结果中取（经过清洗的），其次从输入中取（原始的），最后兜底“未知省份”
    province = result.get("applicant_profile", {}).get("province") or applicant.get("province") or "未知省份"

    _OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    if args.output:
        md_path = Path(args.output).with_suffix(".md")
        json_path = Path(args.output)
    else:
        md_path = _OUTPUTS_DIR / f"1初步筛选_硬约束过滤结果_{province}.md"
        json_path = _OUTPUTS_DIR / f"1初步筛选_硬约束过滤结果_{province}.json"

    # 保存 JSON
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"JSON 结果已保存到：{json_path}", file=sys.stderr)

    # 保存 Markdown
    md_text = format_report(result)
    md_path.write_text(md_text, encoding="utf-8")
    print(f"Markdown 报告已保存到：{md_path}", file=sys.stderr)

    # 生成可选专业方向概览（前置 logic from major-evaluator）
    _generate_major_overview(result, _OUTPUTS_DIR)

    return 0 if result.get("status") == "success" else 2


def _generate_major_overview(result: dict, output_dir: Path) -> None:
    """生成可选专业方向概览 MD 文件，方便用户进行下一阶段的专业选择。"""
    import re
    from collections import Counter
    import datetime

    if result.get("status") != "success":
        return

    all_detail = result.get("all_majors_detail", [])
    eligible_majors = [d.get("major_name", "") for d in all_detail if d.get("status") == "eligible"]
    
    base_majors = []
    for m in eligible_majors:
        base_name = re.sub(r'[\(（].*?[\)）]', '', m).strip()
        if base_name:
            base_majors.append(base_name)

    counter = Counter(base_majors)
    top_categories = counter.most_common(100)

    profile = result.get("applicant_profile", {})
    province = profile.get("province", "未知")
    score = profile.get("total_score", "未知")
    today = datetime.date.today().strftime("%Y%m%d")

    filename = f"1初步筛选_可选专业方向概览_{province}_{score}分_{today}.md"
    dest_path = output_dir / filename

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
    print(f"可选专业方向概览已保存到：{dest_path}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
