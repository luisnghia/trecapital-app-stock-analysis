"""Tiny client-side theme probe for KHDN Ops.

The probe receives Streamlit's *actual active* theme inside a custom component and
forwards only the theme base to the parent page. It never sends a component value,
so it cannot trigger a Python rerun. The static shell listens for that message and
adds/removes the `khdn-light` class. This lets Light-mode CSS react immediately to
a user theme switch while leaving Dark-mode styling untouched.
"""
from pathlib import Path
import streamlit.components.v1 as components


_probe = components.declare_component(
    "khdn_theme_probe",
    path=str(Path(__file__).with_name("theme_probe_component")),
)


def render_theme_probe() -> None:
    """Render a zero-height, no-value component that reports the live theme."""
    _probe(key="khdn_theme_probe_v1", default=None)
