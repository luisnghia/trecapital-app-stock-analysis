from __future__ import annotations

from pathlib import Path

from khdn_apps import weekly_plan_ui as ui


def main():
    # Unit-test the two-phase reset without requiring a Streamlit ScriptRunContext.
    state={"wp_text":"T2 gặp khách hàng","wp_preview":[1],"wp_preview_week":"2026-09-21"}
    ui.request_quick_input_reset(state)
    assert state["wp_text"]=="T2 gặp khách hàng", "request phase must not mutate live widget key"
    assert state.get("_wp_clear_text_next_run") is True
    assert "wp_preview" not in state and "wp_preview_week" not in state
    ui.apply_deferred_widget_resets(state)
    assert state["wp_text"]=="", "next-run phase must clear quick input"
    assert "_wp_clear_text_next_run" not in state

    source=Path(ui.__file__).read_text(encoding="utf-8")
    assert 'text_area(' in source and 'key="wp_text"' in source
    assert 'st.session_state.wp_text=' not in source.replace(" ", "")
    assert 'request_quick_input_reset(st.session_state)' in source
    # Compare against the executable text_area statement, not the explanatory docstring.
    assert source.index('apply_deferred_widget_resets(st.session_state)') < source.index('text = st.text_area(')
    print("WEEKLY_PLAN_STATE_QA_PASS")


if __name__=="__main__":
    main()
