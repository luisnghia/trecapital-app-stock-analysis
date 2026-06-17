-- Schema đề xuất cho Module 1: Tổng quan doanh nghiệp
-- Đơn vị khuyến nghị:
-- market_cap_bil: tỷ đồng
-- shares_outstanding_mil: triệu cổ phiếu
-- current_price, eps: đồng/cổ phiếu
-- pe, pb, ps: lần
-- roe, roa, roic: %

CREATE TABLE IF NOT EXISTS company_overview (
    ticker TEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    exchange TEXT,
    industry TEXT,
    sub_industry TEXT,
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
    source TEXT,
    raw_payload TEXT
);

CREATE INDEX IF NOT EXISTS idx_company_overview_industry
ON company_overview(industry, sub_industry);
