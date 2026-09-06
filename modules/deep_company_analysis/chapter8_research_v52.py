from __future__ import annotations

"""Compatibility import for the Chapter 8 research UI.

The production page historically imports this module name. On the V53 feature branch it
re-exports the Phase 8H wrapper so the existing analyst workspace gains gap-directed research
without duplicating UI state or storage. The workflow remains analyst-controlled and evidence-only.
"""

from modules.deep_company_analysis.chapter8_research_v53 import *  # noqa: F401,F403
