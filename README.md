# LibCSQL：面向高校图书馆流通业务的 NL2SQL 测试集与实验框架

本仓库为独立研究《Comparing Large Language Models and Prompt Engineering Methods
for NL2SQL in Academic Library Scenarios: A Design Science Research Approach》的
配套制品，包含：

1. **测试集** `data/test_cases.json` —— 200 条面向图书馆流通业务的中文自然语言问题
   及其标注 SQL（gold SQL），覆盖四个难度层。
2. **原型系统** —— 将中文自然语言查询转换为安全可执行 SQL 的六层管线（Streamlit 界面）。
3. **实验框架** —— 统一多模型 API 调用、批量评测（EX/LF 自动计算）、失败案例自动分类
   的完整代码，可复现论文第 4 章的全部定量结果。

数据库为程序生成的**完全虚构**数据，不含任何真实读者信息；系统仅允许 SELECT
只读查询。测试集与代码在此公开，供后续研究者复现与扩展。

## 与 BibSQL 的区别

BibSQL (Wang et al., 2025) 面向图书馆**书目检索**（两张表、单跳/双跳元数据查询）；
本测试集面向**流通业务数据**——六张表通过外键关联（图书、读者、借阅记录、图书分类、
出版社、馆藏地），支持从单表查询到多表连接、嵌套子查询的各类操作，可回答"各学院
借阅量排名""借阅量超过学院均值的读者"等 BibSQL 结构上无法覆盖的统计查询。

## 项目结构

```
LibCSQL/
├── config.yaml                模型清单、生成参数、价格（开跑前核对模型ID与价格）
├── .env.example               API密钥模板（复制为 .env 后填写；.env 不会上传）
├── app.py                     Streamlit 原型界面（论文 4.1 节的原型系统）
├── reevaluate.py              JSON残渣修复重评测（论文 4.2.1 节）
├── error_taxonomy.py          失败查询的确定性分类（论文 4.3 节、表 4.4）
├── requirements.txt           依赖清单
├── src/                       原型系统六层管线
│   └── db_setup.py            建库 + 确定性模拟数据（固定随机种子，可复现）
├── data/
│   └── test_cases.json        200条标注测试集（每难度50条）
├── scripts/
│   ├── validate_test_cases.py 测试集校验（逐条执行标注SQL）
│   └── quick_stats.py         快速统计（EX/LF/Token 分模型分难度）
├── analysis/
│   └── descriptive_analysis.py  描述统计与热力图（论文表 4.1–4.3、图 4.1）
└── results/
    ├── raw/*.jsonl            5000 条原始查询记录（每次调用一行）
    ├── revalidated.csv        reevaluate.py 校正后的判定（论文全部准确率数字的来源）
    └── error_classification.csv  error_taxonomy.py 输出，每条查询一行及其错误类别
```

## 测试集说明

`data/test_cases.json` 共 200 条，每条含四个字段：

| 字段 | 说明 |
|------|------|
| `id` | 用例编号（如 L1-001） |
| `difficulty` | 难度层：L1_simple / L2_aggregation / L3_join / L4_nested |
| `question_zh` | 中文自然语言问题 |
| `sql_gold` | 人工标注并经执行验证的标准 SQL |

难度分布（各 50 条）：

- **L1 简单单表**：单表简单过滤（例：查找2025年出版的图书）
- **L2 单表聚合**：单表聚合/分组（例：按出版社统计藏书量）
- **L3 多表连接**：多表 JOIN（例：借阅过某书的读者姓名与学院）
- **L4 复杂嵌套**：嵌套子查询/多重聚合（例：借阅量超过学院均值的读者）

约三分之一的问题采用口语化表述，以测试系统对自然表达的鲁棒性。所有标注 SQL
均在模拟库上执行验证，确保可正确运行且返回预期结果。

## 环境要求

```bash
python -m venv venv
venv\Scripts\activate          # Windows；macOS/Linux 用 source venv/bin/activate
pip install -r requirements.txt
```

## 快速开始

```bash
# 1. 配置密钥
copy .env.example .env         # macOS/Linux 用 cp
# 编辑 .env 填入各平台密钥（本地 qwen2.5-coder 无需密钥）

# 2. 生成测试数据库
python -m src.db_setup

# 3. 校验测试集（每次改动后运行；逐条执行标注SQL确认可运行）
python scripts/validate_test_cases.py

# 4. 小成本试跑（先用1个模型验证全链路）
python -m src.runner --models qwen2.5-coder:7b --limit 5

# 5. 正式实验（5模型 × 5方法 × 200用例 = 5000次查询；可断点续跑）
python -m src.runner

# 6. JSON残渣修复重评测 → results/revalidated.csv
python reevaluate.py

# 7. 失败案例分类 → results/error_classification.csv 与论文表 4.4
python error_taxonomy.py

# 8. 描述统计与热力图（论文表 4.1、4.2、4.3 与图 4.1）
python analysis/descriptive_analysis.py

# 9. 启动原型界面
streamlit run app.py
```

只想核对论文数字、不想重跑 5000 次 API 调用的话，`results/raw/` 里的原始记录已经
全部提供，直接从第 6 步开始即可。

## 评测模型

本研究评测五款大语言模型（四款商业 API + 一款本地部署），均为国产模型：

