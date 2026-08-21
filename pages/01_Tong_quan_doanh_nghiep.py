from __future__ import annotations

import module1_dashboard as m1
from tre_full_width import apply_full_width
from tre_sidebar_nav import render_tre_sidebar_nav

# Keep navigation identical on every page, including Investment Checklist.
if hasattr(m1, "_render_tre_sidebar_nav"):
    m1._render_tre_sidebar_nav = render_tre_sidebar_nav

m1.render_dashboard()
apply_full_width()
