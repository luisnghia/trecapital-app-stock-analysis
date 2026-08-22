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

CREATE TABLE IF NOT EXISTS research_sources(
    id BIGSERIAL PRIMARY KEY,
    company_ref_id BIGINT NOT NULL REFERENCES checklist_company_refs(id),
    source_type TEXT NOT NULL CHECK(source_type IN('annual_report','quarterly_report','filing','investor_presentation','earnings_call','company_website','regulator','industry_report','news','interview','customer_supplier_employee','analyst_upload','other')),
    title TEXT NOT NULL,
    publisher TEXT,
    url TEXT,
    document_date TEXT,
    accessed_at TEXT,
    reliability INTEGER NOT NULL CHECK(reliability BETWEEN 1 AND 5),
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN('active','archived')),
    notes TEXT,
    source_hash TEXT NOT NULL,
    created_by TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    UNIQUE(company_ref_id,source_hash)
);
CREATE INDEX IF NOT EXISTS ix_research_sources_company_date ON research_sources(company_ref_id,document_date DESC,id DESC);

CREATE TABLE IF NOT EXISTS research_source_contents(
    id BIGSERIAL PRIMARY KEY,
    company_ref_id BIGINT NOT NULL REFERENCES checklist_company_refs(id),
    source_id BIGINT NOT NULL REFERENCES research_sources(id),
    version_no INTEGER NOT NULL,
    content_type TEXT NOT NULL,
    locator_scheme TEXT NOT NULL,
    original_filename TEXT,
    scope_label TEXT,
    content_text TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    char_count INTEGER NOT NULL CHECK(char_count>0),
    created_by TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    UNIQUE(source_id,version_no),
    UNIQUE(source_id,content_hash)
);
CREATE INDEX IF NOT EXISTS ix_source_contents_source_version ON research_source_contents(source_id,version_no DESC,id DESC);
CREATE INDEX IF NOT EXISTS ix_source_contents_company ON research_source_contents(company_ref_id,id DESC);

CREATE TABLE IF NOT EXISTS research_evidence(
    id BIGSERIAL PRIMARY KEY,
    company_ref_id BIGINT NOT NULL REFERENCES checklist_company_refs(id),
    source_id BIGINT NOT NULL REFERENCES research_sources(id),
    evidence_key TEXT NOT NULL,
    version_no INTEGER NOT NULL,
    evidence_type TEXT NOT NULL CHECK(evidence_type IN('fact','quote','metric','observation','contradiction','risk')),
    locator_text TEXT,
    excerpt TEXT NOT NULL,
    analyst_note TEXT,
    evidence_date TEXT,
    verification_status TEXT NOT NULL DEFAULT 'unverified' CHECK(verification_status IN('unverified','verified','disputed','stale')),
    direction TEXT NOT NULL DEFAULT 'context' CHECK(direction IN('supports','contradicts','context')),
    confidence INTEGER NOT NULL CHECK(confidence BETWEEN 1 AND 5),
    change_reason TEXT,
    supersedes_evidence_id BIGINT REFERENCES research_evidence(id),
    content_hash TEXT NOT NULL,
    created_by TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    UNIQUE(source_id,evidence_key,version_no)
);
CREATE INDEX IF NOT EXISTS ix_research_evidence_source_key ON research_evidence(source_id,evidence_key,version_no DESC);
CREATE INDEX IF NOT EXISTS ix_research_evidence_company_date ON research_evidence(company_ref_id,evidence_date DESC,id DESC);

CREATE TABLE IF NOT EXISTS evidence_question_links(
    id BIGSERIAL PRIMARY KEY,
    company_ref_id BIGINT NOT NULL REFERENCES checklist_company_refs(id),
    review_id BIGINT NOT NULL REFERENCES research_reviews(id),
    question_id TEXT NOT NULL REFERENCES checklist_questions(question_id),
    evidence_id BIGINT NOT NULL REFERENCES research_evidence(id),
    relationship TEXT NOT NULL CHECK(relationship IN('primary','supporting','context','contradicts')),
    materiality INTEGER NOT NULL CHECK(materiality BETWEEN 1 AND 5),
    link_note TEXT,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN(0,1)),
    deactivation_reason TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    deactivated_at TEXT,
    UNIQUE(review_id,question_id,evidence_id)
);
CREATE INDEX IF NOT EXISTS ix_evidence_links_review_question ON evidence_question_links(review_id,question_id,is_active);

