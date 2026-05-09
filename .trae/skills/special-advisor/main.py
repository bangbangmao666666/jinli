"""special-advisor CLI 入口。

用法：
    python main.py <input.json>                # 读取上游输出 JSON，打印结果
    python main.py -                           # 从 stdin 读取 JSON
    python main.py <input.json> --pretty       # 按中文缩进美化输出

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

from special_advisor import run  # noqa: E402  (import after sys.path edit)


def _load_input(src: str) -> dict:
    if src == "-":
        return json.loads(sys.stdin.read())
    path = Path(src)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="special-advisor: 特殊适配与终审模块 (特殊适配) 的命令行入口"
    )
    parser.add_argument("input", help="上游输出 JSON 文件路径，使用 - 表示从 stdin 读取")
    parser.add_argument("--pretty", action="store_true", help="按中文缩进美化输出")
    parser.add_argument(
        "--data-dir",
        help="覆盖默认的数据目录（默认 ./data）",
        default=None,
    )
    args = parser.parse_args(argv)

    input_data = _load_input(args.input)
    data_dir = Path(args.data_dir) if args.data_dir else None
    result = run(input_data, data_dir=data_dir)

    indent = 2 if args.pretty else None
    print(json.dumps(result, ensure_ascii=False, indent=indent))
    return 0 if result.get("status") == "success" else 2


if __name__ == "__main__":
    raise SystemExit(main())
