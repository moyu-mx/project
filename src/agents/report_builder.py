"""Markdown 报告构建：表格 + Mermaid 图表 + 运营建议。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from src.agents.report_data import PeriodMetrics, load_report_data


def _money(v: float) -> str:
    return f"{v:,.2f}"


def _pct_share(v: float, total: float) -> str:
    if total <= 0:
        return "0.0%"
    return f"{v / total * 100:.1f}%"


def _bar(v: float, max_v: float, width: int = 12) -> str:
    if max_v <= 0:
        return ""
    n = max(1, int(v / max_v * width))
    return "█" * n


def _mermaid_pie(
    title: str,
    items: list[tuple[str, float]],
    max_items: int = 8,
    min_label_pct: float = 0.10,
) -> str:
    """饼图：占比 < min_label_pct 的项合并为「其他」，避免标签重叠。"""
    if not items:
        return "_暂无数据_"
    trimmed = sorted(items, key=lambda x: -x[1], reverse=True)[:max_items]
    total = sum(v for _, v in trimmed)
    if total <= 0:
        return "_暂无数据_"

    major: list[tuple[str, float]] = []
    minor_sum = 0.0
    for name, val in trimmed:
        if val / total >= min_label_pct:
            major.append((name, val))
        else:
            minor_sum += val
    if minor_sum > 0:
        major.append(("其他", minor_sum))
    if not major:
        major = [trimmed[0]]

    safe_title = title.replace('"', "'").replace("\n", " ")
    lines = ["```mermaid", "pie", f"    title {safe_title}"]
    for name, val in major:
        safe = str(name).replace('"', "'").replace(":", " ")
        lines.append(f'    "{safe}" : {max(1, int(round(val)))}')
    lines.append("```")
    return "\n".join(lines)


def _markdown_trend_chart(title: str, labels: list[str], values: list[float]) -> str:
    """销售趋势：Markdown 表格 + Unicode 柱状条（全平台可显示，不依赖 Mermaid 版本）。"""
    if not labels or not values:
        return "_暂无趋势数据_"
    max_v = max(values) if values else 1.0
    lines = [
        f"**{title}**",
        "",
        "| 日期 | 销售额 | 柱状示意 |",
        "| --- | ---: | --- |",
    ]
    for lb, val in zip(labels, values):
        s = str(lb).strip()
        label = f"{s}日" if s.isdigit() else s
        lines.append(f"| {label} | {_money(val)} | {_bar(val, max_v, 18)} |")
    return "\n".join(lines)


def _kpi_table(cur: PeriodMetrics, prev: PeriodMetrics, yoy: PeriodMetrics | None, mom: dict, yoy_pct: dict | None) -> str:
    rows = [
        ("销售额", _money(cur.sales), _money(prev.sales), mom.get("sales", "—"),
         _money(yoy.sales) if yoy else "—", yoy_pct.get("sales", "—") if yoy_pct else "—"),
        ("利润", _money(cur.profit), _money(prev.profit), mom.get("profit", "—"),
         _money(yoy.profit) if yoy else "—", yoy_pct.get("profit", "—") if yoy_pct else "—"),
        ("订单量", str(cur.orders), str(prev.orders), mom.get("orders", "—"),
         str(yoy.orders) if yoy else "—", yoy_pct.get("orders", "—") if yoy_pct else "—"),
        ("客单价", _money(cur.aov), _money(prev.aov), mom.get("aov", "—"),
         _money(yoy.aov) if yoy else "—", yoy_pct.get("aov", "—") if yoy_pct else "—"),
    ]
    lines = [
        "| 指标 | 本期 | 上期 | 环比 | 去年同期 | 同比 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(f"| {' | '.join(row)} |")
    return "\n".join(lines)


def _region_table(regions: list[dict], total_sales: float) -> str:
    if not regions:
        return "_暂无区域数据_"
    lines = ["| 区域 | 销售额 | 占比 | 利润 |", "| --- | ---: | ---: | ---: |"]
    for r in regions[:10]:
        sales = float(r["sales"])
        lines.append(
            f"| {r['market']} | {_money(sales)} | {_pct_share(sales, total_sales)} | {_money(float(r.get('profit', 0)))} |"
        )
    return "\n".join(lines)


def _build_monthly(data: dict[str, Any], generated_at: str) -> tuple[str, str, str]:
    title = f"月度电商经营报告 — {data['period_label']}"
    cur: PeriodMetrics = data["current"]
    pie = _mermaid_pie(
        "区域销售额占比",
        [(r["market"], float(r["sales"])) for r in data.get("regions", [])],
    )
    daily = data.get("daily") or []
    trend_daily = _markdown_trend_chart(
        "月内日销售额",
        [str(int(d["day"])) for d in daily],
        [float(d["sales"]) for d in daily],
    )
    cat_total = sum(float(c["sales"]) for c in data.get("categories", []))
    cat_lines = ["| 品类 | 销售额 | 占比 | 利润 |", "| --- | ---: | ---: | ---: |"]
    for c in data.get("categories", []):
        s = float(c["sales"])
        cat_lines.append(
            f"| {c['category']} | {_money(s)} | {_pct_share(s, cat_total)} | {_money(float(c['profit']))} |"
        )

    md = f"""# {title}

