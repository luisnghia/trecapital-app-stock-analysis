from __future__ import annotations

POSTGRES_SCHEMA_SQL = r'''
CREATE TABLE IF NOT EXISTS checklist_company_refs(
    id BIGSERIAL PRIMARY KEY,
    host_company_key TEXT NOT NULL UNIQUE,
    ticker TEXT NOT NULL,
    exchange TEXT NOT NULL DEFAULT 'UNKNOWN',
    company_name TEXT NOT NULL,
    industry_name TEXT,
    company_type TEXT NOT NULL DEFAULT 'normal',
    currency TEXT NOT NULL DEFAULT 'VND',
    is_active INTEGER NOT NULL DEFAULT 1,
    host_metadata_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text
);
CREATE INDEX IF NOT EXISTS ix_checklist_company_ticker ON checklist_company_refs(ticker,exchange);

CREATE TABLE IF NOT EXISTS checklist_questions(
    question_id TEXT PRIMARY KEY,
    question_no INTEGER NOT NULL UNIQUE CHECK(question_no BETWEEN 1 AND 59),
    group_name TEXT NOT NULL,
    question_vi TEXT NOT NULL,
    guidance TEXT NOT NULL,
    research_mode TEXT NOT NULL CHECK(research_mode IN('manual','hybrid')),
    supporting_tool TEXT,
    source_basis TEXT NOT NULL DEFAULT 'Michael Shearn - The Investment Checklist',
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS screening_criteria(
    criterion_code TEXT PRIMARY KEY,
    criterion_name_en TEXT NOT NULL,
    criterion_name_vi TEXT NOT NULL,
    display_order INTEGER NOT NULL UNIQUE,
    source_basis TEXT NOT NULL DEFAULT 'The Investment Checklist - Table 1.1'
);

CREATE TABLE IF NOT EXISTS research_reviews(
    id BIGSERIAL PRIMARY KEY,
    company_ref_id BIGINT NOT NULL REFERENCES checklist_company_refs(id),
    review_type TEXT NOT NULL DEFAULT 'full' CHECK(review_type IN('full','delta','screening')),
    as_of_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'in_progress' CHECK(status IN('draft','in_progress','completed','archived')),
    prior_review_id BIGINT REFERENCES research_reviews(id),
    analyst_user_id TEXT,
    review_reason TEXT,
    finalize_reason TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text
);
ALTER TABLE research_reviews ADD COLUMN IF NOT EXISTS review_reason TEXT;
ALTER TABLE research_reviews ADD COLUMN IF NOT EXISTS finalize_reason TEXT;
CREATE INDEX IF NOT EXISTS ix_reviews_company_date ON research_reviews(company_ref_id,as_of_date DESC,id DESC);

CREATE TABLE IF NOT EXISTS analyst_assessments(
    id BIGSERIAL PRIMARY KEY,
    company_ref_id BIGINT NOT NULL REFERENCES checklist_company_refs(id),
    review_id BIGINT NOT NULL REFERENCES research_reviews(id),
    question_id TEXT NOT NULL REFERENCES checklist_questions(question_id),
    version_no INTEGER NOT NULL,
    analyst_answer TEXT,
    assessment INTEGER CHECK(assessment BETWEEN -2 AND 2),
    confidence INTEGER CHECK(confidence BETWEEN 1 AND 5),
    materiality INTEGER CHECK(materiality BETWEEN 1 AND 5),
    status TEXT NOT NULL CHECK(status IN('answered','research_gap','needs_review','na','not_reviewed')),
    change_reason TEXT,
    analyst_confirmed INTEGER NOT NULL DEFAULT 0,
    copied_from_assessment_id BIGINT REFERENCES analyst_assessments(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    UNIQUE(review_id,question_id,version_no)
);

CREATE TABLE IF NOT EXISTS screening_assessments(
    id BIGSERIAL PRIMARY KEY,
    company_ref_id BIGINT NOT NULL REFERENCES checklist_company_refs(id),
    review_id BIGINT NOT NULL REFERENCES research_reviews(id),
    criterion_code TEXT NOT NULL REFERENCES screening_criteria(criterion_code),
    version_no INTEGER NOT NULL,
    analyst_value TEXT NOT NULL CHECK(analyst_value IN('yes','no','unknown','na')),
    confidence INTEGER CHECK(confidence BETWEEN 1 AND 5),
    note TEXT,
    copied_from_screening_id BIGINT REFERENCES screening_assessments(id),
    analyst_confirmed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    UNIQUE(review_id,criterion_code,version_no)
);

CREATE TABLE IF NOT EXISTS opportunity_inventory_snapshots(
    id BIGSERIAL PRIMARY KEY,
    company_ref_id BIGINT NOT NULL REFERENCES checklist_company_refs(id),
    as_of_date TEXT NOT NULL,
    version_no INTEGER NOT NULL,
    data_origin TEXT NOT NULL DEFAULT 'manual' CHECK(data_origin IN('manual','host_data_layer','mixed')),
    source_as_of_date TEXT,
    tev DOUBLE PRECISION,
    ebit DOUBLE PRECISION,
    ebitda DOUBLE PRECISION,
    normalized_earnings DOUBLE PRECISION,
    total_debt DOUBLE PRECISION,
    interest_expense DOUBLE PRECISION,
    fcf_current DOUBLE PRECISION,
    market_cap DOUBLE PRECISION,
    dividend_per_share DOUBLE PRECISION,
    market_price DOUBLE PRECISION,
    fcf_estimate DOUBLE PRECISION,
    target_price DOUBLE PRECISION,
    ccc_days DOUBLE PRECISION,
    tev_ebit DOUBLE PRECISION,
    tev_ebitda DOUBLE PRECISION,
    tev_normalized_earnings DOUBLE PRECISION,
    pretax_earnings_yield DOUBLE PRECISION,
    debt_ebitda DOUBLE PRECISION,
    ebit_interest DOUBLE PRECISION,
    fcf_yield_ev DOUBLE PRECISION,
    fcf_yield_market DOUBLE PRECISION,
    dividend_yield DOUBLE PRECISION,
    price_vs_target DOUBLE PRECISION,
    quality_tally INTEGER,
    checklist_answered INTEGER,
    research_completion DOUBLE PRECISION,
    critical_unknowns INTEGER,
    red_flags INTEGER,
    mos DOUBLE PRECISION,
    thesis_direction TEXT CHECK(thesis_direction IN('up','flat','down','unknown')),
    last_review_id BIGINT REFERENCES research_reviews(id),
    note TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    UNIQUE(company_ref_id,as_of_date,version_no)
);
ALTER TABLE opportunity_inventory_snapshots ADD COLUMN IF NOT EXISTS ccc_days DOUBLE PRECISION;

CREATE TABLE IF NOT EXISTS data_snapshots(
    id BIGSERIAL PRIMARY KEY,
    company_ref_id BIGINT NOT NULL REFERENCES checklist_company_refs(id),
    review_id BIGINT REFERENCES research_reviews(id),
    as_of_date TEXT NOT NULL,
    snapshot_type TEXT NOT NULL CHECK(snapshot_type IN('review','manual_backup')),
    snapshot_version INTEGER NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    UNIQUE(review_id,snapshot_type,snapshot_version)
);

CREATE TABLE IF NOT EXISTS audit_logs(
    id BIGSERIAL PRIMARY KEY,
    company_ref_id BIGINT REFERENCES checklist_company_refs(id),
    review_id BIGINT REFERENCES research_reviews(id),
    actor TEXT,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    before_json TEXT,
    after_json TEXT,
    correlation_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text
);

CREATE TABLE IF NOT EXISTS integration_sync_log(
    id BIGSERIAL PRIMARY KEY,
    company_ref_id BIGINT REFERENCES checklist_company_refs(id),
    source_module TEXT NOT NULL,
    source_as_of_date TEXT,
    payload_hash TEXT,
    status TEXT NOT NULL CHECK(status IN('success','partial','failed','skipped')),
    detail TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text
);

CREATE TABLE IF NOT EXISTS persistence_probes(
    probe_key TEXT PRIMARY KEY,
    deployment_marker TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    verified_at TEXT
);
'''
