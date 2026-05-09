"""简单的测试脚本"""
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from strategy_planner import run


def create_test_input() -> dict:
    """创建测试输入"""
    return {
        "applicant_profile": {
            "province": "河南",
            "total_score": 548,
            "provincial_rank": 45000,
            "subject_category": "物理类",
            "selected_subjects": ["物理", "化学", "生物"],
            "gender": "男",
        },
        "passed_majors": [
            {"major_name": "计算机科学与技术", "traffic_light": "绿灯"},
            {"major_name": "软件工程", "traffic_light": "绿灯"},
            {"major_name": "电子信息工程", "traffic_light": "绿灯"},
            {"major_name": "电气工程及其自动化", "traffic_light": "绿灯"},
            {"major_name": "自动化", "traffic_light": "绿灯"},
            {"major_name": "数据科学与大数据技术", "traffic_light": "绿灯"},
            {"major_name": "材料科学与工程", "traffic_light": "红灯"},
        ],
        "recommended_schools": [
            # 冲志愿 (4个)
            {
                "school_name": "郑州大学",
                "major_name": "计算机科学与技术",
                "positioning": "冲",
                "admission_probability": "约30%",
                "admission_probability_num": 0.3,
                "cleanliness": "🟢 干净",
            },
            {
                "school_name": "郑州大学",
                "major_name": "软件工程",
                "positioning": "冲",
                "admission_probability": "约35%",
                "admission_probability_num": 0.35,
                "cleanliness": "🟢 干净",
            },
            {
                "school_name": "河南大学",
                "major_name": "计算机科学与技术",
                "positioning": "冲",
                "admission_probability": "约40%",
                "admission_probability_num": 0.4,
                "cleanliness": "🟢 干净",
            },
            {
                "school_name": "河南大学",
                "major_name": "软件工程",
                "positioning": "冲",
                "admission_probability": "约42%",
                "admission_probability_num": 0.42,
                "cleanliness": "🟢 干净",
            },
            # 稳志愿 (22个，这里简化为6个)
            {
                "school_name": "河南工业大学",
                "major_name": "计算机科学与技术",
                "positioning": "稳",
                "admission_probability": "约70%",
                "admission_probability_num": 0.7,
                "cleanliness": "🟢 干净",
            },
            {
                "school_name": "河南工业大学",
                "major_name": "电子信息工程",
                "positioning": "稳",
                "admission_probability": "约72%",
                "admission_probability_num": 0.72,
                "cleanliness": "🟢 干净",
            },
            {
                "school_name": "河南科技大学",
                "major_name": "计算机科学与技术",
                "positioning": "稳",
                "admission_probability": "约75%",
                "admission_probability_num": 0.75,
                "cleanliness": "🟢 干净",
            },
            {
                "school_name": "河南科技大学",
                "major_name": "软件工程",
                "positioning": "稳",
                "admission_probability": "约73%",
                "admission_probability_num": 0.73,
                "cleanliness": "🟢 干净",
            },
            {
                "school_name": "中原工学院",
                "major_name": "计算机科学与技术",
                "positioning": "稳",
                "admission_probability": "约78%",
                "admission_probability_num": 0.78,
                "cleanliness": "🟢 干净",
            },
            {
                "school_name": "中原工学院",
                "major_name": "电子信息工程",
                "positioning": "稳",
                "admission_probability": "约80%",
                "admission_probability_num": 0.8,
                "cleanliness": "🟢 干净",
            },
            # 保志愿 (19个，这里简化为5个)
            {
                "school_name": "河南理工大学",
                "major_name": "计算机科学与技术",
                "positioning": "保",
                "admission_probability": "约90%",
                "admission_probability_num": 0.9,
                "cleanliness": "🟢 干净",
            },
            {
                "school_name": "河南理工大学",
                "major_name": "电子信息工程",
                "positioning": "保",
                "admission_probability": "约92%",
                "admission_probability_num": 0.92,
                "cleanliness": "🟢 干净",
            },
            {
                "school_name": "郑州轻工业大学",
                "major_name": "计算机科学与技术",
                "positioning": "保",
                "admission_probability": "约93%",
                "admission_probability_num": 0.93,
                "cleanliness": "🟢 干净",
            },
            {
                "school_name": "郑州轻工业大学",
                "major_name": "软件工程",
                "positioning": "保",
                "admission_probability": "约94%",
                "admission_probability_num": 0.94,
                "cleanliness": "🟢 干净",
            },
            {
                "school_name": "河南农业大学",
                "major_name": "计算机科学与技术",
                "positioning": "保",
                "admission_probability": "约95%",
                "admission_probability_num": 0.95,
                "cleanliness": "🟢 干净",
            },
        ],
        "eligible_pool": [
            {
                "school_name": "河南工业大学",
                "major_name": "电子信息工程",
                "admission_probability_num": 0.95,
                "admission_probability": "约95%",
            },
            {
                "school_name": "河南科技大学",
                "major_name": "计算机科学与技术",
                "admission_probability_num": 0.9,
                "admission_probability": "约90%",
            },
            {
                "school_name": "河南理工大学",
                "major_name": "计算机科学与技术",
                "admission_probability_num": 0.9,
                "admission_probability": "约90%",
            },
            {
                "school_name": "郑州轻工业大学",
                "major_name": "计算机科学与技术",
                "admission_probability_num": 0.93,
                "admission_probability": "约93%",
            },
            {
                "school_name": "河南农业大学",
                "major_name": "计算机科学与技术",
                "admission_probability_num": 0.95,
                "admission_probability": "约95%",
            },
        ],
        "risk_preference": "保守型",
        "accept_adjustment": "仅接受干净组调剂",
    }


