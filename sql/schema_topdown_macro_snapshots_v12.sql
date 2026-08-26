-- Fisher Top-Down V1.2 — standalone append-only macro proxy history.
-- Intentionally has no company/review/Q01-Q59 foreign key and no Data API policy.

CREATE TABLE IF NOT EXISTS public.topdown_macro_snapshots (
    id BIGSERIAL PRIMARY KEY,
    version_no INTEGER NOT NULL UNIQUE CHECK(version_no > 0),
    as_of_date DATE NOT NULL,
    snapshot_label TEXT NOT NULL CHECK(length(trim(snapshot_label)) > 0),
    methodology_version TEXT NOT NULL,
    source_registry_hash TEXT,
    payload_json JSONB NOT NULL,
    payload_hash TEXT NOT NULL UNIQUE,
    save_reason TEXT NOT NULL CHECK(length(trim(save_reason)) > 0),
    created_by TEXT NOT NULL CHECK(length(trim(created_by)) > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_topdown_macro_snapshots_asof
ON public.topdown_macro_snapshots(as_of_date DESC, version_no DESC);

CREATE OR REPLACE FUNCTION public.prevent_topdown_macro_snapshot_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'topdown_macro_snapshots is append-only';
END;
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname='no_mutation_topdown_macro_snapshots'
          AND tgrelid='public.topdown_macro_snapshots'::regclass
    ) THEN
        CREATE TRIGGER no_mutation_topdown_macro_snapshots
        BEFORE UPDATE OR DELETE ON public.topdown_macro_snapshots
        FOR EACH ROW EXECUTE FUNCTION public.prevent_topdown_macro_snapshot_mutation();
    END IF;
END $$;

ALTER TABLE public.topdown_macro_snapshots ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.topdown_macro_snapshots FROM anon, authenticated;
REVOKE ALL ON SEQUENCE public.topdown_macro_snapshots_id_seq FROM anon, authenticated;
