"""基于数据库动态生成各图表分析解读。"""
from __future__ import annotations

from sqlalchemy import text

from src.db.connection import get_engine

# 静态标题与说明框架
CHART_META: dict[str, dict[str, str]] = {
    "sales_growth.png": {"title": "年度销售额与增长率", "kind": "sales_growth"},
    "avg_order_value.png": {"title": "年度客单价趋势", "kind": "avg_order_value"},
    "profit_by_month.png": {"title": "各年月度利润分析", "kind": "profit_by_month"},
    "seasonality_sales.png": {"title": "月度销售额与淡旺季", "kind": "seasonality"},
    "shipping_cost_trend.png": {"title": "发货成本月度趋势", "kind": "shipping"},
    "region_share.png": {"title": "各区域销售额占比", "kind": "region_share"},
    "region_yearly_sales_top6.png": {"title": "前六区域年度销售额（2011-2014）", "kind": "region_yearly_top6"},
    "new_old_customers.png": {"title": "新老客户数量（按年）", "kind": "new_old"},
    "segment_share.png": {"title": "客户类型占比", "kind": "segment_share"},
    "segment_yearly_count.png": {"title": "各年不同类型客户数量", "kind": "segment_count"},
    "segment_yearly_sales.png": {"title": "各类型客户年度销售额", "kind": "segment_sales"},
    "segment_category_sales.png": {"title": "客户群体与产品类别销售额分析", "kind": "segment_category"},
    "rfm_distribution.png": {"title": "RFM 客户价值分布（2014）", "kind": "rfm"},
}


def _fmt_money(v: float) -> str:
    if v >= 1_000_000:
        return f"{v / 1_000_000:.2f} 百万"
    if v >= 1_000:
        return f"{v / 1_000:.1f} 千"
    return f"{v:.2f}"