def test_simple():
    """简单测试"""
    data = create_test_input()

    try:
        result = run(data)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return

    print("="*80)
    print("测试结果:")
    print("="*80)
    print(f"状态: {result.get('status')}")
    
    if result.get('status') == 'success':
        # 展示策略摘要表格
        print("\n" + "="*80)
        print("二、各段志愿配置细则")
        print("="*80)
        summary_table = result.get('strategy_summary_table', [])
        if summary_table:
            print(f" {'志愿段':<10}{'数量占比':<10}{'对应志愿数':<15}{'录取概率区间':<15}{'核心报考方向':<30}{'参考院校举例':<30}")
            print(f" {chr(0x2500) * 110}")
            for item in summary_table:
                # 简化参考院校举例以便显示
                ref_schools = item.get('参考院校举例', '')[:30] + ('...' if len(item.get('参考院校举例', ''))>30 else '')
                direction = item.get('核心报考方向', '')[:30] + ('...' if len(item.get('核心报考方向', ''))>30 else '')
                print(f" {item.get('志愿段', ''):<10}{item.get('数量占比', ''):<10}{item.get('对应志愿数', ''):<15}{item.get('录取概率区间', ''):<15}{direction:<30}{ref_schools:<30}")
        
        print("\n" + "="*80)
        print("三、各段志愿参考方向")
        print("="*80)
        
        volunteer_segments = result.get('volunteer_segments', {})
        
        # 展示冲段
        sprint_info = volunteer_segments.get("冲段", {})
        if sprint_info:
            print("\n📌 1. 冲段（{}个志愿，录取概率{}）".format(sprint_info.get("志愿数量", 0), sprint_info.get("录取概率范围", "未知")))
            print(f"   方向：{sprint_info.get('方向说明', '')}")
            print(f"   参考院校：{'、'.join(sprint_info.get('参考院校', []))}")
            print("\n   具体志愿：")
            print(f"   {'序号':<5}{'学校+专业':<40}{'志愿类型':<8}{'录取概率':<12}{'专业组干净度':<15}")
            print(f"   {chr(0x2500) * 85}")
            for vol in sprint_info.get("志愿表格", []):
                print(f"   {vol['序号']:<5}{vol['学校+专业']:<40}{vol['志愿类型']:<8}{vol['录取概率']:<12}{vol['专业组干净度']:<15}")
        
        # 展示稳段
        stable_info = volunteer_segments.get("稳段", {})
        if stable_info:
            print("\n📌 2. 稳段（{}个志愿，录取概率{}）".format(stable_info.get("志愿数量", 0), stable_info.get("录取概率范围", "未知")))
            print(f"   方向：{stable_info.get('方向说明', '')}")
            print(f"   参考院校：{'、'.join(stable_info.get('参考院校', []))}")
            print("\n   具体志愿：")
            print(f"   {'序号':<5}{'学校+专业':<40}{'志愿类型':<8}{'录取概率':<12}{'专业组干净度':<15}")
            print(f"   {chr(0x2500) * 85}")
            for vol in stable_info.get("志愿表格", []):
                print(f"   {vol['序号']:<5}{vol['学校+专业']:<40}{vol['志愿类型']:<8}{vol['录取概率']:<12}{vol['专业组干净度']:<15}")
        
        # 展示保段
        guarantee_info = volunteer_segments.get("保段", {})
        if guarantee_info:
            print("\n📌 3. 保段（{}个志愿，录取概率{}）".format(guarantee_info.get("志愿数量", 0), guarantee_info.get("录取概率范围", "未知")))
            print(f"   方向：{guarantee_info.get('方向说明', '')}")
            print(f"   参考院校：{'、'.join(guarantee_info.get('参考院校', []))}")
            print("\n   具体志愿：")
            print(f"   {'序号':<5}{'学校+专业':<40}{'志愿类型':<8}{'录取概率':<12}{'专业组干净度':<15}")
            print(f"   {chr(0x2500) * 85}")
            for vol in guarantee_info.get("志愿表格", []):
                print(f"   {vol['序号']:<5}{vol['学校+专业']:<40}{vol['志愿类型']:<8}{vol['录取概率']:<12}{vol['专业组干净度']:<15}")
            
            # 展示绝对兜底
            absolute_guarantee = guarantee_info.get("绝对兜底志愿", [])
            if absolute_guarantee:
                print("\n   🔒 绝对兜底志愿（录取概率95%以上，确保不滑档）：")
                print(f"   {'序号':<5}{'学校+专业':<40}{'志愿类型':<8}{'录取概率':<12}{'专业组干净度':<15}")
                print(f"   {chr(0x2500) * 85}")
                for vol in absolute_guarantee:
                    print(f"   {vol['序号']:<5}{vol['学校+专业']:<40}{vol['志愿类型']:<8}{vol['录取概率']:<12}{vol['专业组干净度']:<15}")
        
        print(f"\n策略配置: {result.get('strategy_config')}")
        
        print("\n" + "="*80)
        print("📢 重要提示")
        print("="*80)
        for warning in result.get('warnings', []):
            print(warning)
    else:
        print(f"\n错误码: {result.get('error_code')}")
        print(f"错误信息: {result.get('error_message')}")
        print(f"用户操作建议: {result.get('user_action_required')}")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    test_simple()
