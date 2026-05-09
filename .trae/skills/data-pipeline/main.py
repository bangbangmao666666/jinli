"""数据准备 CLI 入口。

子命令：
  detect  <file>                   识别文件类型
  extract <file> [--output f.json] 提取原始数据
  run     <file> [选项]            一站式：detect+extract+normalize+validate（不写入，等确认）
  store   <normalized.json> [选项] 写入 constraint-filter 数据目录

用法示例：
  python3 main.py detect ~/Downloads/henan_2026.pdf
  python3 main.py run ~/Downloads/henan_2026.pdf --province 河南 --year 2026
  python3 main.py store /tmp/normalized.json --overwrite
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SKILL_ROOT = Path(__file__).resolve().parent
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

from data_agent.pipeline import (  # noqa: E402
    detect, extract, normalize, validate, store, run_full_pipeline
)
from data_agent.errors import DataPipelineError  # noqa: E402


def _load_intermediate(path: Path) -> dict:
    """读取中间归一化文件，同时支持 JSON 和 JSONL 两种格式。"""
    if path.suffix == ".jsonl":
        meta: dict = {}
        records: list = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if obj.get("__meta__"):
                    meta = {k: v for k, v in obj.items() if k != "__meta__"}
                else:
                    records.append(obj)
        # 重组为归一化结构
        key = "data" if "type" in meta else "schools"
        return {**meta, key: records}
    else:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)


def _json_print(obj: dict, pretty: bool = True) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2 if pretty else None))


def cmd_detect(args: argparse.Namespace) -> int:
    try:
        result = detect(args.file)
        _json_print(result)
        return 0
    except DataPipelineError as exc:
        _json_print(exc.to_dict())
        return 2


def cmd_extract(args: argparse.Namespace) -> int:
    try:
        result = extract(args.file)
        if args.output:
            out = Path(args.output)
            out.parent.mkdir(parents=True, exist_ok=True)
            with out.open("w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"✅ 提取完成，已写入 {out}")
            # 打印摘要
            pages = result.get("total_pages") or len(result.get("sheets", []))
            tables = len(result.get("all_tables_flat") or result.get("sheets", []))
            print(f"   文件：{result['file']}")
            print(f"   页数/Sheet数：{pages}，表格数：{tables}")
        else:
            _json_print(result)
        return 0
    except DataPipelineError as exc:
        _json_print(exc.to_dict())
        return 2


def cmd_run(args: argparse.Namespace) -> int:
    hint: dict = {}
    if args.province:
        hint["province"] = args.province
    if args.year:
        hint["valid_for_year"] = args.year

    _OUTPUTS_DIR = _SKILL_ROOT.parent.parent.parent / "结果"
    _OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    # 中间 JSONL 文件写入 outputs/.tmp/，不污染 outputs/ 根目录
    _TMP_DIR = _OUTPUTS_DIR / ".tmp"
    _TMP_DIR.mkdir(parents=True, exist_ok=True)
    import tempfile
    tmp_path = Path(tempfile.mktemp(suffix=".jsonl", dir=str(_TMP_DIR)))

    result = run_full_pipeline(
        args.file,
        user_hint=hint if hint else None,
        save_intermediate=str(tmp_path),
    )

    if result.get("status") == "error":
        _json_print(result)
        return 2

    report = result.get("validation_report", {})
    stats = report.get("stats", {})
    province = stats.get("province") or args.province or "未知"
    year = stats.get("valid_for_year") or args.year or "未知"
    data_type = stats.get("data_type", "admission_plan")

    _TYPE_LABEL = {
        "admission_plan":        "招生计划",
        "major_admission_scores": "录取位次",
        "score_rank_table":      "一分一段表",
        "admission_filing":      "投档情况",
    }
    type_label = _TYPE_LABEL.get(data_type, data_type)

    # 投档情况需区分第几次，避免三个文件互相覆盖
    if data_type == "admission_filing":
        round_num = result.get("normalized", {}).get("round_number", "?")
        type_label = f"第{round_num}次投档情况"

    # 中间 JSONL 文件放在 outputs/.tmp/（不污染 outputs/ 根目录）
    data_filename = f"数据导入_{province}_{year}_{type_label}.jsonl"
    if args.output:
        data_path = Path(args.output)
    else:
        data_path = _TMP_DIR / data_filename

    # 移动临时文件到最终路径（自动创建目标目录）
    if tmp_path.exists():
        import shutil
        data_path = data_path.resolve()
        data_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(tmp_path), str(data_path))

    # 生成 MD 摘要
    md_lines = [
        f"# 数据导入摘要 — {province} {year} {type_label}",
        "",
        f"- 来源文件：{stats.get('source_raw_filename', '?')}",
        f"- 省份：{province}",
        f"- 年份：{year}",
        f"- 数据类型：{type_label}",
    ]
    if data_type == "admission_plan":
        md_lines += [
            f"- 学校数：{stats.get('total_schools', 0)} 所",
            f"- 专业组数：{stats.get('total_major_groups', 0)} 个",
            f"- 专业数：{stats.get('total_majors', 0)} 个",
        ]
    else:
        md_lines.append(f"- 记录数：{stats.get('total_records', 0)} 条")

    md_lines += ["", f"- 归一化数据文件：`{data_path.name}`"]

    ready = result.get("ready_to_store", False)
    md_lines += ["", f"## 验证结果：{'✅ 通过' if ready else '❌ 未通过'}"]

    if report.get("errors"):
        md_lines += ["", "### 必须修复的问题"]
        for e in report["errors"]:
            md_lines.append(f"- {e}")

    if report.get("warnings"):
        md_lines += ["", "### 注意事项"]
        for w in report["warnings"]:
            md_lines.append(f"- {w}")

    if report.get("sample_issues"):
        md_lines += ["", "### 抽样问题（最多10条）"]
        for issue in report["sample_issues"]:
            icon = "❌" if issue["level"] == "error" else "⚠️"
            md_lines.append(f"- {icon} {issue['target']}：{issue['issue']}")

    if ready:
        overwrite_flag = " --overwrite" if args.overwrite else ""
        md_lines += [
            "",
            "## 下一步",
            f"验证通过，确认无误后运行以下命令将数据写入 constraint-filter：",
            "```bash",
            f"python3 main.py store {data_path}{overwrite_flag}",
            "```",
        ]

    md_text = "\n".join(md_lines)
    md_filename = data_path.with_suffix(".md").name
    md_path = _OUTPUTS_DIR / md_filename
    md_path.write_text(md_text, encoding="utf-8")

    # 同时打印到终端
    print(md_text)
    print(f"\nMarkdown 摘要已保存到：{md_path}")

    return 0 if ready else 1


def cmd_store(args: argparse.Namespace) -> int:
    try:
        nf = Path(args.normalized_file)
        if not nf.exists():
            print(f"❌ 文件不存在：{nf}")
            return 2
        normalized = _load_intermediate(nf)

        target_dir = Path(args.target_dir) if args.target_dir else None
        result = store(normalized, target_dir=target_dir, overwrite=args.overwrite)
        print(result["message"])
        return 0
    except DataPipelineError as exc:
        _json_print(exc.to_dict())
        return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="数据准备: 招生计划等数据文件 → constraint-filter JSON"
    )
    sub = parser.add_subparsers(dest="cmd")

    # detect
    p_detect = sub.add_parser("detect", help="识别文件类型和数据类型")
    p_detect.add_argument("file", help="文件路径")

    # extract
    p_extract = sub.add_parser("extract", help="提取文件原始数据")
    p_extract.add_argument("file", help="文件路径")
    p_extract.add_argument("--output", "-o", help="输出 JSON 路径（不指定则打印到 stdout）")

    # run
    p_run = sub.add_parser("run", help="一站式：extract + normalize + validate")
    p_run.add_argument("file", help="文件路径")
    p_run.add_argument("--province", help="手动指定省份（如：河南）")
    p_run.add_argument("--year", type=int, help="手动指定招生年份（如：2026）")
    p_run.add_argument("--output", "-o", default=None,
                       help="归一化结果输出路径（默认自动保存到项目根目录 outputs/）")
    p_run.add_argument("--overwrite", action="store_true",
                       help="存储时覆盖已有文件（在随后的 store 命令中生效）")

    # store
    p_store = sub.add_parser("store", help="将归一化 JSON 写入 constraint-filter 数据目录")
    p_store.add_argument("normalized_file", help="归一化后的 JSON 文件路径")
    p_store.add_argument("--target-dir", help="覆盖默认目标目录")
    p_store.add_argument("--overwrite", action="store_true", help="覆盖已有文件")

    args = parser.parse_args(argv)

    if args.cmd == "detect":
        return cmd_detect(args)
    if args.cmd == "extract":
        return cmd_extract(args)
    if args.cmd == "run":
        return cmd_run(args)
    if args.cmd == "store":
        return cmd_store(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