CREATE TABLE IF NOT EXISTS ai_research_runs(
    id BIGSERIAL PRIMARY KEY,
    company_ref_id BIGINT NOT NULL REFERENCES checklist_company_refs(id),
    review_id BIGINT NOT NULL REFERENCES research_reviews(id),
    run_type TEXT NOT NULL CHECK(run_type IN('evidence_extraction','research_gap','contradiction_scan','delta_review')),
    status TEXT NOT NULL DEFAULT 'completed' CHECK(status IN('completed','failed')),
    provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    model_version TEXT,
    prompt_version TEXT NOT NULL,
    prompt_hash TEXT NOT NULL,
    source_manifest_json TEXT NOT NULL,
    source_manifest_hash TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    output_hash TEXT NOT NULL,
    provider_request_id TEXT,
    provider_response_id TEXT,
    client_request_id TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    total_tokens INTEGER,
    latency_ms INTEGER,
    attempt_count INTEGER,
    service_tier TEXT,
    requested_by TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    error_text TEXT
);
CREATE INDEX IF NOT EXISTS ix_ai_runs_review_created ON ai_research_runs(review_id,id DESC);
CREATE INDEX IF NOT EXISTS ix_ai_runs_company ON ai_research_runs(company_ref_id);
ALTER TABLE ai_research_runs ADD COLUMN IF NOT EXISTS provider_request_id TEXT;
ALTER TABLE ai_research_runs ADD COLUMN IF NOT EXISTS provider_response_id TEXT;
ALTER TABLE ai_research_runs ADD COLUMN IF NOT EXISTS client_request_id TEXT;
ALTER TABLE ai_research_runs ADD COLUMN IF NOT EXISTS input_tokens INTEGER;
ALTER TABLE ai_research_runs ADD COLUMN IF NOT EXISTS output_tokens INTEGER;
ALTER TABLE ai_research_runs ADD COLUMN IF NOT EXISTS total_tokens INTEGER;
ALTER TABLE ai_research_runs ADD COLUMN IF NOT EXISTS latency_ms INTEGER;
ALTER TABLE ai_research_runs ADD COLUMN IF NOT EXISTS attempt_count INTEGER;
ALTER TABLE ai_research_runs ADD COLUMN IF NOT EXISTS service_tier TEXT;

CREATE TABLE IF NOT EXISTS ai_research_suggestions(
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES ai_research_runs(id),
    company_ref_id BIGINT NOT NULL REFERENCES checklist_company_refs(id),
    review_id BIGINT NOT NULL REFERENCES research_reviews(id),
    suggestion_no INTEGER NOT NULL,
    suggestion_type TEXT NOT NULL CHECK(suggestion_type IN('evidence_candidate','contradiction','research_gap')),
    source_id BIGINT REFERENCES research_sources(id),
    source_hash_at_run TEXT,
    source_content_id BIGINT REFERENCES research_source_contents(id),
    source_content_hash_at_run TEXT,
    question_id TEXT NOT NULL REFERENCES checklist_questions(question_id),
    evidence_type TEXT CHECK(evidence_type IN('fact','quote','metric','observation','contradiction','risk')),
    relationship TEXT CHECK(relationship IN('primary','supporting','context','contradicts')),
    direction TEXT CHECK(direction IN('supports','contradicts','context')),
    locator_text TEXT,
    excerpt TEXT,
    rationale TEXT NOT NULL,
    confidence INTEGER NOT NULL CHECK(confidence BETWEEN 1 AND 5),
    materiality INTEGER NOT NULL CHECK(materiality BETWEEN 1 AND 5),
    payload_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    UNIQUE(run_id,suggestion_no)
);
CREATE INDEX IF NOT EXISTS ix_ai_suggestions_review_question ON ai_research_suggestions(review_id,question_id,id DESC);
CREATE INDEX IF NOT EXISTS ix_ai_suggestions_company ON ai_research_suggestions(company_ref_id);
CREATE INDEX IF NOT EXISTS ix_ai_suggestions_source ON ai_research_suggestions(source_id);
ALTER TABLE ai_research_suggestions ADD COLUMN IF NOT EXISTS source_content_id BIGINT REFERENCES research_source_contents(id);
ALTER TABLE ai_research_suggestions ADD COLUMN IF NOT EXISTS source_content_hash_at_run TEXT;
CREATE INDEX IF NOT EXISTS ix_ai_suggestions_source_content ON ai_research_suggestions(source_content_id);
CREATE INDEX IF NOT EXISTS ix_ai_suggestions_question ON ai_research_suggestions(question_id);

