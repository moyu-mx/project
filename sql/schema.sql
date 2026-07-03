-- 超市电商分析数据库 Schema (SQLite)

CREATE TABLE IF NOT EXISTS customers (
    customer_id   TEXT PRIMARY KEY,
    customer_name TEXT NOT NULL,
    segment       TEXT NOT NULL,
    city          TEXT,
    state         TEXT,
    country       TEXT
);

CREATE TABLE IF NOT EXISTS products (
    product_id    TEXT PRIMARY KEY,
    product_name  TEXT NOT NULL,
    category      TEXT NOT NULL,
    sub_category  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS regions (
    market  TEXT PRIMARY KEY,
    region  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    row_id          INTEGER PRIMARY KEY,
    order_id        TEXT NOT NULL,
    order_date      TEXT NOT NULL,
    ship_date       TEXT NOT NULL,
    ship_mode       TEXT,
    customer_id     TEXT NOT NULL,
    product_id      TEXT NOT NULL,
    market          TEXT NOT NULL,
    sales           REAL NOT NULL DEFAULT 0,
    quantity        INTEGER NOT NULL DEFAULT 0,
    discount        REAL NOT NULL DEFAULT 0,
    profit          REAL NOT NULL DEFAULT 0,
    shipping_cost   REAL NOT NULL DEFAULT 0,
    order_priority  TEXT,
    order_year      INTEGER NOT NULL,
    order_month     INTEGER NOT NULL,
    order_quarter   INTEGER NOT NULL,
    ship_year       INTEGER,
    ship_month      INTEGER,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (product_id)  REFERENCES products(product_id),
    FOREIGN KEY (market)      REFERENCES regions(market)
);

CREATE INDEX IF NOT EXISTS idx_orders_order_year ON orders(order_year);
CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_market ON orders(market);

CREATE TABLE IF NOT EXISTS agg_sales_by_year (
    order_year        INTEGER PRIMARY KEY,
    total_sales       REAL NOT NULL,
    total_profit      REAL NOT NULL,
    total_quantity    INTEGER NOT NULL,
    customer_count    INTEGER NOT NULL,
    avg_order_value   REAL NOT NULL,
    sales_growth_rate REAL
);

CREATE TABLE IF NOT EXISTS agg_sales_by_region_year (
    market       TEXT NOT NULL,
    order_year   INTEGER NOT NULL,
    total_sales  REAL NOT NULL,
    total_profit REAL NOT NULL,
    PRIMARY KEY (market, order_year)
);

CREATE TABLE IF NOT EXISTS agg_sales_by_month (
    order_year     INTEGER NOT NULL,
    order_month    INTEGER NOT NULL,
    total_sales    REAL NOT NULL,
    total_quantity INTEGER NOT NULL,
    total_profit   REAL NOT NULL,
    PRIMARY KEY (order_year, order_month)
);

CREATE TABLE IF NOT EXISTS customer_rfm (
    snapshot_year INTEGER NOT NULL,
    customer_id   TEXT NOT NULL,
    recency_days  INTEGER NOT NULL,
    frequency     INTEGER NOT NULL,
    monetary      REAL NOT NULL,
    r_score       INTEGER NOT NULL,
    f_score       INTEGER NOT NULL,
    m_score       INTEGER NOT NULL,
    value_segment TEXT NOT NULL,
    PRIMARY KEY (snapshot_year, customer_id),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE IF NOT EXISTS agg_segment_category (
    segment     TEXT NOT NULL,
    category    TEXT NOT NULL,
    total_sales REAL NOT NULL,
    PRIMARY KEY (segment, category)
);
