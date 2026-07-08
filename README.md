# 电商平台数据分析

基于大型超市零售订单数据的分析系统：完成数据清洗、多维可视化分析、SQLite 入库，并提供 Web 仪表盘与自然语言 SQL 查询能力。

当前版本 v1.5，新增 Agent1 分析报告与 Agent2 数据洞察推理（Markdown 生成与下载）

## 功能概览


| 模块      | 说明                                          |
| ------- | ------------------------------------------- |
| 数据清洗    | 读取 `data.csv`，删除无效列、统一日期格式、派生时间维度字段         |
| 数据分析    | 利润、销售额、客单价、区域、淡旺季、新老客户、RFM 等 11 张图表         |
| 数据入库    | 星型模型写入 SQLite，含年度/区域/RFM 等预计算汇总表            |
| Web 仪表盘 | 固定导航 + 可滚动内容区，图表点击放大并展示数据解读                 |
| Agent 报告 | Agent1 月/周/日报、商品/用户 Markdown；Agent2 波动原因、异常预警、机会点 |
| 大模型查询   | MCP 工具注入 schema 语义，支持 **本地/API** 双模式 NL2SQL |


## 技术栈

- **Python 3.10+** · pandas · matplotlib · seaborn
- **SQLite** · SQLAlchemy
- **FastAPI** · Jinja2 · Uvicorn
- **MCP**（Model Context Protocol）· OpenAI API（可选）

## 项目结构

```
prj/
├── data.csv                    # 原始数据
├── data/cleaned/               # 清洗后 CSV
├── data/superstore.db          # SQLite 数据库（ETL 生成）
├── src/
│   ├── cleaning/               # 数据清洗
│   ├── analysis/               # 分析脚本与图表生成
│   ├── etl/                    # 入库 ETL
│   ├── db/                     # 数据库连接与查询执行
│   ├── mcp/                    # MCP 工具与 schema catalog
│   │   ├── schema_catalog.py   # 表/字段中文语义
│   │   ├── tools.py            # MCP 工具实现
│   │   └── server.py           # 独立 MCP Server
│   └── llm/                    # 对话引擎、NL2SQL、SQL 校验
├── web/
│   ├── app.py                  # Web 入口
│   ├── chart_insights.py       # 图表动态解读文案
│   ├── templates/              # 页面模板
│   └── static/                 # CSS / JS
├── sql/schema.sql              # 建表 DDL
├── config/                     # db.yaml、llm.yaml
├── prompts/nl2sql.txt          # LLM 提示词模板
├── results/charts/             # 分析图表输出
└── tests/                      # 单元测试
```

## 快速开始

### 1. 环境准备

```powershell
cd e:\26实训\prj
python -m venv .venv
.\.venv\Scripts\Activate.ps1
.\.venv\Scripts\pip install -r requirements.txt
```

### 2. 数据处理流水线

按顺序执行（**建议先完成 ETL，再启动 Web**）：

```powershell
# 数据清洗
.\.venv\Scripts\python -m src.cleaning.clean_data

# 生成全部分析图表
.\.venv\Scripts\python -m src.analysis.run_all

# 写入数据库
.\.venv\Scripts\python -m src.etl.load_to_db
```

也可一键执行清洗 + 分析：

```powershell
.\.venv\Scripts\python -m src.analysis.run_all
```

### 3. 启动 Web 服务

```powershell
.\.venv\Scripts\python -m uvicorn web.app:app --reload --app-dir . --port 8000
```