| 模型 | 平台 | 类型 |
|------|------|------|
| qwen3.7-plus | 阿里云百炼 | 商业 / 高性能大模型 |
| doubao-seed-2.0-mini | 火山引擎 | 商业 / 中端 |
| ernie-4.5-turbo-32k | 百度千帆 | 商业 / 中端长上下文 |
| glm-4.7-flashX | 智谱 | 商业 / 中端快速响应 |
| qwen2.5-coder:7b | 本地 Ollama | 开源代码模型 / 零 API 成本 |

单价见 `config.yaml` 的 `pricing` 段（币种与核对日期在同一处声明；本次实验按各平台
官方价格页于 2026-07-20 核对的人民币单价计算，单位为元／百万 Token）。**复现前请
重新核对模型 ID 与当前定价**——模型版本会更新，价格页会变动。

成本口径：每 1000 次查询成本 =（平均输入 Token × 输入单价 + 平均输出 Token ×
输出单价）÷ 1e6 × 1000。本地部署模型无 API 费用，计为 0。

## 五种提示方法

Zero-shot、Few-shot、Chain-of-Thought (CoT)、Schema-Linking (SL)、CoT + Schema-Linking。
生成参数固定为 temperature = 0（减少输出变异）、max_tokens = 2048（防止 CoT 类
方法输出被截断——512 会系统性偏袒简单提示方法，属效度威胁）。

## 关于 reevaluate.py

部分模型（尤其本地 qwen2.5-coder:7b）输出的 JSON 中，SQL 字段末尾偶有残留收尾
字符（如 `"}`），导致 SQLite 报语法错误、被误判为 EX=0。`reevaluate.py` 在
**不改动模型原始输出**的前提下清理这些残渣后重新执行判定，仅对原判 EX=0 的记录
尝试恢复，原判 EX=1 的一律不动。

在本次实验数据上，该步骤恢复 32 条被误判的记录、无一条反向变化，总体 EX 由
0.690 升至 0.696。恢复集中在机制所预期的位置：32 条中有 31 条属于
qwen2.5-coder:7b 的 CoT 条件。论文第 4 章的全部准确率数字均以校正后的
`results/revalidated.csv` 为准。

## 关于 error_taxonomy.py

论文 4.3 节的失败分类由该脚本按**确定性规则**生成，不含任何人工编码，因此表 4.4
的每一格都可由本仓库文件重现。判定按以下顺序进行，每条查询只归入一类：

1. `correct` —— 校正后判定 EX = 1
2. `api_error` —— API 调用本身失败
3. `security_rejection` —— 安全层拒绝（`empty_sql` / `multiple_statements` / `not_select`）
4. `syntax_error` —— 执行报错含 `syntax error` / `unrecognized token` / `incomplete input`
5. `schema_reference_error` —— 执行报错含 `no such column` / `no such table`
6. `other_execution_error` —— 其余执行失败
7. `result_mismatch` —— SQL 可执行，但结果集与标注 SQL 不一致

## 关于统计口径

同一批 200 条测试用例在全部 25 个"模型 × 方法"条件下各运行一次，因此 5000 条记录
是同一组题目的重复测量，而非 25 组独立样本，且每格无重复试验。对其做方差分析会把
记录当作相互独立、低估残差，得到的 p 值不可解释。**论文因此以描述性方式报告模型与
方法的比较**——单元格均值、边际均值、各因素的极差、以及排序在不同条件下的稳定性。

早期版本 `analysis/anova_analysis.py` 曾输出 ANOVA、Tukey HSD 与 logistic 稳健性
检验，论文未采用这部分结果，该脚本已由 `analysis/descriptive_analysis.py` 取代。

推断检验只用在用户测试环节：20 名被试各自在两个系统上贡献一个配对观测，属于
标准的被试内配对设计。

## 指标口径

- **EX（执行准确率，主指标）**：预测 SQL 与标注 SQL 在测试库上执行结果集一致。
  标注 SQL 含顶层 ORDER BY 时按有序比较，否则按无序比较；浮点四舍五入到 1e-6。
- **LF（逻辑形式准确率）**：规范化后字符串匹配，为语义等价的保守下界，辅助指标。
  以 EX 为准，与 Spider 等基准通行做法一致。

## 已知说明

- `results/raw/*.jsonl` 中的 `ex` 字段为**校正前**判定，`error_type` 字段未使用（恒为空）。
  论文第 4 章的全部 EX 数字以 `results/revalidated.csv` 为准；失败分类以
  `results/error_classification.csv` 为准。分析脚本已强制读取前者，缺失时会报错退出。

## 数据伦理

数据库由 `src/db_setup.py` 以固定随机种子生成，全部读者姓名、借阅记录等均为程序
虚构，与任何真实人员无关；系统仅允许 SELECT 查询，无写入能力。

用户测试环节的参与者数据**不包含在本仓库中**。参与者在测试前获口头告知研究目的、
记录内容、数据用途与随时退出的权利，并据此口头同意；本研究未收取书面同意书，
亦未提交机构伦理审查。论文中仅报告汇总统计，不含任何可识别个人的信息。

## 引用

如使用本测试集或代码，请引用：

> He, X. (2026). LibCSQL: A NL2SQL test set and experimental framework for
> academic library circulation scenarios. GitHub. https://github.com/Chang-123ww/LibCSQL

## 许可

本仓库采用双许可：

- **测试集与数据**（`data/`）采用 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
  （知识共享署名 4.0）：可自由使用与再分发，但须署名引用本研究。
- **代码**（`src/`、`scripts/`、`analysis/` 及根目录脚本）采用
  [MIT License](https://opensource.org/licenses/MIT)：可自由使用、修改与分发，
  保留版权与许可声明即可。
