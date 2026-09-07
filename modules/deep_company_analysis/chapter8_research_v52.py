from __future__ import annotations

"""Compatibility import for the Chapter 8 research UI.

The production page historically imports this module name. V53 remains re-exported as the
backward-compatible research baseline, then V54 is re-exported last so its Phase 8I agent is the
active ``Chapter8ResearchAgent``. This keeps the existing analyst workspace/state store while
preserving earlier phase compatibility checks.
"""

from modules.deep_company_analysis.chapter8_research_v53 import *  # noqa: F401,F403
from modules.deep_company_analysis.chapter8_research_v54 import *  # noqa: F401,F403
