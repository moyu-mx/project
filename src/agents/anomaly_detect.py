"""规则 + 统计异常检测，为洞察 Agent 提供结构化异常列表。"""
from __future__ import annotations

from typing import Any


def detect_anomalies(context: dict[str, Any]) -> list[dict[str, Any]]:
    """返回异常项：type, severity, metric, entity, value, baseline, detail。"""
    anomalies: list[dict[str, Any]] = []
    cur = context.get("current") or {}
    mom = context.get("mom_pct") or {}
    avg_disc = float(context.get("avg_discount_all") or 0)

    sales_mom = mom.get("sales")
    if sales_mom is not None and sales_mom <= -10:
        worst_cats = sorted(
            context.get("category_mom") or [],
            key=lambda x: x.get("mom_pct") if x.get("mom_pct") is not None else 0,
        )
        driver = worst_cats[0]["category"] if worst_cats else "未知品类"
        driver_chg = worst_cats[0].get("mom_pct") if worst_cats else None
        anomalies.append({
            "type": "volatility",
            "severity": "high" if sales_mom <= -15 else "medium",
            "metric": "销售额环比",
            "entity": context.get("period_label", ""),
            "value": sales_mom,
            "baseline": 0,
            "detail": f"销售额环比下降 {abs(sales_mom):.1f}%，{driver} 品类环比 "
            f"{driver_chg:+.1f}%" if driver_chg is not None else f"销售额环比下降 {abs(sales_mom):.1f}%",
        })

    for cat in context.get("category_mom") or []:
        chg = cat.get("mom_pct")
        if chg is not None and chg <= -15:
            anomalies.append({
                "type": "volatility",
                "severity": "medium",
                "metric": "品类销售额环比",
                "entity": cat["category"],
                "value": chg,
                "baseline": 0,
                "detail": f"{cat['category']} 品类销售额环比下降 {abs(chg):.1f}%",
            })

    for region in context.get("regions") or []:
        disc = float(region.get("avg_discount") or 0)
        if avg_disc > 0 and disc >= avg_disc * 1.35 and disc - avg_disc >= 0.03:
            anomalies.append({
                "type": "risk",
                "severity": "high",
                "metric": "平均折扣率",
                "entity": region["market"],
                "value": disc * 100,
                "baseline": avg_disc * 100,
                "detail": f"{region['market']} 平均折扣率 {disc*100:.1f}%，"
                f"远高于均值 {avg_disc*100:.1f}%，存在毛利侵蚀/让利风险",
            })
        pr = float(region.get("profit_rate") or 0)
        if pr < 0:
            anomalies.append({
                "type": "risk",
                "severity": "high",
                "metric": "利润率",
                "entity": region["market"],
                "value": pr * 100,
                "baseline": 0,
                "detail": f"{region['market']} 当月利润率为负（{pr*100:.1f}%），需排查成本与定价",
            })

    for rp in context.get("repurchase") or []:
        rank = int(rp.get("sales_rank") or 99)
        mom_pp = rp.get("repurchase_mom_pp")
        rate = float(rp.get("repurchase_rate") or 0)
        if rank >= 4 and mom_pp is not None and mom_pp >= 5 and rate >= 0.35:
            anomalies.append({
                "type": "opportunity",
                "severity": "medium",
                "metric": "老客户复购率",
                "entity": rp["market"],
                "value": rate * 100,
                "baseline": (rate - mom_pp / 100) * 100,
                "detail": f"{rp['market']} 复购率 {rate*100:.1f}%，较上月提升 {mom_pp:.1f} 个百分点，"
                "非头部区域增长明显，可重点运营",
            })

    if not any(a["type"] == "opportunity" for a in anomalies):
        best = max(
            context.get("repurchase") or [{"repurchase_rate": 0, "market": ""}],
            key=lambda x: x.get("repurchase_mom_pp") or -999,
        )
        if best.get("repurchase_mom_pp") and best["repurchase_mom_pp"] > 2:
            anomalies.append({
                "type": "opportunity",
                "severity": "low",
                "metric": "复购率提升",
                "entity": best["market"],
                "value": float(best.get("repurchase_rate", 0)) * 100,
                "baseline": None,
                "detail": f"{best['market']} 复购率提升 {best['repurchase_mom_pp']:.1f} 个百分点，值得加大留存投入",
            })

    return anomalies
