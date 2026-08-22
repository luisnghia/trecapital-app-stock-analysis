from __future__ import annotations

"""Phase 3B UI: explicitly approve and persist a peer ranking into the selected review."""

from typing import Any

import pandas as pd
import streamlit as st

from ..repositories.sqlite_repository import ValidationError
from ..services.peer_snapshots import (
    PEER_QUESTION_IDS,
    get_peer_snapshot,
    list_peer_snapshots,
    normalize_peer_result,
    save_peer_snapshot,
)


_PCT_COLUMNS = {
    "MOS hiện tại %", "ROE %", "ROIC %", "Biên gộp %", "Biên ròng %",
    "CAGR DT 5Y %", "CAGR LNST 5Y %",
}
_RATIO_COLUMNS = {"P/E", "P/B", "CFO/LNST", "FCF/LNST", "Nợ ròng/VCSH"}
_SCORE_COLUMNS = {"Điểm tổng hợp", "Điểm chất lượng", "Điểm dòng tiền", "Điểm định giá", "Moat score"}
_MONEY_COLUMNS = {"Giá hiện tại", "Giá trị weighted", "Vốn hóa (tỷ đồng)"}


def _fmt(value: Any, column: str) -> str:
    if value is None or pd.isna(value):
        return "—"
    if column in _PCT_COLUMNS:
        return f"{float(value):,.1f}%"
    if column in _RATIO_COLUMNS:
        return f"{float(value):,.1f}x"
    if column in _SCORE_COLUMNS:
        return f"{float(value):,.1f}"
    if column in _MONEY_COLUMNS:
        return f"{float(value):,.0f}"
    return str(value)


def _display(frame: pd.DataFrame) -> pd.DataFrame:
    preferred = [
        "Xếp hạng", "Mã", "Tên doanh nghiệp", "Điểm tổng hợp", "MOS hiện tại %",
        "Moat score", "ROE %", "ROIC %", "P/E", "P/B", "Kết luận so sánh",
    ]
    cols = [col for col in preferred if col in frame.columns]
    shown = frame[cols].copy()
    for column in shown.columns:
        shown[column] = shown[column].map(lambda value, name=column: _fmt(value, name))
    return shown


def _saved_frame(snapshot: dict[str, Any] | None) -> pd.DataFrame:
    if not snapshot:
        return pd.DataFrame()
    payload = snapshot.get("payload") or {}
    rows = payload.get("rows") or []
    return pd.DataFrame(rows)


def render_peer_snapshot(
    repo,
    *,
    company_ref_id: int,
    review: dict[str, Any] | None,
    base_ticker: str,
    actor: str,
) -> None:
    st.markdown("#### ⚖️ Peer Snapshot & Ranking — Phase 3B")
    st.caption(
        "Chạy so sánh tối đa 10 doanh nghiệp tại trang So sánh doanh nghiệp, sau đó quay lại đây để "
        "analyst chủ động lưu đúng kết quả vào review. Không tải mạng khi đổi Q01–Q59 và không tự ghi assessment."
    )
    st.caption(f"Liên kết evidence định lượng: {', '.join(PEER_QUESTION_IDS)}.")

    try:
        st.page_link("pages/03_So_sanh_doanh_nghiep.py", label="Mở So sánh doanh nghiệp", icon="⚖️")
    except Exception:
        pass

    if review is None:
        st.info("Cần tạo/chọn một review trước khi lưu Peer Snapshot.")
        return

    latest = get_peer_snapshot(repo, int(review["id"]))
    if latest:
        st.markdown(
            f"**Snapshot đã lưu:** v{latest['version_no']} · {latest['peer_count']} doanh nghiệp · "
            f"as-of {latest['as_of_date']} · hash `{str(latest['payload_hash'])[:12]}…`"
        )
        saved = _saved_frame(latest)
        if not saved.empty:
            st.dataframe(_display(saved), use_container_width=True, hide_index=True, height=min(470, 38 * len(saved) + 90))
        st.caption(f"Lý do lưu: {latest['save_reason']}")
    else:
        st.info("Review này chưa có Peer Snapshot được analyst xác nhận.")

    session_result = st.session_state.get("peer_compare_result")
    session_base_ticker = str(st.session_state.get("module3_base_ticker") or "").strip().upper()
    current = None
    session_error = None
    if isinstance(session_result, pd.DataFrame) and not session_result.empty:
        if session_base_ticker != str(base_ticker).strip().upper():
            session_error = (
                f"Kết quả tạm được tạo cho {session_base_ticker or 'mã không xác định'}, "
                f"không phải {str(base_ticker).strip().upper()}; hãy chạy lại so sánh từ đúng mã."
            )
        else:
            try:
                current = normalize_peer_result(session_result, base_ticker=base_ticker)
            except ValidationError as exc:
                session_error = str(exc)

    if current is None:
        if session_error:
            st.warning(f"Kết quả peer tạm trong phiên chưa thể gắn vào {base_ticker}: {session_error}")
        else:
            st.caption("Chưa có kết quả peer tạm trong phiên. Hãy chạy so sánh rồi quay lại tab này.")
    else:
        st.markdown("##### Kết quả tạm đang chờ analyst xác nhận")
        st.dataframe(_display(current), use_container_width=True, hide_index=True, height=min(470, 38 * len(current) + 90))
        if review["status"] == "completed":
            st.warning("Review đã finalize; kết quả tạm không thể ghi đè snapshot đã khóa.")
        else:
            reason = st.text_area(
                "Lý do lưu Peer Snapshot *",
                key=f"peer_snapshot_reason_{review['id']}",
                help="Ví dụ: Cập nhật peer cùng phân ngành sau BCTC Q2/2026; dùng làm evidence cho Q19/Q26.",
            )
            if st.button(
                "Lưu phiên bản Peer Snapshot vào review",
                type="primary",
                use_container_width=True,
                key=f"save_peer_snapshot_{review['id']}",
                disabled=not reason.strip(),
            ):
                try:
                    version = save_peer_snapshot(
                        repo,
                        company_ref_id=company_ref_id,
                        review_id=int(review["id"]),
                        result=current,
                        base_ticker=base_ticker,
                        target_mos_pct=st.session_state.get("target_mos_pct"),
                        save_reason=reason,
                        actor=actor,
                    )
                    st.success(f"Đã lưu Peer Snapshot v{version}; assessment Q01–Q59 không bị thay đổi.")
                except ValidationError as exc:
                    st.error(str(exc))

    history = list_peer_snapshots(repo, int(review["id"]))
    if history:
        with st.expander("Lịch sử phiên bản Peer Snapshot", expanded=False):
            st.dataframe(pd.DataFrame(history), use_container_width=True, hide_index=True)


__all__ = ["render_peer_snapshot"]