CREATE TABLE IF NOT EXISTS ai_suggestion_decisions(
    id BIGSERIAL PRIMARY KEY,
    suggestion_id BIGINT NOT NULL UNIQUE REFERENCES ai_research_suggestions(id),
    decision TEXT NOT NULL CHECK(decision IN('accepted','rejected')),
    decision_reason TEXT NOT NULL,
    created_evidence_id BIGINT REFERENCES research_evidence(id),
    created_link_id BIGINT REFERENCES evidence_question_links(id),
    decided_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text
);
CREATE INDEX IF NOT EXISTS ix_ai_decisions_created ON ai_suggestion_decisions(created_at DESC,id DESC);
CREATE INDEX IF NOT EXISTS ix_ai_decisions_evidence ON ai_suggestion_decisions(created_evidence_id);
CREATE INDEX IF NOT EXISTS ix_ai_decisions_link ON ai_suggestion_decisions(created_link_id);

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

CREATE TABLE IF NOT EXISTS peer_comparison_snapshots(
    company_ref_id BIGINT NOT NULL REFERENCES checklist_company_refs(id),
    review_id BIGINT NOT NULL REFERENCES research_reviews(id),
    version_no INTEGER NOT NULL,
    as_of_date TEXT NOT NULL,
    base_ticker TEXT NOT NULL,
    target_mos_pct DOUBLE PRECISION,
    peer_count INTEGER NOT NULL CHECK(peer_count BETWEEN 2 AND 10),
    source_module TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    save_reason TEXT NOT NULL,
    created_by TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    PRIMARY KEY(company_ref_id,review_id,version_no)
);
CREATE INDEX IF NOT EXISTS ix_peer_snapshots_review ON peer_comparison_snapshots(review_id,version_no);
CREATE INDEX IF NOT EXISTS ix_peer_snapshots_company_date ON peer_comparison_snapshots(company_ref_id,as_of_date,version_no);

CREATE TABLE IF NOT EXISTS management_people_versions(
    id BIGSERIAL PRIMARY KEY,
    company_ref_id BIGINT NOT NULL REFERENCES checklist_company_refs(id),
    review_id BIGINT NOT NULL REFERENCES research_reviews(id),
    person_key TEXT NOT NULL,
    version_no INTEGER NOT NULL,
    full_name TEXT NOT NULL,
    current_title TEXT NOT NULL,
    appointment_type TEXT NOT NULL CHECK(appointment_type IN('founder','internal','external','unknown')),
    start_date TEXT,
    end_date TEXT,
    is_key_manager INTEGER NOT NULL DEFAULT 1 CHECK(is_key_manager IN(0,1)),
    ownership_pct DOUBLE PRECISION CHECK(ownership_pct BETWEEN 0 AND 100),
    compensation_note TEXT,
    source_evidence_id BIGINT REFERENCES research_evidence(id),
    verification_status TEXT NOT NULL DEFAULT 'unverified' CHECK(verification_status IN('unverified','verified','disputed','stale')),
    change_reason TEXT,
    supersedes_version_id BIGINT REFERENCES management_people_versions(id),
    created_by TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    UNIQUE(review_id,person_key,version_no)
);
CREATE INDEX IF NOT EXISTS ix_management_people_review ON management_people_versions(review_id,person_key,version_no DESC);
CREATE INDEX IF NOT EXISTS ix_management_people_company ON management_people_versions(company_ref_id,review_id);
CREATE INDEX IF NOT EXISTS ix_management_people_evidence ON management_people_versions(source_evidence_id);
CREATE INDEX IF NOT EXISTS ix_management_people_supersedes ON management_people_versions(supersedes_version_id);

CREATE TABLE IF NOT EXISTS management_timeline_events(
    id BIGSERIAL PRIMARY KEY,
    company_ref_id BIGINT NOT NULL REFERENCES checklist_company_refs(id),
    review_id BIGINT NOT NULL REFERENCES research_reviews(id),
    person_key TEXT NOT NULL,
    event_date TEXT NOT NULL,
    end_date TEXT,
    event_type TEXT NOT NULL CHECK(event_type IN('joined','promoted','appointed','role_changed','departed','board_change','ownership_change','compensation_change','insider_trade','other')),
    organization TEXT NOT NULL,
    role_title TEXT NOT NULL,
    event_summary TEXT NOT NULL,
    external_hire INTEGER NOT NULL DEFAULT 0 CHECK(external_hire IN(0,1)),
    source_evidence_id BIGINT REFERENCES research_evidence(id),
    confidence INTEGER NOT NULL CHECK(confidence BETWEEN 1 AND 5),
    supersedes_event_id BIGINT REFERENCES management_timeline_events(id),
    change_reason TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text
);
CREATE INDEX IF NOT EXISTS ix_management_timeline_review_date ON management_timeline_events(review_id,event_date DESC,id DESC);
CREATE INDEX IF NOT EXISTS ix_management_timeline_person ON management_timeline_events(company_ref_id,person_key,event_date DESC);
CREATE INDEX IF NOT EXISTS ix_management_timeline_evidence ON management_timeline_events(source_evidence_id);
CREATE INDEX IF NOT EXISTS ix_management_timeline_supersedes ON management_timeline_events(supersedes_event_id);