> 生成时间：{generated_at}  
> 数据来源：超市电商 SQLite 订单库 · Agent1 自动生成

## 一、核心指标概览

{_kpi_table(cur, data["previous"], data.get("yoy"), data["mom"], data.get("yoy_pct"))}

## 二、月内销售趋势

{trend_daily}

## 三、区域表现

{_region_table(data.get("regions", []), cur.sales)}

{pie}

## 四、品类结构

{chr(10).join(cat_lines)}

## 五、结论与建议

1. 本月销售额 **{_money(cur.sales)}**，环比 {data['mom']['sales']}，同比 {data.get('yoy_pct', {}).get('sales', '—')}。
2. 优先巩固销售额领先区域，对低占比区域制定专项促销。
3. 关注利润率为负或偏低的品类，优化折扣与选品策略。
4. 结合仪表盘「预测分析」模块，提前规划下一周期备货与营销预算。
"""
    filename = f"monthly_report_{data['period_label'].replace('年', '').replace('月', '')}.md"
    return title, md, filename


def _build_weekly(data: dict[str, Any], generated_at: str) -> tuple[str, str, str]:
    title = f"周度经营快报 — {data['period_label']}"
    cur: PeriodMetrics = data["current"]
    pie = _mermaid_pie(
        "本周区域销售额",
        [(r["market"], float(r["sales"])) for r in data.get("regions", [])],
    )
    daily = data.get("daily") or []
    trend = _markdown_trend_chart(
        "周内日销售额",
        [str(int(d["day"])) for d in daily],
        [float(d["sales"]) for d in daily],
    )
    md = f"""# {title}

> 生成时间：{generated_at}

## 一、本周 KPI

| 指标 | 本周 | 上周 | 环比 |
| --- | ---: | ---: | ---: |
| 销售额 | {_money(cur.sales)} | {_money(data['previous'].sales)} | {data['mom']['sales']} |
| 利润 | {_money(cur.profit)} | {_money(data['previous'].profit)} | {data['mom']['profit']} |
| 订单量 | {cur.orders} | {data['previous'].orders} | {data['mom']['orders']} |
| 客单价 | {_money(cur.aov)} | {_money(data['previous'].aov)} | — |

## 二、周内趋势

{trend}

## 三、区域贡献

{_region_table(data.get('regions', []), cur.sales)}

{pie}

## 四、建议

1. 若环比下滑，检查本周促销力度与库存是否充足。
2. 将资源向周内峰值日倾斜，提升转化效率。
"""
    fn = f"weekly_report_{data['period_label'].replace('年', '').replace('月', 'm').replace('第', 'w').replace('周', '')}.md"
    return title, md, fn.replace(" ", "")


def _build_daily(data: dict[str, Any], generated_at: str) -> tuple[str, str, str]:
    title = f"日度经营快照 — {data['period_label']}"
    cur: PeriodMetrics = data["current"]
    top_lines = ["| 商品 | 品类 | 销售额 | 销量 |", "| --- | --- | ---: | ---: |"]
    for p in data.get("top_products", []):
        top_lines.append(
            f"| {p['product_name'][:40]} | {p['category']} | {_money(float(p['sales']))} | {int(p['qty'])} |"
        )
    md = f"""# {title}

> 生成时间：{generated_at}

## 一、当日 KPI

| 指标 | 数值 |
| --- | ---: |
| 销售额 | {_money(cur.sales)} |
| 利润 | {_money(cur.profit)} |
| 订单量 | {cur.orders} |
| 活跃客户 | {cur.customers} |
| 客单价 | {_money(cur.aov)} |
| 较近 7 日均值 | {data.get('vs_avg7', '—')} |

## 二、当日爆款 TOP5

{chr(10).join(top_lines)}

## 三、建议

