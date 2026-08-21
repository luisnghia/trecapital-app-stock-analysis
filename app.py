from __future__ import annotations

import module1_dashboard as m1
from tre_full_width import apply_full_width
from tre_sidebar_nav import render_tre_sidebar_nav

# Module 1 owns the host sidebar. Replace its legacy four-page navigation
# with the shared navigation contract so the Phase 1C preview exposes
# Investment Checklist consistently from the app entry page.
if hasattr(m1, "_render_tre_sidebar_nav"):
    m1._render_tre_sidebar_nav = render_tre_sidebar_nav

m1.render_dashboard()
apply_full_width()
