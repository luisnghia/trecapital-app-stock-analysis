from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Protocol


@dataclass(frozen=True)
class CompanyContext:
    company_key: str
    ticker: str
    company_name: str
    exchange: str = "UNKNOWN"
    industry_name: str = ""
    company_type: str = "normal"
    currency: str = "VND"
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AnalystContext:
    user_id: str = "analyst"
    display_name: str = "Analyst"


@dataclass(frozen=True)
class HostContext:
    company: CompanyContext
    analyst: AnalystContext = field(default_factory=AnalystContext)
    shared_db_path: Optional[Path] = None
    database_url: Optional[str] = None
    selected_as_of_date: Optional[str] = None


@dataclass(frozen=True)
class InventorySourceData:
    as_of_date: str
    tev: Optional[float] = None
    ebit: Optional[float] = None
    ebitda: Optional[float] = None
    normalized_earnings: Optional[float] = None
    total_debt: Optional[float] = None
    interest_expense: Optional[float] = None
    fcf_current: Optional[float] = None
    market_cap: Optional[float] = None
    dividend_per_share: Optional[float] = None
    market_price: Optional[float] = None
    fcf_estimate: Optional[float] = None
    target_price: Optional[float] = None
    mos: Optional[float] = None
    source_module: str = "host_data_layer"


class TrecapitalDataProvider(Protocol):
    def get_inventory_source_data(self, company: CompanyContext) -> Optional[InventorySourceData]: ...


class TrecapitalThemeAdapter(Protocol):
    def inject_module_css(self) -> None: ...
    def render_metric_note(self, label: str, note: str) -> None: ...
