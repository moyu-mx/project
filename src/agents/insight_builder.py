"""数据洞察 Markdown 报告构建。"""
from __future__ import annotations

from typing import Any


def _money(v: float) -> str:
    return f"{v:,.2f}"


def _fmt_mom(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:+.1f}%"


def _bullets(items: list[str]) -> str:
    if not items:
        return "- _暂无_\n"
    return "".join(f"- {line}\n" for line in items)


def _anomaly_table(anomalies: list[dict[str, Any]]) -> str:
    if not anomalies:
        return "_未触发规则异常_\n"
    lines = ["| 类型 | 严重度 | 指标 | 对象 | 说明 |", "| --- | --- | --- | --- | --- |"]
    type_map = {"volatility": "波动", "risk": "风险", "opportunity": "机会"}
    sev_map = {"high": "高", "medium": "中", "low": "低"}
    for a in anomalies:
        lines.append(
            f"| {type_map.get(a.get('type'), a.get('type'))} "
            f"| {sev_map.get(a.get('severity'), '-')} "
            f"| {a.get('metric', '-')} "
            f"| {a.get('entity', '-')} "
            f"| {a.get('detail', '-')} |"
        )
    return "\n".join(lines) + "\n"


def build_insight_markdown(payload: dict[str, Any]) -> dict[str, str]:
    """将 generate_insights 结果转为 Markdown 文件内容。"""
    context = payload["context"]
    anomalies = payload.get("anomalies") or []
    ins = payload.get("insights") or {}
    period = context.get("period_label", "")
    cur = context.get("current") or {}
    mom = context.get("mom_pct") or {}

    title = f"数据洞察推理报告 — {period}"
    filename = f"insight_{context.get('year', 2014)}_{context.get('month', 12):02d}.md"

    md = f"""# {title}

> 生成模式：{ins.get('mode', 'local')} · {ins.get('reasoning', '')}

## 一、波动原因

{_bullets(ins.get('volatility') or [])}
## 二、异常预警

{_bullets(ins.get('anomalies') or [])}
## 三、机会点

{_bullets(ins.get('opportunities') or [])}
## 附录 A · 核心 KPI

| 指标 | 当月 | 环比 |
| --- | --- | --- |
| 销售额 | {_money(float(cur.get('sales') or 0))} | {_fmt_mom(mom.get('sales'))} |
| 利润 | {_money(float(cur.get('profit') or 0))} | {_fmt_mom(mom.get('profit'))} |
| 订单数 | {int(cur.get('orders') or 0):,} | {_fmt_mom(mom.get('orders'))} |
| 客单价 | {_money(float(cur.get('aov') or 0))} | — |
| 平均折扣率 | {float(cur.get('avg_discount') or 0)*100:.1f}% | — |

## 附录 B · 异常检测明细

{_anomaly_table(anomalies)}
"""
    return {"title": title, "filename": filename, "markdown": md}
