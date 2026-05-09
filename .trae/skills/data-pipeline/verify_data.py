#!/usr/bin/env python3
"""验证山东2024数据是否能被 constraint-filter 正确加载。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "constraint-filter"))

from constraint_filter import data_loader

def main():
    province = "山东"
    year = 2024

    print("=== 验证数据加载 ===")
    print(f"省份：{province}，年份：{year}")
    print()

    # 1. 招生计划
    try:
        plan = data_loader.load_admission_plan(province, year)
        schools = plan.get("schools", [])
        print(f"✅ 招生计划：加载成功，共 {len(schools)} 所院校")
        if schools:
            first = schools[0]
            print(f"   示例：{first.get('school_name')} ({first.get('school_code')})")
            groups = first.get("major_groups", [])
            if groups:
                print(f"   首个院校专业组数：{len(groups)}")
                majors = groups[0].get("majors", [])
                if majors:
                    print(f"   首个专业组专业数：{len(majors)}")
    except Exception as exc:
        print(f"❌ 招生计划：加载失败 — {exc}")

    print()

    # 2. 历史录取位次
    try:
        ranks = data_loader.load_historical_ranks(province, year)
        print(f"✅ 历史录取位次：加载成功，共 {len(ranks)} 条 (院校,专业) 组合")
        if ranks:
            sample_key = next(iter(ranks))
            print(f"   示例：{sample_key[0]} · {sample_key[1]} — {ranks[sample_key][:2]}")
    except Exception as exc:
        print(f"❌ 历史录取位次：加载失败 — {exc}")

    print()

    # 3. 一分一段表
    try:
        table = data_loader.load_score_rank_table(province, year)
        print(f"✅ 一分一段表：加载成功，共 {len(table)} 个分数段")
        if table:
            sample_scores = list(table.keys())[:3]
            for s in sample_scores:
                print(f"   {s}分：合计累计 {table[s].get('total', {}).get('cumulative', 'N/A')}")
    except Exception as exc:
        print(f"❌ 一分一段表：加载失败 — {exc}")

    print()
    print("=== 验证完成 ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
