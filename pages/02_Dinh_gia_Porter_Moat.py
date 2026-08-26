from __future__ import annotations

import module2_dashboard as md
from tre_full_width import apply_full_width
from tre_sidebar_nav import render_tre_sidebar_nav

# Keep navigation identical on every page, including Investment Checklist.
if hasattr(md, "_render_tre_sidebar_nav"):
    md._render_tre_sidebar_nav = render_tre_sidebar_nav

md.render_dashboard()
apply_full_width()
