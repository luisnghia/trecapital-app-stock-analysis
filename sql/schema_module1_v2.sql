CREATE TABLE IF NOT EXISTS stocks (
    ticker TEXT PRIMARY KEY,
    company_name TEXT,
    exchange TEXT,
    industry TEXT,
    sub_industry TEXT,
    source TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS company_overview (
    ticker TEXT PRIMARY KEY,
    market_cap_bil REAL,
    shares_outstanding_mil REAL,
    current_price REAL,
    eps REAL,
    pe REAL,
    pb REAL,
    ps REAL,
    roe REAL,
    roa REAL,
    roic REAL,
    updated_at TEXT,
    source TEXT
);

CREATE TABLE IF NOT EXISTS financial_timeseries (
    ticker TEXT,
    period_type TEXT CHECK(period_type IN ('Y','Q','TTM')),
    period TEXT,
    year INTEGER,
    quarter INTEGER,
    revenue_bil REAL,
    gross_revenue_bil REAL,
    gross_profit_bil REAL,
    net_profit_bil REAL,
    pretax_profit_bil REAL,
    cfo_bil REAL,
    cfi_bil REAL,
    cff_bil REAL,
    capex_bil REAL,
    cash_dividend_bil REAL,
    free_cash_flow_bil REAL,
    owner_earnings_bil REAL,
    eps_vnd REAL,
    oeps_vnd REAL,
    roe_pct REAL,
    roa_pct REAL,
    roic_pct REAL,
    gross_margin_pct REAL,
    net_margin_pct REAL,
    asset_turnover REAL,
    equity_multiplier REAL,
    roe_dupont_pct REAL,
    total_assets_bil REAL,
    equity_bil REAL,
    cfo_to_net_profit REAL,
    fcf_to_net_profit REAL,
    source TEXT,
    updated_at TEXT,
    PRIMARY KEY (ticker, period_type, period)
);

CREATE TABLE IF NOT EXISTS raw_source_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT,
    source TEXT,
    raw_file TEXT,
    status TEXT,
    message TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
