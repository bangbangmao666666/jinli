# error_codes.md

> 硬约束过滤模块 (constraint-filter) 统一错误码字典。所有错误必须使用此处定义的 `error_code`，不得自造。

每条错误包含：**含义 / 触发条件 / 用户行动指引 / 开发者排查建议**。

---

## 输入类（INPUT_*）

### INPUT_MISSING_REQUIRED_FIELD
- **含义**：必填字段缺失。
- **触发条件**：`province / total_score / provincial_rank / subject_category / selected_subjects / gender` 任一缺失；或新高考省份 `selected_subjects` 为空。
- **用户行动指引**：请补全列出的所有缺失字段后重新运行。
- **开发者排查**：检查调用方是否按 `schemas/input_schema.json` 构造输入；注意 `provincial_rank` 和 `total_score` 不能相互代替。

### INPUT_INVALID_FIELD_VALUE
- **含义**：字段值不合法（类型错、超出取值范围）。
- **触发条件**：分数为负 / 位次为负或超出该省考生总数 / 省份不在 31 省列表内 / gender 非"男"或"女"。
- **用户行动指引**：按错误消息提示核对字段，重新运行。
- **开发者排查**：先查输入校验函数 `_validate_required_value_ranges`。

### INPUT_INVALID_SUBJECT_COMBINATION
- **含义**：选科组合不合法。
- **触发条件**：3+1+2 省份同时包含"物理"和"历史"；3+1+2 省份首选科目缺失；3+3 省份选考科目数不为 3；含有不在 valid_subjects 列表中的科目。
- **用户行动指引**：核对考生实际选科并改正。
- **开发者排查**：见 `_validate_subject_combination`。

### INPUT_SCORE_RANK_MISMATCH
- **含义**：分数与位次明显矛盾（警告级，不中断）。
- **触发条件**：未实现严格校验时通过 warnings 提示；启用严格模式时可升级为 error。
- **用户行动指引**：核对一分一段表后重新填写位次。
- **开发者排查**：此为保留位，当前版本仅在 warnings 里提示。

---

## 数据类（DATA_*）

### DATA_SOURCE_UNAVAILABLE
- **含义**：数据源（招生计划文件等 P0 数据）无法访问。
- **触发条件**：`data/admission_plans/{province}_{year}.json` 不存在或读取失败。
- **用户行动指引**：请稍后重试；如持续失败，请手动提供该省招生计划文件（PDF/Excel），联系维护者导入。
- **开发者排查**：检查 `data/admission_plans/` 目录；确认文件命名符合 `{province_pinyin_or_cn}_{year}.json`；检查文件编码/JSON 合法性。

### DATA_VERSION_MISMATCH
- **含义**：数据版本与考生高考年份不匹配。
- **触发条件**：招生计划文件 `valid_for_year != applicant.exam_year`。
- **用户行动指引**：禁止继续运行。请等待维护者更新目标年份的数据文件。
- **开发者排查**：更新 `data/admission_plans/` 下对应省份文件的 `valid_for_year`，并同步新的招生计划内容。

### DATA_PARSE_FAILED
- **含义**：数据文件格式错误无法解析。
- **触发条件**：JSON 语法错误 / 关键字段缺失 / 类型不符。
- **用户行动指引**：请联系维护者修复数据文件。
- **开发者排查**：运行 `python -m json.tool data/admission_plans/xxx.json` 定位语法错误。

### DATA_INTEGRITY_VIOLATED
- **含义**：数据内部不一致。
- **触发条件**：某专业缺 major_code / major_group 缺 subject_requirement_raw 等。
- **用户行动指引**：请联系维护者。
- **开发者排查**：检查该条数据记录；补齐字段后重试。

---

## 运行时类（RUNTIME_*）

### RUNTIME_SUBJECT_REQUIREMENT_PARSE_FAILED
- **含义**：选科要求字符串无法解析为逻辑表达式。
- **触发条件**：原始字符串同时包含 AND 和 OR 分隔符无法判断优先级；包含未知关键字（如 "or"、"/" 等被禁用的写法）；包含非合法科目。
- **用户行动指引**：将原始字符串和所在专业一起反馈给维护者修订数据。
- **开发者排查**：查看 error_detail.failed_items，必要时在 `data/subject_requirement_keywords.json` 增补规则，而非改代码硬编码。

### RUNTIME_PHYSICAL_RULE_MAPPING_MISSING
- **含义**：体检映射表未覆盖目标专业。
- **触发条件**：专业的某项体检限制（如 physical_requirement_notes 提到色盲但映射表未登记）。
- **级别**：降级为 warnings，标记 `physical_check: not_verified`，**不中断**运行。
- **用户行动指引**：请自行核对该专业的体检要求。
- **开发者排查**：向 `data/physical_restrictions.json` 补充规则。

### RUNTIME_UNEXPECTED_EXCEPTION
- **含义**：兜底异常。
- **触发条件**：任何未被上面分类捕获的异常。
- **用户行动指引**：请将错误报告反馈给维护者。
- **开发者排查**：`error_detail.traceback` 含完整栈；优先补充专门的错误码而非依赖兜底。

---

## 外部类（EXTERNAL_*）

> 当前 MVP 不接入实时 API，以下错误码为接入后生效的占位定义。

### EXTERNAL_API_TIMEOUT
- **含义**：外部接口超时。

### EXTERNAL_API_RATE_LIMIT
- **含义**：外部接口限流。

### EXTERNAL_API_AUTH_FAILED
- **含义**：认证失败。
