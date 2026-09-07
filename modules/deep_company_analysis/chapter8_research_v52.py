from __future__ import annotations

"""Compatibility import for the Chapter 8 research UI.

The production page historically imports this module name. V53 remains re-exported as the
backward-compatible baseline, V54 preserves official deep retrieval, V55 adds bounded archive
research, V56 adds explicit direct official-URL ingestion, and V57 is re-exported last so
analyst-supplied official file/PDF ingestion is available from the same Chapter 8 research agent.
This keeps one analyst workspace/state store while preserving earlier phase compatibility checks.
"""

from modules.deep_company_analysis.chapter8_research_v53 import *  # noqa: F401,F403
from modules.deep_company_analysis.chapter8_research_v54 import *  # noqa: F401,F403
from modules.deep_company_analysis.chapter8_research_v55 import *  # noqa: F401,F403
from modules.deep_company_analysis.chapter8_research_v56 import *  # noqa: F401,F403
from modules.deep_company_analysis.chapter8_research_v57 import *  # noqa: F401,F403
