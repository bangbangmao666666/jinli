"""strategy-planner CLI 入口。

用法：
    python main.py <input.json>                # 自动保存 Markdown 报告到 outputs/
    python main.py -                           # 从 stdin 读取 JSON
    python main.py <input.json> --pretty       # 同时打印 JSON 到 stdout
    python main.py <input.json> -o result.md   # 指定输出路径

默认行为（不指定 --output 时）：
    自动保存到项目根目录的 outputs/ 文件夹，使用中文文件名：
    - outputs/填报策略方案_<省份>_<分数>.md

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

from strategy_planner import run  # noqa: E402  (import after sys.path edit)
from strategy_planner.report_formatter import format_report  # noqa: E402


def _load_input(src: str) -> dict:
    if src == "-":
        return json.loads(sys.stdin.read())
    path = Path(src)
    if path.suffix.lower() == ".md":
        from strategy_planner.md_parser import parse_school_matcher_md
        return parse_school_matcher_md(path.read_text(encoding="utf-8"))
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="strategy-planner: 填报策略模块 (填报策略) 的命令行入口"
    )
    parser.add_argument("input", help="输入 JSON 文件路径，使用 - 表示从 stdin 读取")
    parser.add_argument("--pretty", action="store_true", help="将 JSON 结果打印到 stdout（调试用）")
    parser.add_argument(
        "--output", "-o",
        help="将 Markdown 报告保存到指定路径；不指定时自动保存到 outputs/",
        default=None,
    )
    args = parser.parse_args(argv)

    input_data = _load_input(args.input)
    result = run(input_data)

    # 提取考生信息（用于文件命名）
    applicant = input_data.get("applicant_profile", {})
    province = applicant.get("province", "未知省份")
    score = applicant.get("total_score", "")
    score_str = f"_{score}" if score else ""

    # 确定输出路径：默认写入项目根目录 结果/
    _OUTPUTS_DIR = _SKILL_ROOT.parent.parent.parent / "结果"
    _OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    if args.output:
        md_path = Path(args.output)
    else:
        md_path = _OUTPUTS_DIR / f"4填报策略_填报策略方案_{province}{score_str}.md"

    md_text = format_report(result)
    md_path.write_text(md_text, encoding="utf-8")
    print(f"Markdown 报告已保存到：{md_path}", file=sys.stderr)

    # --pretty 时额外打印 JSON（调试用）
    if args.pretty:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0 if result.get("status") == "success" else 2


if __name__ == "__main__":
    raise SystemExit(main())
