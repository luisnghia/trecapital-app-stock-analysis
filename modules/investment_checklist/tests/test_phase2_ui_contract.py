from __future__ import annotations

from pathlib import Path

import pandas as pd

from modules.investment_checklist.ui.quant_tools import _latest_first


def test_phase2_history_displays_ttm_first_then_latest_years():
    df = pd.DataFrame([
        {"Kỳ": "2023", "Value": 1},
        {"Kỳ": "TTM", "Value": 4},
        {"Kỳ": "2025", "Value": 3},
        {"Kỳ": "2024", "Value": 2},
    ])
    assert _latest_first(df)["Kỳ"].tolist() == ["TTM", "2025", "2024", "2023"]


def test_phase2_ui_executes_only_selected_tool_and_exposes_formula_audit():
    source = Path("modules/investment_checklist/ui/quant_tools.py").read_text(encoding="utf-8")
    shell = Path("modules/investment_checklist/ui/__init__.py").read_text(encoding="utf-8")
    assert "st.tabs(" not in source
    assert "🧮 Analytical Tools" in shell
    assert "PHASE2_FORMULA_ROWS" in source
    assert "📐 Công thức & giả định của Analytical Tools" in source


def test_phase2_formula_registry_distinguishes_source_and_trecapital_extension():
    source = Path("modules/investment_checklist/phase2_formula_assumptions.py").read_text(encoding="utf-8")
    assert "Shearn" in source
    assert "Trecapital extension" in source
    assert "Single Source of Truth" in source
    assert "Không tính lại Beneish" in source
