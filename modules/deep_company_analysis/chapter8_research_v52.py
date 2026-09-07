from __future__ import annotations

"""Compatibility import for the Chapter 8 research UI.

The production page historically imports this module name. V53 remains re-exported as the
backward-compatible baseline, V54 preserves the official deep-retrieval layer, and V55 is
re-exported last so the Phase 8J official archive/history agent is active. This keeps one analyst
workspace/state store while preserving earlier phase compatibility checks.
"""

from modules.deep_company_analysis.chapter8_research_v53 import *  # noqa: F401,F403
from modules.deep_company_analysis.chapter8_research_v54 import *  # noqa: F401,F403
from modules.deep_company_analysis.chapter8_research_v55 import *  # noqa: F401,F403
