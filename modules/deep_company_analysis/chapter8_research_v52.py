from __future__ import annotations

"""Compatibility import for the Chapter 8 research UI.

The production page historically imports this module name. V53 remains re-exported as the
backward-compatible baseline, V54 preserves official deep retrieval, V55 adds bounded archive
research, V56 adds explicit direct official-URL ingestion, V57 adds analyst-supplied official
file/PDF ingestion, V59 adds bounded scanned-PDF OCR, V60 adds gap-directed high-resolution OCR,
and V61 is re-exported last so open source-locked dimensions can first expand the official document
set by relevant archive section before any expensive OCR pass. One analyst workspace/state store is preserved.
"""

from modules.deep_company_analysis.chapter8_research_v53 import *  # noqa: F401,F403
from modules.deep_company_analysis.chapter8_research_v54 import *  # noqa: F401,F403
from modules.deep_company_analysis.chapter8_research_v55 import *  # noqa: F401,F403
from modules.deep_company_analysis.chapter8_research_v56 import *  # noqa: F401,F403
from modules.deep_company_analysis.chapter8_research_v57 import *  # noqa: F401,F403
from modules.deep_company_analysis.chapter8_research_v59 import *  # noqa: F401,F403
from modules.deep_company_analysis.chapter8_research_v60 import *  # noqa: F401,F403
from modules.deep_company_analysis.chapter8_research_v61 import *  # noqa: F401,F403
