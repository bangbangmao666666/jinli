# constraint-filter

硬约束过滤模块 —— 高考志愿填报流水线的第一道关卡。用刚性条件将全国院校+专业压缩为**该考生能合法填报**的基本盘。

## 目录结构

```
constraint-filter/
├── SKILL.md                         # Skill 入口（供 Claude 调用）
├── README.md                        # 本文件
├── main.py                          # CLI 入口
├── constraint_filter/               # Python 包
│   ├── __init__.py                  # 导出 run()
│   ├── errors.py                    # FilterError + 子类
│   ├── data_loader.py               # 读取 JSON 数据（版本校验）
│   ├── input_validator.py           # 输入字段/选科组合校验
│   ├── subject_parser.py            # 选科要求字符串 → 结构化表达式
│   ├── physical_filter.py           # 第四层体检限制
│   ├── rank_tier.py                 # rank_ratio 计算与冲稳保分档
│   └── pipeline.py                  # 主流水线
├── schemas/
│   ├── input_schema.json
│   └── output_schema.json
├── data/
│   ├── province_exam_mode.json
│   ├── subject_requirement_keywords.json
│   ├── physical_restrictions.json
│   ├── error_codes.md
│   └── admission_plans/
│       └── henan_2026.json          # MVP 样板数据
└── tests/
    ├── test_input_validator.py
    ├── test_subject_parser.py
    ├── test_physical_filter.py
    ├── test_rank_tier.py
    └── test_pipeline.py
```

## 运行

### CLI
```bash
cd <skill 目录>
python main.py tests/fixtures/henan_physics_medium.json --pretty
```

### 模块调用
```python
from constraint_filter import run
result = run(applicant_dict)
```

### 测试
```bash
python -m unittest discover -s tests -v
```

需要 Python 3.9+。仅依赖标准库。

## 已知限制（MVP）

1. 目前仅样板数据：`data/admission_plans/henan_2026.json`（河南 2026 年，少量院校）。其它省份需要后续补数据。
2. 不接入任何外部 API；所有数据走本地 JSON 文件。
3. 传统文理省份的"文史/理工/兼收"识别基于 `group_name` 字符串，真实上线前需要在招生计划文件中增加结构化字段。
4. 单科成绩限制（如"数学≥120 才能报某专业"）尚未实现，留作 P1。
5. 定向、专项、民族班、艺术/体育类等特殊批次未实现，留作后续迭代。

## 维护须知

- **数据版本**：每份 JSON 必须带有 `valid_for_year`；考生填写的 `exam_year` 与之不符时 skill 会抛 `DATA_VERSION_MISMATCH`。这是故意的——宁可停下也不用旧数据糊弄新年份。
- **添加新省份**：
  1. 在 `data/admission_plans/` 下新增 `<省拼音>_<年份>.json`
  2. 如映射缺失，在 `data_loader.PROVINCE_FILE_SLUG` 中补充
  3. 检查 `data/province_exam_mode.json` 是否已涵盖该省
- **扩展体检规则**：仅修改 `data/physical_restrictions.json`，不要把规则硬编码进 Python。每条规则必须带 `authority`（来源引用）。
- **扩展选科解析**：仅修改 `data/subject_requirement_keywords.json`。若招生计划出现无法归类的写法——**报错而非猜测**。

## 错误码

见 `data/error_codes.md`。