浏览器访问：**[http://127.0.0.1:8000](http://127.0.0.1:8000)**

## Web 使用说明

- **左侧导航**：固定不随页面滚动，点击跳转到对应分析区块
- **图表交互**：点击任意图表放大查看，右侧展示基于数据库的动态分析解读
- **智能查询**：页面底部输入自然语言问题，系统自动生成 SQL 并展示查询结果
- **Agent1 分析报告**：在「Agent」下拉框选择「Agent1 · 分析报告」，选择月报/周报/日报/商品/用户报告类型与周期，点击「生成 Markdown 报告」即可下载 `.md`（含 Mermaid 图表，建议用 Typora 或 GitHub 打开）
- **Agent2 数据洞察**：选择「Agent2 · 数据洞察推理」，指定年月与本地/API 模式，自动生成波动原因、异常预警、机会点 Markdown 报告

示例问题：

- `2013年各区域销售额是多少？`
- `各年销售额`
- `客单价趋势`
- `RFM客户价值分布`

## 大模型对话（MCP 双模式）

### 架构

```
用户提问 → chat_engine
              ├─ local：MCP 工具加载 schema + 本地规则生成 SQL
              └─ api：OpenAI 兼容 API + MCP function calling 多轮推理
           → SQL 安全校验 → 执行 → 返回结果
```

### MCP 工具


| 工具                    | 作用                               |
| --------------------- | -------------------------------- |
| `list_tables`         | 列出所有表及中文说明                       |
| `get_database_schema` | 表结构、字段类型、中文含义、业务规则               |
| `get_field_glossary`  | market/segment/category 等易混淆字段对照 |
| `preview_table`       | 预览表样本数据                          |


字段语义定义见 `src/mcp/schema_catalog.py`。

### 模式配置

编辑 `config/llm.yaml`：

```yaml
mode: local   # local | api

local:
  description: "MCP 工具 + 本地规则，无需 API Key"

api:
  provider: openai
  model: gpt-4o-mini
  api_key: "your-key"
  base_url: ""
```

- **local（默认）**：自动调用 MCP 工具注入完整 schema，本地规则匹配生成 SQL
- **api**：需配置 `api_key`，模型通过 function calling 调用 MCP 工具后再生成 SQL

### 独立 MCP Server（供 Cursor 等客户端）

```powershell
.\.venv\Scripts\python -m src.mcp.server
```

Cursor 配置示例见 `config/mcp.cursor.json`。

## 配置（其他）

默认 SQLite 路径：`data/superstore.db`  
表结构见 `sql/schema.sql`，主要包括：

- 维度表：`customers`、`products`、`regions`
- 事实表：`orders`
- 汇总表：`agg_sales_by_year`、`agg_sales_by_region_year`、`customer_rfm` 等

## 分析图表


| 图表                             | 说明                                 |
| ------------------------------ | ---------------------------------- |
| `sales_growth.png`             | 年度销售额与同比增长率                        |
| `avg_order_value.png`          | 年度客单价趋势                            |
| `profit_by_month.png`          | 2011–2014 各年月度利润                   |
| `seasonality_sales.png`        | 月度销售额淡旺季                           |
| `shipping_cost_trend.png`      | 发货成本趋势                             |
| `region_share.png`             | 区域销售额占比（<1% 合并为「其他」）               |
| `region_yearly_sales_top6.png` | 前六区域 2011–2014 年度销售额               |
| `new_old_customers.png`        | 新老客户数量                             |
| `segment_share.png`            | 客户类型占比                             |
| `segment_yearly_count.png`     | 各年客户类型数量                           |
| `segment_yearly_sales.png`     | 各类型客户年度销售额                         |
| `segment_category_sales.png`   | 客户群体与产品类别销售额                       |
| `rfm_distribution.png`         | RFM 客户价值分布（2014）                   |
| `sales_forecast.png`           | 2015 年度销售额预测（月度线性回归）               |
| `aov_forecast.png`             | 2015 客单价预测（RF/GBR/Ridge 自动选型 + 融合） |
| `seasonality_forecast.png`     | 2015 月度销售额/淡旺季预测                   |
| `region_forecast.png`          | 前六区域 2015 销售额预测                    |


### 预测分析说明

从现有展示图中选取 **4 组** 具有明显时间趋势、适合外推的指标做 2015 年预测（虚线/绿色/金色为预测值）：


| 历史图       | 预测图                        | 算法                                        | 数据粒度              |
| --------- | -------------------------- | ----------------------------------------- | ----------------- |
| 年度销售额与增长率 | `sales_forecast.png`       | 月度销售额一元线性回归，汇总全年                          | 48 个月原始订单         |
| 年度客单价趋势   | `aov_forecast.png`         | Random Forest / GBR / Ridge 自动选型 + 年度特征融合 | 48 月原始订单 + 年度聚合特征 |
| 月度销售额淡旺季  | `seasonality_forecast.png` | 线性趋势 + 季节指数                               | 48 个月原始订单         |
| 前六区域年度销售额 | `region_forecast.png`      | 各区域独立年度线性回归                               | 区域×年原始订单          |


单独运行预测：`python -m src.analysis.forecast`  
预测报告：`results/forecast_report.json`

## 数据清洗说明


| 步骤   | 处理内容                                                          |
| ---- | ------------------------------------------------------------- |
| 删除列  | 移除空值过多的 `Postal Code`                                         |
| 日期   | 兼容 `M/D/YYYY` 与 `DD-MM-YYYY` 两种格式                             |
| 数值   | 转换 Sales 等字段，剔除无效行（约 23 条）                                    |
| 派生字段 | `Order-year`、`Order-month`、`quarter`、`Ship-year`、`Ship-month` |


清洗报告：`results/cleaning_report.json`  
ETL 校验：`results/etl_validation.json`

## 测试

```powershell
.\.venv\Scripts\python -m pytest tests/ -q
```

## 常见问题

**ETL 报错「另一个程序正在使用此文件」**  
先 `Ctrl+C` 停止 Web 服务，再执行 `load_to_db`。

**端口 8000 被占用**

```powershell
netstat -ano | findstr :8000
taskkill /PID <PID> /F
# 或换端口
.\.venv\Scripts\python -m uvicorn web.app:app --reload --app-dir . --port 8001
```

**页面未更新**  
重启服务后使用 `Ctrl + F5` 强制刷新浏览器。

## 数据源字段

原始 CSV 主要字段：Order ID、Order Date、Ship Date、Customer ID、Segment、Market、Category、Sales、Quantity、Discount、Profit、Shipping Cost 等。详见项目根目录 `data.csv`。

---

超市电商数据分析课程项目