# 电商平台数据分析

基于大型超市零售订单数据的分析系统：完成数据清洗、多维可视化分析、SQLite 入库，并提供 Web 仪表盘、Agent 报告与自然语言 SQL 查询能力。

**当前版本：v1.6** · 工程设计实训课程项目

**GitHub 仓库：** https://github.com/moyu-mx/project

---

## 文档

| 文档 | 内容 |
| --- | --- |
| [项目功能](docs/项目功能.md) | 功能模块、技术栈、项目结构、Web 使用、MCP/NL2SQL、分析图表、数据说明 |
| [环境配置与运行](docs/环境配置与运行.md) | 环境要求、关键配置（含 API 密钥）、部署启动、打包分发、测试、常见问题 |

---

## 快速开始

```powershell
cd e:\26实训\prj
python -m venv .venv
.\.venv\Scripts\Activate.ps1
.\.venv\Scripts\pip install -r requirements.txt

# 数据处理流水线（首次必做）
.\.venv\Scripts\python -m src.analysis.run_all
.\.venv\Scripts\python -m src.etl.load_to_db

# 启动 Web
.\.venv\Scripts\python -m uvicorn web.app:app --reload --app-dir . --port 8000
```

浏览器访问 **http://127.0.0.1:8000**

详细步骤、配置说明与打包流程见 [环境配置与运行](docs/环境配置与运行.md)。

---

## 功能概览

| 模块 | 说明 |
| --- | --- |
| 数据清洗 | 读取 `data.csv`，统一格式、派生时间维度字段 |
| 数据分析 | 销售、利润、区域、客户、RFM 等 17 张图表 + 4 张预测图 |
| 数据入库 | 星型模型写入 SQLite |
| Web 仪表盘 | ECharts 动态图表 + 数据解读 |
| Agent 报告 | 月/周/日报、商品/用户报告；波动原因、异常预警、机会点 |
| 智能查询 | MCP + NL2SQL，支持 local / API 双模式 |

默认 **local 模式**可离线运行，无需 API 密钥。密钥配置见 [环境配置与运行 · 关键配置](docs/环境配置与运行.md#关键配置)。
