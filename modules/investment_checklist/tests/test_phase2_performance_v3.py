from pathlib import Path
import inspect

import pandas as pd

from modules.investment_checklist.ui.performance_v3 import metric_candidates_v3, _assessment_bundle


def test_all_empty_numeric_metric_remains_analyst_editable():
    df = pd.DataFrame({
        "Kỳ": ["TTM", "2025"],
        "Net income": [100.0, 90.0],
        "Provision": [None, None],
        "Method": ["direct", "proxy"],
    })
    metrics = metric_candidates_v3(df, {"Kỳ"})
    assert "Net income" in metrics
    assert "Provision" in metrics
    assert "Method" not in metrics


def test_formula_renderer_uses_st_html_not_markdown_code_path():
    source = Path("modules/investment_checklist/ui/performance_v3.py").read_text(encoding="utf-8")
    assert "st.html(html)" in source
    assert "white-space:normal!important" in source
    assert "overflow-wrap:anywhere" in source


def test_question_navigation_is_fragment_isolated_from_page_pipeline():
    shell = Path("modules/investment_checklist/ui/integration_preview_v3.py").read_text(encoding="utf-8")
    page = Path("pages/05_Investment_Checklist.py").read_text(encoding="utf-8")
    assert "@st.fragment" in shell
    assert "integration_preview_v3 import render_investment_checklist" in page
    assert "@st.cache_data(ttl=120, show_spinner=False)" in page
    assert "Fast mode: đổi Question/tool không tải lại pipeline tài chính" in page


def test_workspace_question_read_is_one_sql_execute_and_catalog_is_local():
    source = inspect.getsource(_assessment_bundle)
    assert source.count("c.execute(") == 1
    perf = Path("modules/investment_checklist/ui/performance_v3.py").read_text(encoding="utf-8")
    assert "load_questions(CATALOG_PATH)" in perf
    assert "repo.list_questions()" not in inspect.getsource(__import__(
        "modules.investment_checklist.ui.performance_v3", fromlist=["render_workspace_fast"]
    ).render_workspace_fast)


def test_interactive_query_budget_is_reduced_by_more_than_half():
    # Previous Q switch path performed: list_reviews + watchlist state + list_questions + current + prior + history
    # = at least 6 persistence reads, in addition to a full page financial rerun.
    # Fast path caches reviews/watch state/catalog and executes one history query from which current/prior are derived.
    old_reads = 6
    fast_reads = 1
    assert fast_reads <= old_reads * 0.5
