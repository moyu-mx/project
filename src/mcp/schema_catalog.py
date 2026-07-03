"""超市电商 SQLite 库表结构与字段语义 catalog。"""
from __future__ import annotations

DATABASE_NAME = "superstore_analytics"

TABLES: dict[str, dict] = {
    "orders": {
        "label": "订单明细事实表",
        "description": "每一行是一笔订单中的单个商品明细，NL2SQL 最常用的核心表。",
        "primary_key": "row_id",
        "foreign_keys": {
            "customer_id": "customers.customer_id",
            "product_id": "products.product_id",
            "market": "regions.market",
        },
    },
    "customers": {
        "label": "客户维度表",
        "description": "客户基本信息，通过 customer_id 与 orders 关联。",
        "primary_key": "customer_id",
    },
    "products": {
        "label": "产品维度表",
        "description": "商品信息，通过 product_id 与 orders 关联。",
        "primary_key": "product_id",
    },
    "regions": {
        "label": "区域维度表",
        "description": "商店所属区域，market 为主键，与 orders.market 关联。",
        "primary_key": "market",
    },
    "agg_sales_by_year": {
        "label": "年度销售汇总表",
        "description": "按年预聚合的销售额、利润、客单价、增长率，适合年度趋势类问题。",
        "primary_key": "order_year",
    },
    "agg_sales_by_region_year": {
        "label": "区域年度销售汇总表",
        "description": "各 market 在各年的销售额与利润汇总。",
        "primary_key": "(market, order_year)",
    },
    "agg_sales_by_month": {
        "label": "月度销售汇总表",
        "description": "按年月的销量与销售额，适合淡旺季分析。",
        "primary_key": "(order_year, order_month)",
    },
    "customer_rfm": {
        "label": "RFM 客户价值表",
        "description": "按年快照的客户 R/F/M 评分及 8 类价值标签，如「重要价值客户」。",
        "primary_key": "(snapshot_year, customer_id)",
    },
    "agg_segment_category": {
        "label": "客户类型×品类销售汇总",
        "description": "Segment 与 Category 交叉的销售额汇总。",
        "primary_key": "(segment, category)",
    },
}

