from __future__ import annotations

from pathlib import Path
import pandas as pd

from .base import ProviderResult, normalize_columns, MODULE1_OVERVIEW_COLUMNS, MODULE1_TIMESERIES_COLUMNS


class CSVProvider:
    """Provider dùng cho dữ liệu đã chuẩn hóa từ FireAnt/Vietstock/export Excel."""

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)

    def fetch(self, ticker: str) -> ProviderResult:
        ticker = ticker.upper().strip()
        overview_path = self.data_dir / "company_overview_sample.csv"
        year_path = self.data_dir / "financial_timeseries_year.csv"
        quarter_path = self.data_dir / "financial_timeseries_quarter.csv"
        overview = pd.read_csv(overview_path) if overview_path.exists() else pd.DataFrame(columns=MODULE1_OVERVIEW_COLUMNS)
        annual = pd.read_csv(year_path) if year_path.exists() else pd.DataFrame(columns=MODULE1_TIMESERIES_COLUMNS)
        quarterly = pd.read_csv(quarter_path) if quarter_path.exists() else pd.DataFrame(columns=MODULE1_TIMESERIES_COLUMNS)
        overview = overview[overview["ticker"].astype(str).str.upper() == ticker] if not overview.empty else overview
        annual = annual[annual["ticker"].astype(str).str.upper() == ticker] if not annual.empty else annual
        quarterly = quarterly[quarterly["ticker"].astype(str).str.upper() == ticker] if not quarterly.empty else quarterly
        return ProviderResult(
            overview=normalize_columns(overview, MODULE1_OVERVIEW_COLUMNS),
            annual=normalize_columns(annual, MODULE1_TIMESERIES_COLUMNS),
            quarterly=normalize_columns(quarterly, MODULE1_TIMESERIES_COLUMNS),
            note="Loaded from normalized CSV files.",
        )
