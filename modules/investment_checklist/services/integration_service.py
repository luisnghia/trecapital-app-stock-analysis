from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Optional, Union

from ..contracts import HostContext, InventorySourceData, TrecapitalDataProvider
from ..repositories.sqlite_repository import SQLiteChecklistRepository
from ..repositories.postgres_repository import PostgresChecklistRepository

MODULE_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = MODULE_ROOT / "catalog" / "question_catalog_prd.csv"
ChecklistRepository = Union[SQLiteChecklistRepository, PostgresChecklistRepository]

# Streamlit reruns the script for every widget change. Re-creating the repository on every
# rerun caused schema checks + 59 question upserts + 10 screening upserts each time and also
# destroyed any PostgreSQL connection pool. Keep one initialized repository per backend for
# the lifetime of the Python process. Repository methods remain transaction-scoped/thread-safe.
_REPOSITORY_CACHE: dict[tuple[str, str], ChecklistRepository] = {}
_REPOSITORY_CACHE_LOCK = threading.Lock()


def resolve_database_url(host: HostContext) -> Optional[str]:
    if host.database_url and str(host.database_url).strip():
        return str(host.database_url).strip()
    for key in ("TREC_CHECKLIST_DATABASE_URL", "DATABASE_URL", "SUPABASE_DB_URL"):
        value = os.getenv(key)
        if value and value.strip():
            return value.strip()
    return None


def resolve_db_path(host: HostContext) -> Path:
    if host.shared_db_path:
        return Path(host.shared_db_path)
    env_path = os.getenv("TREC_CHECKLIST_DB_PATH")
    if env_path:
        return Path(env_path)
    return MODULE_ROOT / "data" / "checklist_phase1b_dev.db"


def _repository_key(host: HostContext) -> tuple[str, str]:
    database_url = resolve_database_url(host)
    if database_url:
        # Do not expose the credential in logs/debug keys. The digest only separates backends.
        digest = hashlib.sha256(database_url.encode("utf-8")).hexdigest()
        return ("postgresql", digest)
    return ("sqlite", str(resolve_db_path(host).resolve()))


def build_repository(host: HostContext) -> ChecklistRepository:
    key = _repository_key(host)
    cached = _REPOSITORY_CACHE.get(key)
    if cached is not None:
        return cached

    with _REPOSITORY_CACHE_LOCK:
        cached = _REPOSITORY_CACHE.get(key)
        if cached is not None:
            return cached
        database_url = resolve_database_url(host)
        if database_url:
            repo: ChecklistRepository = PostgresChecklistRepository(database_url, CATALOG_PATH)
        else:
            repo = SQLiteChecklistRepository(resolve_db_path(host), CATALOG_PATH)
        repo.initialize()
        _REPOSITORY_CACHE[key] = repo
        return repo


def clear_repository_cache() -> None:
    """Test/dev hook. Production Streamlit normally keeps the cache for process lifetime."""
    with _REPOSITORY_CACHE_LOCK:
        for repo in _REPOSITORY_CACHE.values():
            close = getattr(repo, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass
        _REPOSITORY_CACHE.clear()


def persistence_backend(host: HostContext) -> str:
    return "postgresql" if resolve_database_url(host) else "sqlite-local"


class ChecklistIntegrationService:
    def __init__(self, repo: ChecklistRepository, host: HostContext,
                 data_provider: Optional[TrecapitalDataProvider] = None):
        self.repo = repo
        self.host = host
        self.data_provider = data_provider

    def sync_company_context(self) -> int:
        c = self.host.company
        return self.repo.upsert_company_ref(
            host_company_key=c.company_key,
            ticker=c.ticker,
            company_name=c.company_name,
            exchange=c.exchange,
            industry_name=c.industry_name,
            company_type=c.company_type,
            currency=c.currency,
            host_metadata=dict(c.metadata),
            actor=self.host.analyst.user_id,
        )

    def get_inventory_prefill(self) -> Optional[InventorySourceData]:
        if self.data_provider is None:
            return None
        try:
            return self.data_provider.get_inventory_source_data(self.host.company)
        except Exception as exc:
            company_ref = self.repo.get_company_ref_by_host_key(self.host.company.company_key)
            if company_ref:
                self.repo.record_sync(
                    company_ref_id=company_ref["id"],
                    source_module="host_data_layer",
                    status="failed",
                    detail=str(exc),
                )
            return None

    @staticmethod
    def payload_hash(data: InventorySourceData) -> str:
        payload = json.dumps(data.__dict__, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def save_host_inventory_snapshot(self, *, company_ref_id: int, review_id: Optional[int],
                                     data: InventorySourceData, mos=None,
                                     thesis_direction="unknown", note="") -> int:
        iid = self.repo.save_inventory_snapshot(
            company_ref_id=company_ref_id,
            as_of_date=data.as_of_date,
            review_id=review_id,
            tev=data.tev,
            ebit=data.ebit,
            ebitda=data.ebitda,
            normalized_earnings=data.normalized_earnings,
            total_debt=data.total_debt,
            interest_expense=data.interest_expense,
            fcf_current=data.fcf_current,
            market_cap=data.market_cap,
            dividend_per_share=data.dividend_per_share,
            market_price=data.market_price,
            fcf_estimate=data.fcf_estimate,
            target_price=data.target_price,
            mos=data.mos if mos is None else mos,
            thesis_direction=thesis_direction,
            note=note,
            actor=self.host.analyst.user_id,
            data_origin="host_data_layer",
            source_as_of_date=data.as_of_date,
        )
        self.repo.record_sync(
            company_ref_id=company_ref_id,
            source_module=data.source_module,
            source_as_of_date=data.as_of_date,
            payload_hash=self.payload_hash(data),
            status="success",
            detail=f"Saved opportunity_inventory snapshot #{iid}",
        )
        return iid