CREATE TABLE IF NOT EXISTS management_track_records(
    id BIGSERIAL PRIMARY KEY,
    company_ref_id BIGINT NOT NULL REFERENCES checklist_company_refs(id),
    review_id BIGINT NOT NULL REFERENCES research_reviews(id),
    record_key TEXT NOT NULL,
    version_no INTEGER NOT NULL,
    record_type TEXT NOT NULL CHECK(record_type IN('compensation_ownership','insider_transaction','guidance','capital_allocation','buyback','ma_decision','ma_outcome','integrity','communication','human_intelligence')),
    subject_key TEXT NOT NULL,
    event_date TEXT,
    period_label TEXT,
    title TEXT NOT NULL,
    statement_text TEXT NOT NULL,
    expected_outcome TEXT,
    actual_outcome TEXT,
    result_status TEXT NOT NULL CHECK(result_status IN('pending','met','partly_met','missed','value_created','neutral','value_destroyed','verified','disputed','unknown')),
    horizon TEXT NOT NULL CHECK(horizon IN('current','1y','3y','5y','other')),
    amount_value DOUBLE PRECISION,
    currency TEXT NOT NULL DEFAULT 'VND',
    source_category TEXT NOT NULL CHECK(source_category IN('company','customer','competitor','supplier','employee','industry_insider','academic','headhunter','regulator','other')),
    credibility INTEGER NOT NULL CHECK(credibility BETWEEN 1 AND 5),
    corroboration_status TEXT NOT NULL CHECK(corroboration_status IN('single_source','corroborated','contradicted','not_applicable')),
    confidential INTEGER NOT NULL DEFAULT 0 CHECK(confidential IN(0,1)),
    source_evidence_id BIGINT REFERENCES research_evidence(id),
    question_ids_json TEXT NOT NULL,
    change_reason TEXT,
    supersedes_record_id BIGINT REFERENCES management_track_records(id),
    created_by TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    UNIQUE(review_id,record_key,version_no)
);
CREATE INDEX IF NOT EXISTS ix_management_track_review_type ON management_track_records(review_id,record_type,event_date DESC,id DESC);
CREATE INDEX IF NOT EXISTS ix_management_track_company ON management_track_records(company_ref_id,review_id);
CREATE INDEX IF NOT EXISTS ix_management_track_evidence ON management_track_records(source_evidence_id);
CREATE INDEX IF NOT EXISTS ix_management_track_supersedes ON management_track_records(supersedes_record_id);

CREATE TABLE IF NOT EXISTS management_question_signals(
    id BIGSERIAL PRIMARY KEY,
    company_ref_id BIGINT NOT NULL REFERENCES checklist_company_refs(id),
    review_id BIGINT NOT NULL REFERENCES research_reviews(id),
    question_id TEXT NOT NULL REFERENCES checklist_questions(question_id),
    subject_key TEXT NOT NULL,
    version_no INTEGER NOT NULL,
    signal_status TEXT NOT NULL CHECK(signal_status IN('supported','contradicted','mixed','research_gap','not_reviewed')),
    signal_score INTEGER CHECK(signal_score BETWEEN -2 AND 2),
    confidence INTEGER NOT NULL CHECK(confidence BETWEEN 1 AND 5),
    materiality INTEGER NOT NULL CHECK(materiality BETWEEN 1 AND 5),
    rationale TEXT NOT NULL,
    source_evidence_id BIGINT REFERENCES research_evidence(id),
    change_reason TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    UNIQUE(review_id,question_id,subject_key,version_no)
);
CREATE INDEX IF NOT EXISTS ix_management_signals_review_question ON management_question_signals(review_id,question_id,version_no DESC);
CREATE INDEX IF NOT EXISTS ix_management_signals_company ON management_question_signals(company_ref_id,review_id);
CREATE INDEX IF NOT EXISTS ix_management_signals_evidence ON management_question_signals(source_evidence_id);
CREATE INDEX IF NOT EXISTS ix_management_signals_question ON management_question_signals(question_id);

CREATE TABLE IF NOT EXISTS persistence_probes(
    probe_key TEXT PRIMARY KEY,
    deployment_marker TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    verified_at TEXT
);
'''