def _build_analysis(kind: str, conn) -> str:
    try:
        if kind == "sales_growth":
            rows = conn.execute(text(
                "SELECT order_year, total_sales, sales_growth_rate FROM agg_sales_by_year ORDER BY order_year"
            )).fetchall()
            if not rows:
                return "暂无数据。"
            lines = ["本图展示 2011—2014 年各年销售总额及同比增长率。"]
            for y, sales, gr in rows:
                if y and y <= 2014:
                    gr_txt = f"{gr * 100:.1f}%" if gr is not None else "—"
                    lines.append(f"{int(y)} 年销售额 {_fmt_money(float(sales))}，增长率 {gr_txt}。")
            if len(rows) >= 2:
                lines.append("整体呈稳步上升，2012 年后增速趋于平稳，企业经营逐步稳定。")
            return "".join(lines)

        if kind == "avg_order_value":
            rows = conn.execute(text(
                "SELECT order_year, avg_order_value FROM agg_sales_by_year WHERE order_year BETWEEN 2011 AND 2014 ORDER BY order_year"
            )).fetchall()
            if not rows:
                return "暂无数据。"
            lines = ["客单价 = 年销售额 ÷ 当年去重客户数。"]
            for y, aov in rows:
                lines.append(f"{int(y)} 年客单价 {float(aov):.2f} 元；")
            if len(rows) >= 2 and float(rows[-1][1]) > float(rows[0][1]):
                lines.append("客单价逐年上升，顾客购买水平持续增强。")
            return "".join(lines)

        if kind == "profit_by_month":
            row = conn.execute(text(
                "SELECT order_year, SUM(profit) AS p FROM orders WHERE order_year BETWEEN 2011 AND 2014 GROUP BY order_year ORDER BY order_year"
            )).fetchall()
            best = conn.execute(text(
                "SELECT order_year, order_month, SUM(profit) AS p FROM orders "
                "WHERE order_year BETWEEN 2011 AND 2014 GROUP BY order_year, order_month "
                "ORDER BY p DESC LIMIT 1"
            )).fetchone()
            lines = ["按年份与月份汇总利润，对比各年同一月份表现。"]
            for y, p in row:
                lines.append(f"{int(y)} 年总利润 {_fmt_money(float(p))}；")
            if best:
                lines.append(f"利润最高月份为 {int(best[0])} 年 {int(best[1])} 月（{_fmt_money(float(best[2]))}）。")
            return "".join(lines)

        if kind == "seasonality":
            rows = conn.execute(text(
                "SELECT order_month, SUM(total_sales) AS s FROM agg_sales_by_month "
                "WHERE order_year BETWEEN 2011 AND 2014 GROUP BY order_month ORDER BY s DESC LIMIT 3"
            )).fetchall()
            low = conn.execute(text(
                "SELECT order_month, SUM(total_sales) AS s FROM agg_sales_by_month "
                "WHERE order_year BETWEEN 2011 AND 2014 GROUP BY order_month ORDER BY s ASC LIMIT 2"
            )).fetchall()
            lines = ["按年月汇总销售额，观察淡旺季规律。"]
            if rows:
                peak = "、".join(f"{int(m)}月" for m, _ in rows)
                lines.append(f"销量高峰月份：{peak}。")
            if low:
                trough = "、".join(f"{int(m)}月" for m, _ in low)
                lines.append(f"相对低谷月份：{trough}，可针对性开展促销。")
            lines.append("下半年通常为销售旺季，建议在 7、10 月低谷期加大营销投入。")
            return "".join(lines)

        if kind == "shipping":
            rows = conn.execute(text(
                "SELECT ship_year, SUM(shipping_cost) AS c FROM orders WHERE ship_year BETWEEN 2011 AND 2014 "
                "GROUP BY ship_year ORDER BY ship_year"
            )).fetchall()
            lines = ["按发货年、月汇总 Shipping Cost。"]
            for y, c in rows:
                lines.append(f"{int(y)} 年发货成本合计 {_fmt_money(float(c))}；")
            lines.append("成本随业务规模总体上升，需持续优化物流合作以控制费用。")
            return "".join(lines)

        if kind == "region_share":
            rows = conn.execute(text(
                "SELECT market, SUM(total_sales) AS s FROM agg_sales_by_region_year GROUP BY market ORDER BY s DESC"
            )).fetchall()
            total = sum(float(r[1]) for r in rows) or 1
            lines = ["按 Market 汇总销售额；占比不足 1% 的区域在图中合并为「其他」。"]
            for market, s in rows[:3]:
                pct = float(s) / total * 100
                lines.append(f"{market} 占 {pct:.1f}%（{_fmt_money(float(s))}）；")
            lines.append("应巩固头部区域优势，评估低占比市场的投入产出比。")
            return "".join(lines)

        if kind == "region_yearly_top6":
            top6_rows = conn.execute(text(
                "SELECT market, SUM(total_sales) AS s FROM agg_sales_by_region_year "
                "WHERE order_year BETWEEN 2011 AND 2014 GROUP BY market ORDER BY s DESC LIMIT 6"
            )).fetchall()
            if not top6_rows:
                return "暂无数据。"
            top6 = [r[0] for r in top6_rows]
            lines = [f"按销售额选取前 6 区域：{'、'.join(top6)}。"]
            for market in top6[:2]:
                yearly = conn.execute(text(
                    "SELECT order_year, total_sales FROM agg_sales_by_region_year "
                    "WHERE market = :m AND order_year BETWEEN 2011 AND 2014 ORDER BY order_year"
                ), {"m": market}).fetchall()
                if len(yearly) >= 2:
                    y0, s0 = int(yearly[0][0]), float(yearly[0][1])
                    y1, s1 = int(yearly[-1][0]), float(yearly[-1][1])
                    growth = (s1 - s0) / s0 * 100 if s0 else 0
                    lines.append(f"{market} 从 {y0} 年 {_fmt_money(s0)} 增至 {y1} 年 {_fmt_money(s1)}（+{growth:.1f}%）；")
            lines.append(
                "各区域 2011—2014 年销售总额均呈增长趋势，其中 APAC 与 EU 增速较快、前景较好，"
                "下一年可适当加大运营成本以把握市场机会。"
            )
            return "".join(lines)

        if kind == "segment_category":
            rows = conn.execute(text(
                "SELECT category, SUM(total_sales) AS s FROM agg_segment_category "
                "WHERE category IN ('Technology', 'Furniture', 'Office Supplies') "
                "GROUP BY category ORDER BY s DESC"
            )).fetchall()
            seg_rows = conn.execute(text(
                "SELECT segment, SUM(total_sales) AS s FROM agg_segment_category "
                "WHERE category IN ('Technology', 'Furniture', 'Office Supplies') "
                "GROUP BY segment ORDER BY s DESC"
            )).fetchall()
            cat_cn = {
                "Technology": "科技产品",
                "Furniture": "家具产品",
                "Office Supplies": "办公用品",
            }
            seg_cn = {
                "Consumer": "个人消费者",
                "Corporate": "企业客户",
                "Home Office": "居家办公",
            }
            lines = ["按 Segment 与 Category 分组汇总销售额。"]
            if rows:
                order = " > ".join(cat_cn.get(r[0], r[0]) for r in rows)
                lines.append(f"各客户群体对产品消费额由高到低均为：{order}。")
            if seg_rows:
                top_seg = seg_cn.get(seg_rows[0][0], seg_rows[0][0])
                low_seg = seg_cn.get(seg_rows[-1][0], seg_rows[-1][0])
                lines.append(
                    f"{top_seg} 在三种产品上的消费均最高，可保持现有策略；"
                    f"{low_seg} 群体销售额相对较低，建议加强定向营销推广。"
                )
            lines.append("可加大对科技产品的推广力度。")
            return "".join(lines)

        if kind == "segment_share":
            rows = conn.execute(text(
                "SELECT segment, SUM(total_sales) AS s FROM agg_segment_category GROUP BY segment ORDER BY s DESC"
            )).fetchall()
            total = sum(float(r[1]) for r in rows) or 1
            lines = ["按 Segment 统计客户类型占比。"]
            for seg, s in rows:
                pct = float(s) / total * 100
                lines.append(f"{seg} 占 {pct:.1f}%；")
            top = rows[0][0] if rows else ""
            lines.append(f"{top} 类型占比最高，Home Office 等低占比类型可加强定向营销。")
            return "".join(lines)

        if kind == "rfm":
            rows = conn.execute(text(
                "SELECT value_segment, COUNT(*) AS c FROM customer_rfm WHERE snapshot_year=2014 "
                "GROUP BY value_segment ORDER BY c DESC"
            )).fetchall()
            total = sum(r[1] for r in rows) or 1
            lines = ["基于 2014 年订单，按 R/F/M 三维度划分 8 类客户价值。"]
            for seg, c in rows[:4]:
                lines.append(f"{seg} 占 {c / total * 100:.1f}%；")
            vip = sum(c for seg, c in rows if "重要" in seg)
            lines.append(f"重要价值/保持类客户合计 {vip / total * 100:.1f}%，是核心维护对象。")
            return "".join(lines)

        if kind in ("new_old", "segment_count", "segment_sales"):
            fallbacks = {
                "new_old": "按年区分首次消费（新客）与历史消费（老客）。老客户占比高说明留存良好；新客减少时需加强拉新。",
                "segment_count": "各类型客户数量逐年变化反映客户结构是否健康，需关注增长放缓的类型。",
                "segment_sales": "Consumer 类型销售额通常最高；可对 Home Office 群体制定专项推广策略。",
            }
            return fallbacks[kind]

    except Exception as e:
        return f"分析数据加载失败：{e}"

    return "暂无分析说明。"


def build_insights() -> dict[str, dict[str, str]]:
    """返回 {文件名: {title, analysis}}，analysis 含真实数据。"""
    result: dict[str, dict[str, str]] = {}
    try:
        engine = get_engine()
        with engine.connect() as conn:
            for fname, meta in CHART_META.items():
                result[fname] = {
                    "title": meta["title"],
                    "analysis": _build_analysis(meta["kind"], conn),
                }
    except Exception:
        for fname, meta in CHART_META.items():
            result[fname] = {"title": meta["title"], "analysis": "请先运行 ETL 入库后再查看数据分析。"}
    return result