FIELDS: dict[str, dict[str, dict]] = {
    "orders": {
        "row_id": {"type": "INTEGER", "label": "行编号", "meaning": "订单明细唯一主键"},
        "order_id": {"type": "TEXT", "label": "订单ID", "meaning": "同一订单可有多行明细", "example": "IN-2013-47883"},
        "order_date": {"type": "DATE", "label": "订单日期", "meaning": "下单日期，格式 YYYY-MM-DD"},
        "ship_date": {"type": "DATE", "label": "发货日期", "meaning": "商品发货日期"},
        "ship_mode": {"type": "TEXT", "label": "发货模式", "meaning": "物流等级", "example": "Standard Class"},
        "customer_id": {"type": "TEXT", "label": "客户ID", "meaning": "外键，关联 customers 表"},
        "product_id": {"type": "TEXT", "label": "产品ID", "meaning": "外键，关联 products 表"},
        "market": {"type": "TEXT", "label": "商店区域", "meaning": "业务区域，非 country", "example": "APAC, EU, US"},
        "sales": {"type": "REAL", "label": "销售额", "meaning": "该明细行的销售金额"},
        "quantity": {"type": "INTEGER", "label": "销售量", "meaning": "购买数量"},
        "discount": {"type": "REAL", "label": "折扣", "meaning": "0~1 之间"},
        "profit": {"type": "REAL", "label": "利润", "meaning": "该明细行利润，可为负"},
        "shipping_cost": {"type": "REAL", "label": "发货成本", "meaning": "物流费用"},
        "order_priority": {"type": "TEXT", "label": "订单优先级", "example": "High, Medium"},
        "order_year": {"type": "INTEGER", "label": "订单年份", "meaning": "按年过滤首选", "example": "2011-2014"},
        "order_month": {"type": "INTEGER", "label": "订单月份", "meaning": "1-12"},
        "order_quarter": {"type": "INTEGER", "label": "订单季度", "meaning": "1-4"},
        "ship_year": {"type": "INTEGER", "label": "发货年份", "meaning": "从 ship_date 派生"},
        "ship_month": {"type": "INTEGER", "label": "发货月份", "meaning": "从 ship_date 派生"},
    },
    "customers": {
        "customer_id": {"type": "TEXT", "label": "客户ID", "meaning": "主键"},
        "customer_name": {"type": "TEXT", "label": "客户姓名", "meaning": "客户名称"},
        "segment": {"type": "TEXT", "label": "客户类别", "meaning": "客户类型", "example": "Consumer, Corporate, Home Office"},
        "city": {"type": "TEXT", "label": "城市", "meaning": "客户所在城市"},
        "state": {"type": "TEXT", "label": "州/省", "meaning": "客户所在州或省"},
        "country": {"type": "TEXT", "label": "国家", "meaning": "客户国家，区别于 orders.market"},
    },
    "products": {
        "product_id": {"type": "TEXT", "label": "产品ID", "meaning": "主键"},
        "product_name": {"type": "TEXT", "label": "产品名称", "meaning": "商品全称"},
        "category": {"type": "TEXT", "label": "产品大类", "example": "Technology, Furniture, Office Supplies"},
        "sub_category": {"type": "TEXT", "label": "产品子类", "meaning": "细分类别"},
    },
    "regions": {
        "market": {"type": "TEXT", "label": "商店区域", "meaning": "主键，业务分区", "example": "APAC, EU, US"},
        "region": {"type": "TEXT", "label": "所属大区", "meaning": "更高层地理分区", "example": "Oceania, North"},
    },
    "agg_sales_by_year": {
        "order_year": {"type": "INTEGER", "label": "年份", "meaning": "主键"},
        "total_sales": {"type": "REAL", "label": "年度总销售额", "meaning": "该年 sales 合计"},
        "total_profit": {"type": "REAL", "label": "年度总利润", "meaning": "该年 profit 合计"},
        "total_quantity": {"type": "INTEGER", "label": "年度总销量", "meaning": "该年 quantity 合计"},
        "customer_count": {"type": "INTEGER", "label": "成交客户数", "meaning": "该年去重 customer 数"},
        "avg_order_value": {"type": "REAL", "label": "客单价", "meaning": "total_sales / customer_count"},
        "sales_growth_rate": {"type": "REAL", "label": "销售额同比增长率", "meaning": "相对上年的增长率"},
    },
    "agg_sales_by_region_year": {
        "market": {"type": "TEXT", "label": "商店区域", "meaning": "业务区域"},
        "order_year": {"type": "INTEGER", "label": "年份", "meaning": "订单年份"},
        "total_sales": {"type": "REAL", "label": "区域年度销售额", "meaning": "该区域该年 sales 合计"},
        "total_profit": {"type": "REAL", "label": "区域年度利润", "meaning": "该区域该年 profit 合计"},
    },
    "agg_sales_by_month": {
        "order_year": {"type": "INTEGER", "label": "年份", "meaning": "订单年份"},
        "order_month": {"type": "INTEGER", "label": "月份", "meaning": "1-12"},
        "total_sales": {"type": "REAL", "label": "月度销售额", "meaning": "该月 sales 合计"},
        "total_quantity": {"type": "INTEGER", "label": "月度销量", "meaning": "该月 quantity 合计"},
        "total_profit": {"type": "REAL", "label": "月度利润", "meaning": "该月 profit 合计"},
    },
    "customer_rfm": {
        "snapshot_year": {"type": "INTEGER", "label": "快照年份", "meaning": "RFM 基准年，如 2014"},
        "customer_id": {"type": "TEXT", "label": "客户ID", "meaning": "外键"},
        "recency_days": {"type": "INTEGER", "label": "R-最近消费间隔", "meaning": "距参考日天数"},
        "frequency": {"type": "INTEGER", "label": "F-消费频次", "meaning": "该年订单条数"},
        "monetary": {"type": "REAL", "label": "M-消费金额", "meaning": "该年 sales 合计"},
        "r_score": {"type": "INTEGER", "label": "R评分", "meaning": "0或1"},
        "f_score": {"type": "INTEGER", "label": "F评分", "meaning": "0或1"},
        "m_score": {"type": "INTEGER", "label": "M评分", "meaning": "0或1"},
        "value_segment": {"type": "TEXT", "label": "客户价值类型", "example": "重要价值客户"},
    },
    "agg_segment_category": {
        "segment": {"type": "TEXT", "label": "客户类别", "example": "Consumer, Corporate"},
        "category": {"type": "TEXT", "label": "产品大类", "example": "Technology, Furniture"},
        "total_sales": {"type": "REAL", "label": "销售额", "meaning": "segment×category 的 sales 合计"},
    },
}

BUSINESS_RULES = [
    "仅生成 SQLite SELECT 语句，禁止 INSERT/UPDATE/DELETE/DROP。",
    "区域/分店用 orders.market，不要用 country 代替 market。",
    "客户类型用 customers.segment，产品大类用 products.category。",
    "按年过滤优先用 order_year，按年月用 order_year + order_month。",
    "客单价可用 agg_sales_by_year.avg_order_value 或 SUM(sales)/COUNT(DISTINCT customer_id)。",
    "RFM 分析用 customer_rfm，snapshot_year 通常为 2014。",
    "多表：orders JOIN customers/products/regions 见 JOIN 提示。",
    "默认加 LIMIT 100。",
]

JOIN_HINTS = (
    "orders o JOIN customers c ON o.customer_id = c.customer_id; "
    "orders o JOIN products p ON o.product_id = p.product_id; "
    "orders o JOIN regions r ON o.market = r.market"
)


def format_schema_markdown(table: str | None = None) -> str:
    lines = [f"# 数据库：{DATABASE_NAME}\n"]
    names = [table] if table else list(TABLES.keys())
    for t in names:
        if t not in TABLES:
            continue
        meta = TABLES[t]
        lines.append(f"## `{t}` — {meta['label']}")
        lines.append(meta["description"])
        lines.append("| 字段 | 类型 | 中文 | 含义 | 示例 |")
        lines.append("|------|------|------|------|------|")
        for fname, finfo in FIELDS.get(t, {}).items():
            lines.append(
                f"| {fname} | {finfo['type']} | {finfo['label']} | {finfo.get('meaning','')} | {finfo.get('example','')} |"
            )
        lines.append("")
    lines.append("## 业务规则\n" + "\n".join(f"- {r}" for r in BUSINESS_RULES))
    lines.append(f"\nJOIN: {JOIN_HINTS}")
    return "\n".join(lines)


def list_tables() -> list[dict]:
    return [{"name": k, "label": v["label"], "description": v["description"]} for k, v in TABLES.items()]
