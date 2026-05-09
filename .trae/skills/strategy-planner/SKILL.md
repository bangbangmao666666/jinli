---
name: 4填报策略
description: 填报策略规划，生成安全风险明确的方案。当用户提及志愿怎么排顺序、冲稳保怎么分配、帮我生成志愿方案、调剂怎么选、志愿顺序、志愿方案、填报策略、兜底志愿、服从调剂、滑档预案等关键词时，必须触发本 skill。本 skill 为填报策略模块流水线核心模块，基于考生省份的招生规则，对「院校匹配」模块输出的院校专业清单进行专业组干净度检查、冲稳保比例分配、志愿顺序排列，生成安全、可执行、风险明确的完整志愿填报方案。
---



# strategy-planner — 填报策略模块：填报策略Skill

## 核心使命

> 基于考生所在省份的招生规则，对 院校匹配模块 输出的院校专业清单进行专业组干净度核查、冲稳保比例分配、志愿顺序排列，
> 生成安全、可执行、风险明确的完整志愿填报方案；宁可保守也不冒进，确保普通家庭考生不滑档、不被调剂到天坑专业。

详尽的设计背景、哲学与错误处理规约见：`../../../prds/strategy-planner-SKILL需求规格说明书.txt`。

## 何时触发

任一条件满足即应调用：

- 流水线中 院校匹配模块 完成院校匹配，输出推荐院校清单；
- 用户输入 "志愿怎么排顺序 / 冲稳保怎么分配 / 帮我生成志愿方案 / 调剂怎么选 / 志愿顺序 / 填报策略 / 兜底志愿" 等意图；
- 用户要求对已有志愿方案进行安全性检查。

不触发：评估专业好坏（专业评估模块）、推荐院校（院校匹配模块）、特殊群体适配（特殊适配与终审模块）。

## 一、中间数据获取规则（最高优先级）

**所有中间数据必须从 `结果/` 目录读取，禁止从项目根目录或其他位置读取同类文件。**

| 数据类型 | 读取路径 |
|---------|---------|
| 考生画像 | `结果/1初步筛选_考生画像_<省份>.md` |
| 硬约束过滤结果 | `结果/1初步筛选_硬约束过滤结果_<省份>.md` |
| 专业评估报告 | `结果/2选专业_专业评估报告_<省份>.md` |
| 院校匹配结果 | `结果/3选学校_院校匹配结果_{省份}.md` |

**操作顺序**：依次读取上游 模块 的输出文件。如 `结果/` 目录下无对应文件，停止并提示用户按顺序运行。

## 使用方法

### 方式一：Python 模块调用（推荐）

```python
from pathlib import Path
import sys

sys.path.insert(0, str(Path("<此 skill 绝对路径>")))
from strategy_planner import run

# 流水线模式
result = run({
    "applicant_profile": {...},  # 硬约束过滤模块 输出的考生完整信息
    "passed_majors": [...],      # 专业评估模块 输出的绿灯/黄灯专业清单
    "recommended_schools": [...], # 院校匹配模块 输出的推荐院校专业清单
    "eligible_pool": [...],       # 硬约束过滤模块 输出的完整可填报基本盘
    "risk_preference": "保守型",  # 可选：保守型/适中型/激进型
    "accept_adjustment": "仅接受干净组调剂",  # 可选：是/否/仅接受干净组调剂
    "target_sprint_schools": [],  # 可选：明确的冲刺目标院校列表
})
```

### 方式二：CLI

```bash
# 从文件输入
python main.py input.json --pretty

# 从 stdin
cat input.json | python main.py -
```

退出码：`0` 表示 success，`2` 表示任何 error 响应。

需要 **Python 3.9+**，**仅依赖标准库，无需安装额外包**。

## 输入结构

### 流水线模式必填字段

| 字段 | 来源 | 说明 |
|------|------|------|
| applicant_profile | 硬约束过滤模块 | 考生完整信息（province, total_score, provincial_rank 必填） |
| passed_majors | 专业评估模块 | 评估通过的绿灯/黄灯专业清单，含红灯专业列表 |
| recommended_schools | 院校匹配模块 | 推荐院校专业清单，含冲/稳/保定位、录取概率 |
| eligible_pool | 硬约束过滤模块 | 完整的可填报基本盘，用于兜底志愿不足时补充 |

### 可选补充字段

| 字段 | 说明 | 缺失时行为 |
|------|------|-----------|
| risk_preference | 风险偏好：保守型/适中型/激进型 | 默认保守型 |
| accept_adjustment | 调剂意愿：是/否/仅接受干净组调剂 | 默认仅接受干净组调剂 |
| target_sprint_schools | 明确的冲刺目标院校列表 | 无特殊冲校目标 |
| special_requirements | 其他特殊要求 | 无特殊要求 |

