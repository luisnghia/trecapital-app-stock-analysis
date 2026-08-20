from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_streamlit_phase1b_initial_render_has_no_exception():
    app = Path(__file__).with_name("streamlit_smoke_app.py")
    at = AppTest.from_file(str(app)).run(timeout=30)
    assert len(at.exception) == 0
    values = [x.value for x in at.subheader]
    assert any("Investment Research & Checklist System" in str(v) for v in values)
