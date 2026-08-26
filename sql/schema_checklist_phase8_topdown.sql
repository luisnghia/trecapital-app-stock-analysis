-- V23.92 / Phase 8 — Governed Fisher Top-down & Sector Context
-- Backend-only workflow state. No Data API privileges are granted to client roles.

CREATE TABLE IF NOT EXISTS public.topdown_sector_snapshots(
    id BIGSERIAL PRIMARY KEY,
    company_ref_id BIGINT NOT NULL REFERENCES public.checklist_company_refs(id),
    review_id BIGINT NOT NULL REFERENCES public.research_reviews(id),
    version_no INTEGER NOT NULL,
    as_of_date TEXT NOT NULL,
    horizon_months INTEGER NOT NULL CHECK(horizon_months BETWEEN 1 AND 36),
    methodology_version TEXT NOT NULL,
    selected_sector_code TEXT NOT NULL,
    selected_sector_name TEXT NOT NULL,
    cycle_phase TEXT NOT NULL,
    benchmark_id TEXT NOT NULL,
    benchmark_name TEXT NOT NULL,
    benchmark_status TEXT NOT NULL CHECK(benchmark_status IN('unverified','historical_source','analyst_verified')),
    benchmark_source_evidence_id BIGINT REFERENCES public.research_evidence(id),
    sector_score DOUBLE PRECISION NOT NULL CHECK(sector_score BETWEEN 0 AND 100),
    benchmark_weight_pct DOUBLE PRECISION NOT NULL CHECK(benchmark_weight_pct BETWEEN 0 AND 100),
    proposed_weight_pct DOUBLE PRECISION NOT NULL CHECK(proposed_weight_pct BETWEEN 0 AND 100),
    tilt_pct DOUBLE PRECISION NOT NULL CHECK(tilt_pct BETWEEN -100 AND 100),
    research_gaps_json TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    source_mapping_hash TEXT NOT NULL,
    analyst_confirmed INTEGER NOT NULL CHECK(analyst_confirmed=1),
    change_reason TEXT NOT NULL,
    supersedes_snapshot_id BIGINT REFERENCES public.topdown_sector_snapshots(id),
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    UNIQUE(review_id,version_no)
);

CREATE INDEX IF NOT EXISTS ix_topdown_sector_review_version
    ON public.topdown_sector_snapshots(review_id,version_no DESC,id DESC);
CREATE INDEX IF NOT EXISTS ix_topdown_sector_company_date
    ON public.topdown_sector_snapshots(company_ref_id,as_of_date DESC,id DESC);
CREATE INDEX IF NOT EXISTS ix_topdown_sector_evidence
    ON public.topdown_sector_snapshots(benchmark_source_evidence_id);
CREATE INDEX IF NOT EXISTS ix_topdown_sector_supersedes
    ON public.topdown_sector_snapshots(supersedes_snapshot_id);

COMMENT ON TABLE public.topdown_sector_snapshots IS
    'Phase 8 governed Fisher Top-down/Sector context; append-only analyst snapshots, trusted direct Postgres only.';

ALTER TABLE public.topdown_sector_snapshots ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.topdown_sector_snapshots FROM anon, authenticated;
REVOKE ALL ON SEQUENCE public.topdown_sector_snapshots_id_seq FROM anon, authenticated;
