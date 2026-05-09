"""测试辅助：加入 skill 根目录到 sys.path，提供典型 applicant fixture。"""
from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def henan_physics_applicant(**overrides):
    base = {
        "province": "河南",
        "total_score": 580,
        "provincial_rank": 45000,
        "subject_category": "物理类",
        "selected_subjects": ["物理", "化学", "生物"],
        "gender": "男",
        "physical_exam": {
            "color_blindness": "正常",
            "vision_left": 4.8,
            "vision_right": 4.8,
            "height_cm": 175,
            "weight_kg": 65,
            "hearing_normal": True,
            "other_conditions": [],
        },
        "political_review_clean": True,
        "exam_year": 2026,
    }
    out = deepcopy(base)
    out.update(overrides)
    return out
