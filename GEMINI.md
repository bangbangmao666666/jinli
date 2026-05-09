# GEMINI.md

This file provides guidance to Gemini CLI when working with code in this repository.

---

## 这个项目是干什么的

**高考志愿填报智能顾问系统** —— 专为 2026 年夏季高考的**普通家庭考生**提供科学、务实、可执行的志愿填报方案。

服务对象是本科线到 211 线之间、寄希望于用高考改变命运的普通家庭孩子。**高考是他们手里最重要、也最公平的向上通道，科学填报志愿是守护孩子奋斗成果的关键。**

---

## 运行平台：Trae Solo

**本项目运行在 [Trae Solo](https://docs.trae.cn/solo/what-is-trae-solo?_lang=zh) 上。** Trae Solo 是字节跳动推出的 AI 原生工作台，支持 Web 和桌面双端，面向非开发者用户（产品经理、数据分析师、普通学生家长等）提供 AI 对话式任务完成能力。

本项目使用的是 Trae Solo 的 **MTC 模式**（More Than Coding），目标用户是**完全不懂代码的普通家长和考生**，他们通过自然语言对话获得志愿填报建议。

### Trae Solo 的核心机制

Trae Solo 通过以下三类配置文件控制 AI 的行为：

| 配置类型 | 文件位置 | 作用 |
|----------|----------|------|
| **模块 主控规则** | `CLAUDE.md`（项目根目录） | 定义 AI 的整体行为、流水线架构、协作规则 |
| **启动引导规则** | `.trae/rules/BOOTSTRAP.md` | 定义新用户首次进入时的欢迎语和基础信息收集流程 |
| **用户画像规则** | `.trae/rules/USER.md` | 定义服务对象特征，所有 模块 共享此规则 |
| **技能（Skills）** | `.trae/skills/<skill名>/SKILL.md` | 定义可复用的子任务模块，AI 根据 `description` 字段自动判断何时调用 |

### SKILL.md 的触发机制（重要）

Trae Solo 通过读取每个 Skill 的 `SKILL.md` 文件中的 `description` 字段，**自动判断**当前对话是否需要调用该 Skill。`description` 写得越清晰、包含越多触发关键词，AI 就越能在正确时机自动调用，而不需要用户手动指定。

例如，`1初步筛选` 的 SKILL.md 头部：
```yaml
---
name: 1初步筛选
description: >
  高考志愿硬约束过滤，筛选100%可填报专业。当用户提及高考、志愿填报、选学校、选专业、
  报考、分数线、位次、能上什么大学、能报什么专业等关键词时，必须触发本 skill。
---
```

### 项目的 `.trae/` 目录即 Trae Solo 的配置目录

```
.trae/
├── rules/
│   ├── USER.md              # 用户画像，全局规则，所有 模块 自动读取
│   └── BOOTSTRAP.md         # 新用户引导，初次使用时自动触发
├── modules/                  # 各 模块 的 Markdown 定义文件
├── skills/
│   ├── constraint-filter/   # 1初步筛选 模块 的 Python 实现（已完成）
│   │   └── SKILL.md         # Trae Solo 识别此 Skill 的入口
│   └── data-pipeline/       # 0准备数据 模块（已完成）
│       └── SKILL.md
└── references/              # 专业/院校数据库（模块 的知识来源）
```

---

## 系统定位（`CLAUDE.md` 是主控入口）

项目根目录的 `CLAUDE.md` 是整个系统的 AI 入口文件，相当于系统的"总指挥"。对话时，AI 从 `CLAUDE.md` 读取系统架构和协作规则，然后按流水线逐步输出志愿方案。

用户画像的详细定义见 → `./USER.md`

---

## 系统架构：统一 模块 驱动 (Gaokao Expert)

本项目已升级为**单 模块 核心 + 领域专家技能 (Skills)** 架构。对话启动时，AI 即是“高考志愿填报高级顾问”。

### 核心角色 (Gaokao Expert)
深耕高考志愿填报领域的资深专家，专门为本科线到 211 线之间的普通家庭考生提供科学、务实、可执行的方案。

### 全生命周期工作流
系统通过以下 6 个逻辑阶段引导用户完成决策：

1. **阶段 0：数据准备 (data-pipeline)**
   - **任务**：将官方 PDF/Excel 转化为系统可用的 CSV 数据。
   - **工具**：`0准备数据` 技能。

2. **阶段 1：初步筛选 (constraint-filter)**
   - **任务**：圈出 100% 可合法填报的基本盘。
   - **工具**：`1初步筛选` 技能。

3. **阶段 2：选专业 (major-evaluator)**
   - **任务**：深度拆解专业价值（维度：宽度、体制导向、地域性、陷阱、匹配度）。
   - **工具**：`2选专业` 技能。

4. **阶段 3：选学校 (school-matcher)**
   - **任务**：针对选定专业，寻找性价比最高的“窝里横”大学。
   - **工具**：`3选学校` 技能。

5. **阶段 4：填报策略 (strategy-planner)**
   - **任务**：确定 96 个志愿（如山东）的排列顺序。
   - **工具**：`4填报策略` 技能。

6. **阶段 5：精调终审 (special-advisor)**
   - **任务**：特殊群体（女生、数理薄弱、低分段）微调及安全终审。
   - **工具**：`5精调终审` 技能。

---

## 核心规则
- **环境感知 (Environment Sensing)**：在开始任何咨询前，**必须优先**扫描 `结果/` 目录。
- **文件命名规范**：各 Skill 生成的所有结果文件（报告、数据、中间状态等），**文件名头部必须包含该 Skill 的完整中文名称**（例如 `1初步筛选_考生画像_山东.md` 或 `4填报策略_志愿方案.md`），以便明确产出来源。
- **数据先行**：缺失必要数据时优先引导进入阶段 0。
- **阶梯推进**：完成上一阶段产出后才进入下一阶段。
- **主动引导 (Proactive Guidance)**：从阶段 1（初筛）进入阶段 2（选专业）时，若已存在初筛结果，**必须自动调用** `major-evaluator` 的 `--overview` 功能生成《可选专业方向概览》，并在对话中引导用户基于此概览缩小兴趣范围，禁止仅通过提问等待。
- **禁止编造**：所有数据必须来自本地文件。



**参考数据库**（模块 的知识来源）：
- `.trae/references/major-database.md` —— 专业分类与评价数据（含张雪峰评价体系）
- `.trae/references/school-database.md` —— 院校推荐数据与评价维度

---

## 已实现的代码（Skills）

目前 `1初步筛选` 模块和数据导入工具已经用 Python 实现，位于 `.trae/skills/` 目录下。

### 1初步筛选 模块：初步筛选 (constraint-filter)

**目录**：`.trae/skills/constraint-filter/`

**核心使命**：用最严格的刚性条件，圈出考生"100% 可以合法填报"的基本盘。**宁可停下报错，不可输出误导。**

#### 运行方式

```bash
cd .trae/skills/constraint-filter

# 用考生 JSON 文件运行（--pretty 输出中文友好格式）
python main.py tests/fixtures/henan_physics_medium.json --pretty

# 从标准输入读取
python main.py -

# 指定数据目录
python main.py applicant.json --data-dir /path/to/data
```

退出码：`0` 成功 / `2` 有错误

#### 运行测试

```bash
cd .trae/skills/constraint-filter
python -m unittest discover -s tests -v
```

需要 **Python 3.9+**，**仅依赖标准库，无需安装额外包**。

#### 代码结构

```
constraint_filter/
├── pipeline.py         # 主流水线，按顺序执行五层过滤
├── input_validator.py  # 校验必填字段，字段缺失立即停止
├── subject_parser.py   # 解析选科要求字符串（如"物理+化学"）→ 结构化表达式
├── physical_filter.py  # 第四层：体检限制过滤
├── rank_tier.py        # 计算 rank_ratio，打冲/稳/保标签
└── data_loader.py      # 加载 JSON 数据文件，校验 valid_for_year 版本
```

#### 五层过滤逻辑（顺序执行，前层不过就直接排除）

1. **省份与招生计划过滤** —— 只保留该省有招生计划的院校专业
2. **分数位次过滤** —— 用 `rank_ratio = 考生位次 / 历史最低录取位次加权平均` 分档（权重：最近年 0.5 / 次年 0.3 / 再前年 0.2），默认保留 rank_ratio ∈ [0.8, 2.0]
3. **选科过滤** —— 解析招生计划中的选科要求，不满足则排除；解析失败直接报错，不猜
4. **体检限制过滤** —— 对照 `data/physical_restrictions.json`，色盲/色弱/视力/身高等
5. **政审与特殊限制过滤** —— 公安/军校/定向等

#### 考生输入 JSON 格式（必填字段）

```json
{
  "province": "河南",
  "total_score": 580,
  "provincial_rank": 45000,
  "subject_category": "物理类",
  "selected_subjects": ["物理", "化学", "生物"],
  "gender": "男",
  "exam_year": 2026
}
```

可选字段：`physical_exam`（体检信息）、`political_review_clean`（政审是否清白）、`preferred_cities`、`family_economy_level`、`target_system`

---

### 数据准备 模块 (data-pipeline)

**目录**：`.trae/skills/data-pipeline/`

**功能**：把官方文件（PDF/Excel/Word 格式的招生计划、历史录取位次、一分一段表等）转化成 `1初步筛选` 模块能直接消费的干净数据文件。**超过500条记录的大文件自动输出 JSONL，小文件输出 JSON。**

#### 安装依赖

```bash
cd .trae/skills/data-pipeline
pip install -r requirements.txt   # Python 3.9+
```

依赖：`pdfplumber`（PDF 解析）、`openpyxl`（Excel 解析）、`python-docx`（Word 解析）

#### 运行方式

```bash
# 一站式处理（推荐）：识别 → 提取 → 归一化 → 校验（不自动写入，等用户确认）
python main.py run 河南招生计划.pdf --province 河南 --year 2026

# 分步执行
python main.py detect 河南招生计划.pdf          # 识别文件类型
python main.py extract 河南招生计划.pdf -o /tmp/raw.json   # 提取原始数据
python main.py store /tmp/normalized.json       # 确认后写入

# 覆盖已有文件
python main.py store /tmp/normalized.json --overwrite
```

数据写入目标：`.trae/constraint-filter/data/admission_plans/`

---

## 如何新增省份数据

1. 准备该省官方招生计划文件（PDF 或 Excel），用 `0准备数据` 导入
2. 生成的 JSON 放入 `data/admission_plans/<省份拼音>_<年份>.json`
3. 在 `constraint_filter/data_loader.py` 的 `PROVINCE_FILE_SLUG` 中添加省份映射
4. 确认 `data/province_exam_mode.json` 中已包含该省的高考模式

---

## 如何扩展规则（重要：不要硬编码进 Python）

- **体检限制规则** → 只修改 `data/physical_restrictions.json`，每条必须填 `authority`（文件来源）
- **选科要求解析规则** → 只修改 `data/subject_requirement_keywords.json`
- **新增 模块** → 在 `.trae/modules/` 下新建 `.md` 文件，在 `CLAUDE.me` 中注册

---

## 核心设计原则（开发时必须遵守）

**宁可停下报错，绝不输出误导。** 具体体现：

| 场景 | 正确行为 | 禁止行为 |
|------|----------|----------|
| 必填字段缺失 | 停止，报 `INPUT_MISSING_REQUIRED_FIELD` | 用默认值继续跑 |
| 选科要求无法解析 | 停止，报 `RUNTIME_SUBJECT_REQUIREMENT_PARSE_FAILED` | 模糊匹配或按常见情况推断 |
| 招生计划文件不存在 | 停止，报 `DATA_SOURCE_UNAVAILABLE` | 用网页搜索替代 |
| 数据年份与考生年份不符 | 停止，报 `DATA_VERSION_MISMATCH` | 用旧数据继续 |
| 某专业历史数据缺失 | 保留但标记 `historical_data_missing: true` + 加入 warnings | 用均值估算 |
| 体检规则未覆盖某专业 | 保留但标记 `physical_check: not_verified` + 加入 warnings | 自行推测 |

**AI 在使用本地数据时，禁止通过网页搜索获取招生计划、一分一段表、位次等数据。** 本地数据是唯一可信源。

---

## 目前的限制（MVP 阶段）

- 招生计划样本数据仅覆盖**河南省 2026 年**（少量院校），其他省份需补充数据
- 不接入任何外部实时 API，全部使用本地 JSON 文件
- 单科成绩限制（如"数学≥120分"）尚未实现
- 定向生、专项计划、艺术/体育类等特殊批次尚未实现
- 选专业/选学校/填报策略/精调终审 目前仅有 Markdown 定义，代码尚未实现
