"""数据洞察推理引擎：异常检测 + 本地规则 / DeepSeek API 文本生成。"""
from __future__ import annotations

import json
from typing import Any

from src.agents.anomaly_detect import detect_anomalies
from src.agents.insight_data import fetch_insight_context
from src.llm.chat_engine import load_llm_config


def _local_insights(context: dict[str, Any], anomalies: list[dict[str, Any]]) -> dict[str, Any]:
    """基于规则与异常检测结果生成本地结论。"""
    volatility: list[str] = []
    risks: list[str] = []
    opportunities: list[str] = []

    mom = context.get("mom_pct") or {}
    period = context.get("period_label", "")
    sales_mom = mom.get("sales")
    profit_mom = mom.get("profit")

    if sales_mom is not None:
        direction = "上升" if sales_mom >= 0 else "下降"
        line = f"{period}销售额环比{direction} {abs(sales_mom):.1f}%"
        cats = context.get("category_mom") or []
        if cats and sales_mom < 0:
            worst = min(cats, key=lambda x: x.get("mom_pct") if x.get("mom_pct") is not None else 0)
            chg = worst.get("mom_pct")
            if chg is not None:
                line += f"，主要是 {worst['category']} 品类下滑（环比 {chg:+.1f}%）"
        elif cats and sales_mom > 0:
            best = max(cats, key=lambda x: x.get("mom_pct") if x.get("mom_pct") is not None else -999)
            chg = best.get("mom_pct")
            if chg is not None and chg > 0:
                line += f"，{best['category']} 品类拉动明显（环比 +{chg:.1f}%）"
        volatility.append(line)

    if profit_mom is not None and abs(profit_mom) >= 5:
        direction = "改善" if profit_mom >= 0 else "承压"
        volatility.append(f"利润环比{direction} {abs(profit_mom):.1f}%，需关注折扣与成本结构")

    for a in anomalies:
        detail = a.get("detail", "")
        if not detail:
            continue
        t = a.get("type")
        if t == "volatility" and detail not in volatility:
            volatility.append(detail)
        elif t == "risk":
            risks.append(detail)
        elif t == "opportunity":
            opportunities.append(detail)

    if not volatility:
        cur = context.get("current") or {}
        volatility.append(
            f"{period}经营平稳，销售额 {cur.get('sales', 0):,.0f}，"
            f"订单 {cur.get('orders', 0):,} 笔，环比波动在常态区间"
        )
    if not risks:
        avg_disc = float(context.get("avg_discount_all") or 0)
        risks.append(
            f"各区域平均折扣率整体 {avg_disc*100:.1f}%，未发现显著异常让利，"
            "建议持续监控负利润区域"
        )
    if not opportunities:
        rep = context.get("repurchase") or []
        if rep:
            top = max(rep, key=lambda x: x.get("repurchase_rate") or 0)
            opportunities.append(
                f"{top['market']} 老客户复购率最高（{top['repurchase_rate']*100:.1f}%），"
                "可复用其留存策略至其他区域"
            )
        else:
            opportunities.append("建议结合 RFM 分层，对高价值客户加大复购激励")

    return {
        "volatility": volatility[:5],
        "anomalies": risks[:5],
        "opportunities": opportunities[:5],
        "reasoning": "本地模式：规则异常检测 + 模板化结论生成。",
        "mode": "local",
    }


async def _api_insights(
    context: dict[str, Any],
    anomalies: list[dict[str, Any]],
    extra_data: str | None,
    cfg: dict,
) -> dict[str, Any]:
    from openai import AsyncOpenAI

    api_cfg = cfg.get("api", {})
    client = AsyncOpenAI(
        api_key=api_cfg.get("api_key", ""),
        base_url=api_cfg.get("base_url") or None,
        timeout=90.0,
    )
    model = api_cfg.get("model", "deepseek-chat")

    compact_ctx = {
        "period": context.get("period_label"),
        "mom_pct": context.get("mom_pct"),
        "current_kpi": context.get("current"),
        "category_mom": [
            {"category": c["category"], "mom_pct": c.get("mom_pct"), "sales": c.get("sales")}
            for c in (context.get("category_mom") or [])[:6]
        ],
        "regions": [
            {
                "market": r["market"],
                "profit_rate_pct": round(float(r.get("profit_rate") or 0) * 100, 1),
                "avg_discount_pct": round(float(r.get("avg_discount") or 0) * 100, 1),
            }
            for r in (context.get("regions") or [])[:8]
        ],
        "repurchase": [
            {
                "market": r["market"],
                "repurchase_rate_pct": round(float(r.get("repurchase_rate") or 0) * 100, 1),
                "mom_pp": r.get("repurchase_mom_pp"),
            }
            for r in (context.get("repurchase") or [])[:8]
        ],
        "detected_anomalies": anomalies,
    }
    user_extra = f"\n\n用户补充数据/查询结果：\n{extra_data}" if extra_data else ""

    system = (
        "你是超市电商数据分析专家。根据给定的 KPI、品类/区域指标与异常检测结果，"
        "生成简洁、具体、带数字的中文洞察结论。字段说明：market=销售区域，"
        "category=商品大类（Technology/Furniture/Office Supplies），"
        "avg_discount=平均折扣率，repurchase_rate=老客户复购占比。"
        "不要编造数据库中不存在的字段（如退款率、店铺名、美妆类目）。"
        "严格返回 JSON："
        '{"volatility":["波动原因…"],"anomalies":["异常预警…"],"opportunities":["机会点…"]}'
    )
    user_msg = (
        f"分析数据：\n{json.dumps(compact_ctx, ensure_ascii=False, indent=2)}"
        f"{user_extra}\n\n"
        "请各输出 2-4 条结论：volatility=波动原因，anomalies=异常预警，opportunities=机会点。"
    )

    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content or "{}"
    parsed = json.loads(raw)
    return {
        "volatility": list(parsed.get("volatility") or [])[:5],
        "anomalies": list(parsed.get("anomalies") or [])[:5],
        "opportunities": list(parsed.get("opportunities") or [])[:5],
        "reasoning": "API 模式：DeepSeek 基于异常检测上下文生成洞察。",
        "mode": "api",
    }


async def generate_insights(
    year: int,
    month: int,
    mode: str = "local",
    extra_data: str | None = None,
) -> dict[str, Any]:
    """生成洞察结论与原始上下文。"""
    context = fetch_insight_context(year, month)
    anomalies = detect_anomalies(context)

    cfg = load_llm_config()
    use_api = mode == "api" and bool(cfg.get("api_enabled")) and bool(cfg.get("api", {}).get("api_key"))

    if use_api:
        try:
            insights = await _api_insights(context, anomalies, extra_data, cfg)
        except Exception as exc:
            local = _local_insights(context, anomalies)
            local["reasoning"] = f"API 调用失败（{exc}），已回退本地规则。"
            insights = local
    else:
        insights = _local_insights(context, anomalies)
        if extra_data:
            insights["reasoning"] += " 用户补充数据已记录，本地模式未做 LLM 解读。"

    return {
        "context": context,
        "anomalies": anomalies,
        "insights": insights,
    }
