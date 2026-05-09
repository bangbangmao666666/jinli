
"""数据加载模块。

支持两种数据源：
1. 本地院校数据库 (school-database.md)
2. 复用constraint-filter的数据加载
"""
from pathlib import Path

from .errors import DataSourceUnavailableError

# 默认数据目录指向references目录
DEFAULT_DATA_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "references"
)

# constraint-filter的数据目录
CONSTRAINT_FILTER_DATA_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "constraint-filter" / "data"
)


def _read_text(path, kind):
    """读取文本文件"""
    if not path.exists():
        raise DataSourceUnavailableError(
            "无法找到%s数据文件：%s" % (kind, path.name),
            user_action="请确认数据文件存在。",
            detail={"missing_path": str(path), "kind": kind}
        )
    try:
        with path.open("r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        raise DataSourceUnavailableError(
            "读取%s文件失败：%s" % (kind, e),
            user_action="请确认文件权限正常。",
            detail={"path": str(path)}
        ) from e


def load_school_database(data_dir=None):
    """加载院校数据库。

    解析school-database.md，提取院校评价信息。
    返回结构化的院校数据库字典。
    """
    data_dir = data_dir or DEFAULT_DATA_DIR
    path = data_dir / "school-database.md"

    content = _read_text(path, kind="院校数据库")

    school_db = {}
    school_db["schools"] = {}
    school_db["industry_schools"] = {}
    school_db["treasure_schools"] = set()
    school_db["value_schools"] = set()

    # 解析顶尖与985层次
    current_section = ""
    lines = content.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if line.startswith("###"):
            current_section = line
        elif line.startswith("|") and not line.startswith("| 院校"):
            # 表格行，解析
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 2:
                school_name = parts[0]

                if "宝藏校" in current_section:
                    school_db["treasure_schools"].add(school_name)
                elif "性价比" in current_section:
                    school_db["value_schools"].add(school_name)
                elif "行业特色" in current_section:
                    industry = parts[1] if len(parts) > 1 else ""
                    school_db["industry_schools"].setdefault(industry, []).append(school_name)
                    school_db["schools"][school_name] = {
                        "industry": industry,
                        "tags": parts[2] if len(parts) > 2 else "",
                        "description": parts[3] if len(parts) > 3 else "",
                        "is_industry_school": True
                    }
                elif "顶尖" in current_section:
                    school_db["schools"][school_name] = {
                        "tags": parts[1] if len(parts) > 1 else "",
                        "description": parts[2] if len(parts) > 2 else "",
                        "is_top_school": True
                    }
        i += 1

    # 按行业分类的特殊处理
    school_db["industry_schools"]["电力"] = ["东北电力大学", "华北电力大学", "三峡大学"]
    school_db["industry_schools"]["石油"] = ["东北石油大学", "西南石油大学"]
    school_db["industry_schools"]["航空航天"] = ["北京航空航天大学", "南京航空航天大学"]

    return school_db


def load_major_database(data_dir=None):
    """加载专业数据库，用于辅助评估"""
    data_dir = data_dir or DEFAULT_DATA_DIR
    path = data_dir / "major-database.md"

    try:
        content = _read_text(path, kind="专业数据库")
        return {"content": content}
    except DataSourceUnavailableError:
        return {"content": ""}


def load_historical_ranks(province, year, data_dir=None):
    """复用constraint-filter加载历史录取位次"""
    import sys

    # 临时添加constraint-filter到path
    constraint_filter_path = Path(__file__).resolve().parent.parent.parent.parent / "constraint-filter"
    if str(constraint_filter_path) not in sys.path:
        sys.path.insert(0, str(constraint_filter_path))

    try:
        from constraint_filter import data_loader as cf_data_loader
        return cf_data_loader.load_historical_ranks(province, year, data_dir or CONSTRAINT_FILTER_DATA_DIR)
    except ImportError:
        return {}


def load_admission_plan(province, year, data_dir=None):
    """复用constraint-filter加载招生计划"""
    import sys

    constraint_filter_path = Path(__file__).resolve().parent.parent.parent.parent / "constraint-filter"
    if str(constraint_filter_path) not in sys.path:
        sys.path.insert(0, str(constraint_filter_path))

    try:
        from constraint_filter import data_loader as cf_data_loader
        return cf_data_loader.load_admission_plan(province, year, data_dir or CONSTRAINT_FILTER_DATA_DIR)
    except Exception:
        return {}


def get_industry_school_list(school_db, industry):
    """获取指定行业的院校列表"""
    for key, schools in school_db.get("industry_schools", {}).items():
        if industry in key:
            return schools
    return []


def is_treasure_school(school_db, school_name):
    """判断是否为宝藏校"""
    return school_name in school_db.get("treasure_schools", set())


def is_value_school(school_db, school_name):
    """判断是否为性价比高的院校"""
    return school_name in school_db.get("value_schools", set())


def is_industry_school(school_db, school_name, industry=""):
    """判断是否为行业特色校"""
    if not industry:
        for schools in school_db.get("industry_schools", {}).values():
            if school_name in schools:
                return True
        return False
    return school_name in school_db.get("industry_schools", {}).get(industry, [])

