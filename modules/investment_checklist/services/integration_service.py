from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Optional

from ..contracts import HostContext, InventorySourceData, TrecapitalDataProvider
from ..repositories.sqlite_repository import SQLiteChecklistRepository

MODULE_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = MODULE_ROOT / "catalog" / "question_catalog_prd.csv"


def resolve_db_path(host: HostContext) -> Path:
    if host.shared_db_path:
        return Path(host.shared_db_path)
    env_path = os.getenv("TREC_CHECKLIST_DB_PATH")
    if env_path:
        return Path(env_path)
    return MODULE_ROOT / "data" / "checklist_phase1b_dev.db"


def build_repository(host: HostContext) -> SQLiteChecklistRepository:
    repo = SQLiteChecklistRepository(resolve_db_path(host), CATALOG_PATH)
    repo.initialize()
    return repo


class ChecklistIntegrationService:
    def __init__(self, repo: SQLiteChecklistRepository, host: HostContext,
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
