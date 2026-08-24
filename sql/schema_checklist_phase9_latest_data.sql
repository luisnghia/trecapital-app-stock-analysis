-- V23.94 / Phase 9 — Governed latest-on-click Portfolio Driver data
-- No realtime subscription, cron, background polling or client Data API privileges.

CREATE TABLE IF NOT EXISTS public.topdown_data_update_runs(
    id BIGSERIAL PRIMARY KEY,
    company_ref_id BIGINT NOT NULL REFERENCES public.checklist_company_refs(id),
    review_id BIGINT NOT NULL REFERENCES public.research_reviews(id),
    trigger_type TEXT NOT NULL CHECK(trigger_type='manual_click'),
    status TEXT NOT NULL CHECK(status IN('running','completed','partial','failed')),
    requested_driver_ids_json TEXT NOT NULL,
    source_registry_version TEXT NOT NULL,
    source_registry_hash TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    success_count INTEGER NOT NULL DEFAULT 0 CHECK(success_count>=0),
    failure_count INTEGER NOT NULL DEFAULT 0 CHECK(failure_count>=0),
    detail_json TEXT NOT NULL DEFAULT '{}',
    requested_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text
);

CREATE TABLE IF NOT EXISTS public.topdown_data_observations(
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES public.topdown_data_update_runs(id),
    company_ref_id BIGINT NOT NULL REFERENCES public.checklist_company_refs(id),
    review_id BIGINT NOT NULL REFERENCES public.research_reviews(id),
    driver_id TEXT NOT NULL,
    source_code TEXT NOT NULL,
    source_tier TEXT NOT NULL,
    series_code TEXT NOT NULL,
    source_url TEXT NOT NULL,
    period_label TEXT NOT NULL,
    observation_date TEXT NOT NULL,
    published_at TEXT,
    retrieved_at TEXT NOT NULL,
    frequency TEXT NOT NULL,
    value_numeric DOUBLE PRECISION NOT NULL,
    previous_value_numeric DOUBLE PRECISION,
    delta_numeric DOUBLE PRECISION,
    unit TEXT NOT NULL,
    observation_status TEXT NOT NULL,
    freshness_status TEXT NOT NULL CHECK(freshness_status IN('current','aging','stale','event_driven')),
    payload_hash TEXT NOT NULL,
    raw_locator TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    UNIQUE(run_id,series_code)
);

CREATE TABLE IF NOT EXISTS public.topdown_driver_suggestions(
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES public.topdown_data_update_runs(id),
    observation_id BIGINT NOT NULL REFERENCES public.topdown_data_observations(id),
    company_ref_id BIGINT NOT NULL REFERENCES public.checklist_company_refs(id),
    review_id BIGINT NOT NULL REFERENCES public.research_reviews(id),
    driver_id TEXT NOT NULL,
    suggested_score INTEGER CHECK(suggested_score BETWEEN -2 AND 2),
    confidence INTEGER NOT NULL CHECK(confidence BETWEEN 1 AND 5),
    rationale TEXT NOT NULL,
    data_gap_reason TEXT,
    method_version TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    UNIQUE(run_id,observation_id)
);

CREATE TABLE IF NOT EXISTS public.topdown_driver_decisions(
    id BIGSERIAL PRIMARY KEY,
    suggestion_id BIGINT NOT NULL UNIQUE REFERENCES public.topdown_driver_suggestions(id),
    company_ref_id BIGINT NOT NULL REFERENCES public.checklist_company_refs(id),
    review_id BIGINT NOT NULL REFERENCES public.research_reviews(id),
    decision TEXT NOT NULL CHECK(decision IN('accept','reject')),
    applied_score INTEGER CHECK(applied_score BETWEEN -2 AND 2),
    decision_reason TEXT NOT NULL,
    analyst_confirmed INTEGER NOT NULL CHECK(analyst_confirmed IN(0,1)),
    decided_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    CHECK((decision='accept' AND applied_score IS NOT NULL AND analyst_confirmed=1)
       OR (decision='reject' AND applied_score IS NULL AND analyst_confirmed=0))
);

CREATE INDEX IF NOT EXISTS ix_topdown_update_runs_review
    ON public.topdown_data_update_runs(review_id,id DESC);
CREATE INDEX IF NOT EXISTS ix_topdown_update_runs_company
    ON public.topdown_data_update_runs(company_ref_id,id DESC);
CREATE INDEX IF NOT EXISTS ix_topdown_observations_review_driver
    ON public.topdown_data_observations(review_id,driver_id,id DESC);
CREATE INDEX IF NOT EXISTS ix_topdown_observations_run
    ON public.topdown_data_observations(run_id,id);
CREATE INDEX IF NOT EXISTS ix_topdown_observations_company_date
    ON public.topdown_data_observations(company_ref_id,observation_date DESC,id DESC);
CREATE INDEX IF NOT EXISTS ix_topdown_suggestions_review
    ON public.topdown_driver_suggestions(review_id,id DESC);
CREATE INDEX IF NOT EXISTS ix_topdown_suggestions_driver
    ON public.topdown_driver_suggestions(company_ref_id,driver_id,id DESC);
CREATE INDEX IF NOT EXISTS ix_topdown_suggestions_observation
    ON public.topdown_driver_suggestions(observation_id);
CREATE INDEX IF NOT EXISTS ix_topdown_decisions_review
    ON public.topdown_driver_decisions(review_id,id DESC);
CREATE INDEX IF NOT EXISTS ix_topdown_decisions_company
    ON public.topdown_driver_decisions(company_ref_id,id DESC);

COMMENT ON TABLE public.topdown_data_update_runs IS
    'Phase 9 explicit manual-click fetch audit. Never populated by realtime, cron or background polling.';
COMMENT ON TABLE public.topdown_data_observations IS
    'Append-only exact observations with source URL, source period, retrieval time and payload SHA-256.';
COMMENT ON TABLE public.topdown_driver_suggestions IS
    'Governed Portfolio Driver suggestions. Does not write Q01-Q59 or investment decisions.';
COMMENT ON TABLE public.topdown_driver_decisions IS
    'Immutable analyst accept/reject decision for each Phase 9 suggestion.';

ALTER TABLE public.topdown_data_update_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.topdown_data_observations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.topdown_driver_suggestions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.topdown_driver_decisions ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.topdown_data_update_runs FROM anon, authenticated;
REVOKE ALL ON TABLE public.topdown_data_observations FROM anon, authenticated;
REVOKE ALL ON TABLE public.topdown_driver_suggestions FROM anon, authenticated;
REVOKE ALL ON TABLE public.topdown_driver_decisions FROM anon, authenticated;
REVOKE ALL ON SEQUENCE public.topdown_data_update_runs_id_seq FROM anon, authenticated;
REVOKE ALL ON SEQUENCE public.topdown_data_observations_id_seq FROM anon, authenticated;
REVOKE ALL ON SEQUENCE public.topdown_driver_suggestions_id_seq FROM anon, authenticated;
REVOKE ALL ON SEQUENCE public.topdown_driver_decisions_id_seq FROM anon, authenticated;
