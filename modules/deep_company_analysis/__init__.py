"""Deep company analysis module for Trecapital."""

# Chapter 2 Phase 2B keeps the broad evidence/data bridge in `chapter2_auto` and applies a
# boundary-safe Q6 geography extractor. Import-time wiring preserves the public API used by the
# page/tests while avoiding false country matches such as "Ấn Độ" across "Thái Lan doanh thu".
from . import chapter2_auto as _chapter2_auto
from .chapter2_q6_bridge import build_chapter2_assistant_draft as _q6_safe_build

_chapter2_auto.build_chapter2_assistant_draft = _q6_safe_build
