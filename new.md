# v1.5 Agent 开发规划 — 分析报告 & 数据洞察

> 基于 v1.4（动态图表 + 区间筛选 + 预测参数可调）继续迭代。

## 一、目标

在大模型智能查询模块旁增加 **Agent 选择框**，交付：

- **Agent1**：完整分析报告（Markdown + Mermaid）
- **Agent2**：数据解读 & 推理（波动原因、异常预警、机会点）

## 二、Agent 清单

| Agent | 名称 | 状态 |
|-------|------|------|
| 默认 | 智能查询（NL2SQL + 图表） | ✅ v1.4 |
| Agent1 | 完整分析报告生成 | ✅ v1.5 |
| Agent2 | 数据洞察推理 | ✅ v1.5 |

### Agent1 报告类型

| 类型 ID | 名称 | 说明 |
|---------|------|------|
| `monthly` | 月报 · 月度电商经营总结 | KPI 表（环比/同比）+ 月内日趋势 + 区域/品类 + Mermaid 饼图 |
| `weekly` | 周报 · 周度经营快报 | 指定年月第 N 周 KPI + 周内日趋势 + 区域饼图 |
| `daily` | 日报 · 日度经营快照 | 单日 KPI + 近 7 日均值对比 + 当日爆款 TOP5 |
| `product` | 商品分析报告 | 爆款 TOP10 / 滞销 BOTTOM10 + 品类表 + Mermaid 品类饼图 |
| `user` | 用户运营报告 | RFM 分层 + Segment + 新老客 + 双 Mermaid 饼图 + 运营建议 |

### Agent2 洞察输出

| 类别 | 示例（映射真实字段） |
|------|----------------------|
| 波动原因 | 「3 月销售额环比下降 18%，主要是 Office Supplies 品类下滑」 |
| 异常预警 | 「Central 平均折扣率 12%，远高于均值 3.2%，存在毛利侵蚀风险」 |
| 机会点 | 「非头部区域复购率提升明显，可重点运营」 |

**输入**：指定年月 KPI + 品类/区域/复购聚合；可选粘贴查询结果（API 模式解读）。  
**调用**：规则异常检测 + 本地模板 / DeepSeek 文本生成 API。

## 三、Agent2 技术架构

```
前端 Agent2 + 年月 + 调用方式（local/api）
    ↓ POST /api/agents/insight/generate
insight_data.py     ← SQL 聚合环比、品类、区域折扣、复购
    ↓
anomaly_detect.py   ← 规则异常（环比骤降、高折扣、负利润、复购提升）
    ↓
insight_engine.py   ← 本地结论 / DeepSeek JSON 洞察
    ↓
insight_builder.py  → Markdown（三类结论 + KPI 附录 + 异常表）
    ↓
{ title, filename, markdown, insights } → 预览 + 下载
```

| 模块 | 路径 | 职责 |
|------|------|------|
| 取数 | `src/agents/insight_data.py` | 月度 KPI、品类环比、区域指标、复购 |
| 异常 | `src/agents/anomaly_detect.py` | 波动/风险/机会规则检测 |
| 推理 | `src/agents/insight_engine.py` | 本地模板 + DeepSeek API |
| 构建 | `src/agents/insight_builder.py` | Markdown 报告 |
| 配置 | `src/agents/config.py` | Agent 元数据 |
| API | `web/app.py` | `POST /api/agents/insight/generate` |
| 前端 | `index.html` + `app.js` | Agent2 参数、预览、下载 |
| 测试 | `tests/test_insight_agent.py` | 取数、异常、本地流水线、API 冒烟 |

## 四、Agent1 Markdown 模板（含图表）

图表采用 **Mermaid**；饼图占比 **<10%** 的项自动合并为「其他」。

## 五、开发进度

### Agent1
- [x] Step 0 规划
- [x] Step 1 后端 report_data + report_builder
- [x] Step 2 API 路由
- [x] Step 3 前端 Agent 选择与下载
- [x] Step 4 联调（`pytest tests/test_agents.py`）

### Agent2
- [x] **Step 0** 规划写入 `new.md`
- [x] **Step 1** `insight_data` + `anomaly_detect` 取数与规则异常
- [x] **Step 2** `insight_engine` + `insight_builder`（本地 + DeepSeek API）
- [x] **Step 3** API `POST /api/agents/insight/generate`
- [x] **Step 4** 前端 Agent2 控件 + 预览/下载
- [x] **Step 5** 测试 `pytest tests/test_insight_agent.py`

## 六、使用方式

### Agent1
1. Agent 选择 **Agent1 · 分析报告**
2. 选择报告类型与年月 → **生成 Markdown 报告**

### Agent2
1. Agent 选择 **Agent2 · 数据洞察推理**
2. 选择年月；调用方式选 **本地** 或 **API**（需 `config/llm_keys.yaml` 或 `DEEPSEEK_API_KEY`）
3. 可选填写「补充数据」粘贴查询结果
4. 点击 **生成洞察报告** → 自动下载 `.md`，对话框预览三类结论

## 七、后续（v1.6+）

- [ ] 对接 NL2SQL 查询结果自动传入 Agent2
- [ ] Agent1 摘要 LLM 润色
- [ ] 导出 PDF / HTML
- [ ] 对话框内 Mermaid 实时渲染