## 输出结构

两种状态二选一：

- `status=success`：含 basic_info、strategy_config、volunteer_list、adjustment_guide、slide_prevention_plan、final_checklist、warnings 等字段。
- `status=error`：含 error_code、error_message、user_action_required、error_detail。

**结果写入**：每次运行成功后，必须将最终志愿方案保存为：`结果/4填报策略_填报策略方案_<省份>.md`。

**凡异常一律走 error 分支，绝不降级为 success。**

### 核心输出字段说明

| 字段 | 说明 |
|------|------|
| basic_info | 考生信息摘要、该省填报规则、策略基调、风险提示 |
| strategy_config | 风险偏好、冲稳保比例与数量、调剂策略 |
| volunteer_list | 按冲→稳→保顺序排列的志愿清单，每个志愿含干净度、录取概率、风险提示 |
| adjustment_guide | 针对每个专业组的调剂建议 |
| slide_prevention_plan | 滑档后的应急处理方案 |
| final_checklist | 填报前的最终确认清单 |

## 四条不可逾越的底线

1. **安全第一**：所有策略必须优先确保不滑档、不被调剂到天坑专业，其次才是最大化分数利用率
2. **风险透明**：所有可能的风险必须明确、醒目地告知用户，包括风险发生的概率和后果
3. **规则可解释**：为什么这么排顺序、为什么这个比例，都必须有明确的规则依据
4. **保守优先**：当有多种策略可选时，优先选择更保守、更安全的方案

## 错误码

| 错误码 | 含义 |
|--------|------|
| INPUT_UPSTREAM_EMPTY | 上游输入为空（无考生信息或无推荐院校） |
| DATA_RULE_NOT_FOUND | 该省填报规则未收录 |
| INPUT_VOLUNTEER_INSUFFICIENT | 可选院校数量不足 |
| DATA_PROFESSIONAL_GROUP_MISSING | 部分专业组信息缺失 |
| DATA_ADMISSION_PROBABILITY_MISSING | 部分专业录取概率无法计算 |
| INPUT_MISSING_REQUIRED_FIELD | 缺失必填字段 |
| INPUT_INVALID_FIELD_VALUE | 字段值不合法 |

## 代码结构

```
strategy-planner/
├── main.py                          # CLI 入口
├── strategy_planner/
│   ├── __init__.py                  # 主入口（run 函数）
│   ├── errors.py                    # 错误码定义
│   ├── input_validator.py           # 输入校验
│   ├── data_loader.py               # 数据加载（填报规则、招生计划、录取数据）
│   ├── rule_matcher.py              # 填报规则匹配
│   ├── ratio_allocator.py           # 冲稳保比例分配
│   ├── cleanliness_checker.py       # 专业组干净度检查
│   ├── hidden_threshold_checker.py  # 隐藏门槛核查
│   ├── volunteer_sorter.py          # 志愿顺序排列
│   ├── adjustment_guide.py          # 调剂策略生成
│   ├── slide_prevention.py          # 滑档预案生成
│   ├── output_formatter.py          # 输出格式化
│   └── pipeline.py                  # 主流水线
├── tests/
│   ├── test_simple.py               # 简单功能测试
│   └── test_pipeline.json           # 流水线模式测试数据
└── SKILL.md                         # 本文件
```

## 重要使用说明

1. **数据来源优先级**：优先使用项目本地招生规则数据库、录取数据，仅在数据缺失时标注并提示用户核实
2. **保守策略为默认**：普通家庭考生默认使用保守型策略，激进策略必须明确提示风险
3. **专业组干净度必须核查**：每个专业组必须检查是否包含红灯专业，不干净的专业组必须明确标注风险
4. **必须有兜底志愿**：保底志愿的核心在于“录取概率足够高且专业可接受”，无需刻意追求过高的数量。保段+补充志愿合计达到 45 个左右即可，重点是依据 硬约束过滤模块/3 的结果筛选出高质量的选项。注意：`rank_ratio` 越低（如 0.90, 0.85）意味着考生的位次优势越大，录取概率越高，完全符合保底安全阈值；同时，对于 211 等具有特定优势的高校，即使地理位置偏远（如石河子大学），将其保留在稳段或保段前列也是合理的策略。
5. **禁止绝对化承诺**：不得出现「肯定能上」「保证录取」等表述，所有录取概率必须明确给出具体数值