1. 对比近 7 日均值，判断当日是否为异常峰值或低谷。
2. 对 TOP 商品确保库存与曝光；低动销 SKU 考虑捆绑促销。
"""
    fn = f"daily_report_{data['period_label'].replace('年', '').replace('月', 'm').replace('日', 'd')}.md"
    return title, md, fn


def _build_product(data: dict[str, Any], generated_at: str) -> tuple[str, str, str]:
    year = data["year"]
    title = f"商品分析报告 — {year}年"
    cats = data.get("categories") or []
    pie = _mermaid_pie(
        "品类销售额占比",
        [(c["category"], float(c["sales"])) for c in cats],
    )
    top_lines = ["| # | 商品 | 品类 | 销售额 | 销量 | 利润 |", "| ---: | --- | --- | ---: | ---: | ---: |"]
    for i, p in enumerate(data.get("top", []), 1):
        top_lines.append(
            f"| {i} | {p['product_name'][:36]} | {p['category']} | {_money(float(p['sales']))} | "
            f"{int(p['quantity'])} | {_money(float(p['profit']))} |"
        )
    bottom_lines = ["| # | 商品 | 品类 | 销售额 | 销量 |", "| ---: | --- | --- | ---: | ---: |"]
    for i, p in enumerate(data.get("bottom", []), 1):
        bottom_lines.append(
            f"| {i} | {p['product_name'][:36]} | {p['category']} | {_money(float(p['sales']))} | {int(p['quantity'])} |"
        )
    md = f"""# {title}

> 生成时间：{generated_at}

## 一、品类概览

{pie}

| 品类 | 销售额 | 利润 | 销量 |
| --- | ---: | ---: | ---: |
"""
    for c in cats:
        md += f"| {c['category']} | {_money(float(c['sales']))} | {_money(float(c['profit']))} | {int(c['quantity'])} |\n"

    md += f"""
## 二、爆款 TOP10

{chr(10).join(top_lines)}

## 三、滞销预警 BOTTOM10

{chr(10).join(bottom_lines)}

## 四、诊断与建议

1. **爆款**：加大 TOP 商品库存与首页曝光，考虑组合套餐提升客单价。
2. **滞销**：对 BOTTOM 商品做限时折扣或区域清仓，减少占用资金。
3. **品类**：利润贡献低的品类审查折扣策略，向高利润 Technology 类倾斜资源。
"""
    return title, md, f"product_report_{year}.md"


def _build_user(data: dict[str, Any], generated_at: str) -> tuple[str, str, str]:
    year, rfm_year = data["year"], data["rfm_year"]
    title = f"用户运营报告 — {year}年（RFM {rfm_year}）"
    rfm_items = [(r["value_segment"], float(r["customer_count"])) for r in data.get("rfm", [])]
    pie_rfm = _mermaid_pie("RFM 客户价值分布", rfm_items)
    seg_items = [(r["segment"], float(r["sales"])) for r in data.get("segments", [])]
    pie_seg = _mermaid_pie("客户类型销售额占比", seg_items)
    rfm_lines = ["| 价值分层 | 客户数 | 占比 |", "| --- | ---: | ---: |"]
    total_rfm = sum(float(r["customer_count"]) for r in data.get("rfm", []))
    for r in data.get("rfm", []):
        c = float(r["customer_count"])
        rfm_lines.append(f"| {r['value_segment']} | {int(c)} | {_pct_share(c, total_rfm)} |")

    md = f"""# {title}

> 生成时间：{generated_at}

## 一、客户活跃概况（{year}年）

| 指标 | 数量 |
| --- | ---: |
| 活跃客户 | {data['total_active']} |
| 新客户 | {data['new_customers']} |
| 回头客 | {data['returning_customers']} |

## 二、RFM 价值分层（快照 {rfm_year}）

{chr(10).join(rfm_lines)}

{pie_rfm}

## 三、Segment 客户类型

| 类型 | 客户数 | 销售额 |
| --- | ---: | ---: |
"""
    for s in data.get("segments", []):
        md += f"| {s['segment']} | {s['customer_count']} | {_money(float(s['sales']))} |\n"

    md += f"""
{pie_seg}

## 四、运营建议

1. **重要价值/保持客户**：提供会员专属折扣与优先发货，提升 LTV。
2. **重要发展/挽留客户**：推送个性化品类推荐，激活沉睡购买。
3. **一般客户**：通过满减与新品试用扩大购买频次。
4. **新客获取**：针对 {year} 年新客占比，加强首单优惠与复购提醒。
"""
    return title, md, f"user_report_{year}_rfm{rfm_year}.md"


_BUILDERS = {
    "monthly": _build_monthly,
    "weekly": _build_weekly,
    "daily": _build_daily,
    "product": _build_product,
    "user": _build_user,
}


def generate_report_markdown(report_type: str, params: dict[str, Any]) -> dict[str, str]:
    """生成完整 Markdown 报告，返回 title / filename / markdown。"""
    if report_type not in _BUILDERS:
        raise ValueError(f"未知报告类型: {report_type}")
    data = load_report_data(report_type, params)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    title, markdown, filename = _BUILDERS[report_type](data, generated_at)
    return {
        "report_type": report_type,
        "title": title,
        "filename": filename,
        "markdown": markdown,
        "generated_at": generated_at,
    }
