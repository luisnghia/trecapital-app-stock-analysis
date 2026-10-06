"""Bound visible card work without caching business data or permissions."""
from __future__ import annotations

import hashlib


def page_rows(st, rows, key, page_size=24):
    """Keep every row reachable while rendering one small page at a time.

    Counts and filtering use the complete, freshly authorized input collection.
    Only a page number/fingerprint is kept in Session State; rows are never cached.
    """
    rows = list(rows)
    if len(rows) <= page_size:
        return rows
    prefix = f"_card_page_{key}"
    fingerprint = hashlib.sha256(
        ','.join(str(x.get('id', i)) for i, x in enumerate(rows)).encode()
    ).hexdigest()[:20]
    if st.session_state.get(prefix + '_rows') != fingerprint:
        st.session_state[prefix + '_rows'] = fingerprint
        st.session_state[prefix] = 0
    last = (len(rows) - 1) // page_size
    page = max(0, min(last, int(st.session_state.get(prefix, 0))))
    st.session_state[prefix] = page

    def move(delta):
        st.session_state[prefix] = max(0, min(last, int(st.session_state.get(prefix, 0)) + delta))

    left, center, right = st.columns([1, 3, 1])
    left.button('← Trước', key=prefix + '_prev', disabled=page == 0,
                on_click=move, args=(-1,), use_container_width=True)
    start = page * page_size
    center.caption(f"Công việc {start + 1}–{min(start + page_size, len(rows))} / {len(rows)} · Trang {page + 1}/{last + 1}")
    right.button('Sau →', key=prefix + '_next', disabled=page == last,
                 on_click=move, args=(1,), use_container_width=True)
    return rows[start:start + page_size]
