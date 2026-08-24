"""module_topdown_dashboard.py — Giao diện module Phân tích Top-Down theo ngành.

Thiết kế bám đúng format app Trecapital hiện tại để có thể ghép thẳng vào một page:
    - Cùng header thương hiệu (logo + hero card)
    - Cùng ngôn ngữ màu (teal #0B7F75, vàng #F5B21B, đỏ #B91C1C)
    - Cùng kiểu bảng có ghi chú giải thích khi click
    - Cùng cơ chế điều hướng sidebar bằng st.page_link

Cách tích hợp vào app Trecapital: copy các file module_topdown_*.py, tre_log.py và
thư mục configs/ vào thư mục gốc của app, sau đó tạo file
pages/05_Phan_tich_TopDown_Nganh.py với nội dung:

    from module_topdown_dashboard import render_dashboard
    from tre_full_width import apply_full_width
    render_dashboard()
    apply_full_width()
"""

from __future__ import annotations

import base64
import hashlib
import html
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import module_topdown_engine as E
from tre_log import clear_memory_log, log_event, memory_log_rows

APP_ROOT = Path(__file__).resolve().parent
LOGO_PATH = APP_ROOT / "assets" / "trecapital_logo.png"

st.set_page_config(
    page_title=E.APP_NAME,
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ======================================================================================
# A. Lớp giao diện dùng chung
# ======================================================================================


def _logo_data_uri() -> str:
    try:
        if LOGO_PATH.exists():
            return "data:image/png;base64," + base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
    except Exception:  # noqa: BLE001
        log_event("WARNING", "ui", "Không đọc được logo Trecapital.")
    return ""


def _render_brand_page_header(title: str, subtitle: str) -> None:
    logo_uri = _logo_data_uri()
    logo_html = f"<img src='{logo_uri}' alt='Trecapital' class='page-logo-img'>" if logo_uri else ""
    st.markdown(
        f"""
        <div class="page-brand-shell">
          <div class="page-logo-wrap">{logo_html}</div>
          <div class="hero-card page-hero-card">
            <h1>{html.escape(title)}</h1>
            <p>{html.escape(subtitle)}</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _markdownish_to_html(text: object) -> str:
    raw = "" if text is None else str(text)
    escaped = html.escape(raw.replace("\r\n", "\n").replace("\r", "\n"))
    escaped = escaped.replace("**", "")
    return escaped.replace("\n", "<br>")


def _render_important_red(title: str, body: object) -> None:
    st.markdown(
        f"""
        <div class="important-red" style="color:#B91C1C !important;font-size:1.06rem;line-height:1.65;font-weight:800;
             background:linear-gradient(180deg,#FFF1F2 0%,#FEF2F2 100%);border:2px solid rgba(220,38,38,.34);
             border-left:10px solid #DC2626;padding:16px 18px;border-radius:16px;margin:12px 0 16px 0;
             box-shadow:0 8px 22px rgba(185,28,28,.10);">
            <div style="color:#991B1B;font-size:1.20rem;font-weight:950;margin-bottom:8px;">{html.escape(str(title))}</div>
            <div>{_markdownish_to_html(body)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_warning_card(title: str, body: object) -> None:
    st.markdown(
        f"""
        <div class="big-warning-card" style="border:2px solid #F5B21B;border-left:10px solid #F5B21B;border-radius:16px;
             padding:14px 16px;background:linear-gradient(135deg,#FFF7E6 0%,#FEF3C7 100%);margin:12px 0 16px 0;
             box-shadow:0 8px 22px rgba(245,178,27,.13);">
            <div style="font-size:1.06rem;font-weight:950;color:#8A5A00;margin-bottom:7px;">{html.escape(str(title))}</div>
            <div style="font-size:.95rem;font-weight:700;color:#5F3B00;line-height:1.55;">{_markdownish_to_html(body)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_ok_card(title: str, body: object) -> None:
    st.markdown(
        f"""
        <div class="ok-card" style="border:2px solid #0B7F75;border-left:10px solid #0B7F75;border-radius:16px;
             padding:14px 16px;background:linear-gradient(135deg,#ECFDF5 0%,#F0FDF4 100%);margin:12px 0 16px 0;
             box-shadow:0 8px 22px rgba(11,127,117,.12);">
            <div style="font-size:1.06rem;font-weight:950;color:#065F46;margin-bottom:7px;">{html.escape(str(title))}</div>
            <div style="font-size:.95rem;font-weight:700;color:#064E47;line-height:1.55;">{_markdownish_to_html(body)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _inject_runtime_ui_css() -> None:
    """CSS phải inject trong render_dashboard(), không để ở top-level import.

    Lý do giống module 1 và 2 của Trecapital: Streamlit cache module Python, khi widget
    gây rerun thì phần import không chạy lại và style sẽ biến mất.
    """
    st.markdown(
        """
        <style>
        :root {
            --tre-teal:#0B7F75; --tre-teal-dark:#064E47; --tre-teal-soft:#EAF7F1;
            --tre-yellow:#F5B21B; --tre-red:#B91C1C; --tre-emerald:#10B981;
        }
        .main .block-container {padding-top:1rem !important; padding-bottom:2rem !important; max-width:none !important; width:100% !important;}
        .stApp {background: radial-gradient(circle at 10% 0%, rgba(11,127,117,.08), transparent 28%),
                            linear-gradient(180deg,#F7FBF8 0%,#FFFFFF 60%) !important;}
        section[data-testid="stSidebar"] {background: linear-gradient(180deg,#EAF7F1 0%,#FFFFFF 72%) !important;
                                          border-right:1px solid rgba(11,127,117,.14) !important;}
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] {display:none !important;}

        div[data-testid="stPageLink"] a {
            border:1.7px solid rgba(11,127,117,.28) !important; border-radius:17px !important;
            margin:6px 0 !important; padding:11px 14px !important;
            background: linear-gradient(135deg, rgba(255,255,255,.95), rgba(248,255,251,.88)) !important;
            color:#064E47 !important; font-weight:900 !important; text-decoration:none !important;
            box-shadow:0 7px 17px rgba(11,127,117,.08) !important;
        }
        div[data-testid="stPageLink"] a:hover {
            border-color:#F5B21B !important;
            background: linear-gradient(135deg,#F8FFFB 0%,#FFF7E6 100%) !important;
            color:#0B5F58 !important; box-shadow:0 10px 22px rgba(11,127,117,.16) !important;
        }

        .page-brand-shell {display:grid !important; grid-template-columns:134px minmax(0,1fr) !important;
                           gap:18px !important; align-items:stretch !important; margin:8px 0 22px 0 !important;}
        .page-logo-wrap {min-height:124px !important; display:flex !important; align-items:center !important;
                         justify-content:center !important; border-radius:18px !important;
                         background:linear-gradient(135deg,#FFF7E6 0%,#EAF7F1 100%) !important;
                         border:2.6px solid #0B7F75 !important; border-bottom:4px solid rgba(6,78,71,.38) !important;
                         box-shadow:0 12px 30px rgba(11,127,117,.16) !important;}
        .page-logo-img {max-height:104px !important; max-width:108px !important; object-fit:contain !important;}
        .hero-card {padding:26px 32px !important; border-radius:16px !important;
                    background:linear-gradient(135deg,#064E47 0%,#0B7F75 72%,#12695F 100%) !important;
                    border-left:8px solid #F5B21B !important; color:#FFFFFF !important;
                    box-shadow:0 18px 40px rgba(11,127,117,.22) !important;}
        .page-hero-card {min-height:124px !important; display:flex !important; flex-direction:column !important; justify-content:center !important;}
        .hero-card h1 {color:#FFFFFF !important; font-size:1.98rem !important; line-height:1.16 !important; margin:0 0 8px 0 !important; font-weight:900 !important;}
        .hero-card p {color:rgba(255,255,255,.90) !important; font-size:1.0rem !important; line-height:1.55 !important; margin:0 !important;}

        div[data-testid="stTabs"] div[role="tablist"] {
            gap:6px !important; min-height:58px !important; padding:8px !important; margin:12px 0 20px 0 !important;
            background:#FFFFFF !important; border:1px solid rgba(11,127,117,.20) !important; border-radius:14px !important;
            box-shadow:0 10px 22px rgba(11,127,117,.06) !important; flex-wrap:wrap !important;
        }
        button[role="tab"] {
            min-height:44px !important; padding:0 16px !important; border-radius:11px !important;
            border:1.8px solid rgba(245,178,27,.50) !important; border-bottom:4px solid rgba(11,127,117,.32) !important;
            background:linear-gradient(135deg,#FFF6D8 0%,#EAF5EC 100%) !important;
            color:#064E47 !important; -webkit-text-fill-color:#064E47 !important; font-weight:800 !important;
        }
        button[role="tab"]:hover {background:linear-gradient(135deg,#FFE8A3 0%,#D8F3E4 100%) !important; border-color:#F5B21B !important;}
        button[role="tab"][aria-selected="true"] {
            background:linear-gradient(135deg,#064E47 0%,#0B7F75 72%,#F5B21B 155%) !important;
            color:#FFFFFF !important; -webkit-text-fill-color:#FFFFFF !important; border-color:#F5B21B !important;
        }
        button[role="tab"] p, button[role="tab"] span {color:inherit !important; -webkit-text-fill-color:inherit !important; font-weight:820 !important;}
        div[data-baseweb="tab-highlight"], div[data-baseweb="tab-border"] {display:none !important;}

        div.stButton > button, div[data-testid="stDownloadButton"] > button {
            border-radius:11px !important; border:1px solid #064E47 !important; background:#064E47 !important;
            color:#FFFFFF !important; -webkit-text-fill-color:#FFFFFF !important; font-weight:820 !important;
        }
        div.stButton > button:hover, div[data-testid="stDownloadButton"] > button:hover {
            background:#FFFFFF !important; color:#064E47 !important; -webkit-text-fill-color:#064E47 !important;
            border-color:#F5B21B !important; box-shadow:inset 0 -3px 0 #F5B21B !important;
        }
        div.stButton > button *, div[data-testid="stDownloadButton"] > button * {color:inherit !important; -webkit-text-fill-color:inherit !important;}

        div[data-testid="stMetric"] {border-radius:14px !important; background:#FFFFFF !important;
                                     border:1px solid rgba(11,127,117,.18) !important; padding:14px 16px !important;
                                     box-shadow:0 8px 20px rgba(11,127,117,.06) !important;}
        div[data-testid="stMetricValue"] {color:#064E47 !important; font-weight:900 !important;}

        div[data-testid="stDataFrame"] [role="columnheader"] {
            position:sticky !important; top:0 !important; z-index:50 !important;
            background:#EAF7F1 !important; color:#064E47 !important; font-weight:900 !important;
        }
        .tre-section-title {font-size:1.16rem; font-weight:950; color:#064E47; margin:16px 0 8px 0;
                            padding-left:11px; border-left:6px solid #F5B21B;}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ======================================================================================
# B. Bảng có ghi chú: click đôi để hiện note + quét chọn thuật ngữ để hiện diễn giải
# ======================================================================================

# Bảng màu heatmap theo mức độ quan trọng (nguyên tắc số 8).
_HEAT_CSS = """
      td.heat-green-strong {background:#047857 !important; color:#FFFFFF !important; font-weight:950 !important;}
      td.heat-green        {background:#A7F3D0 !important; color:#064E3B !important; font-weight:900 !important;}
      td.heat-yellow       {background:#FEF3C7 !important; color:#92400E !important; font-weight:900 !important;}
      td.heat-orange       {background:#FED7AA !important; color:#9A3412 !important; font-weight:900 !important;}
      td.heat-red          {background:#FECACA !important; color:#7F1D1D !important; font-weight:900 !important;}
      td.sig-ok            {background:#D1FAE5 !important; color:#065F46 !important; font-weight:900 !important; border-left:4px solid #059669;}
      td.sig-warn          {background:#FEF3C7 !important; color:#92400E !important; font-weight:900 !important; border-left:4px solid #F59E0B;}
      td.sig-bad           {background:#FEE2E2 !important; color:#991B1B !important; font-weight:900 !important; border-left:4px solid #EF4444;}
"""


def _num(value):
    try:
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).replace(",", "").replace("%", "").strip()
        if not text or text in {"-", "--", "N/A", "None", "nan"}:
            return None
        return float(text)
    except Exception:
        return None


def _grad_color(value: float, vmax_pos: float, vmax_neg: float) -> str:
    """Nguyên tắc số 5: âm màu đỏ (âm càng lớn càng đậm), dương màu xanh ngọc lục bảo."""
    if value is None:
        return ""
    if value < 0:
        alpha = min(0.70, 0.12 + 0.58 * min(abs(value) / max(vmax_neg, 1e-9), 1.0))
        return f"background-color:rgba(239,68,68,{alpha:.2f}); color:#7F1D1D; font-weight:700;"
    if value > 0:
        alpha = min(0.62, 0.10 + 0.52 * min(value / max(vmax_pos, 1e-9), 1.0))
        return f"background-color:rgba(16,185,129,{alpha:.2f}); color:#064E3B; font-weight:700;"
    return ""


_COT_SO_DUONG_AM = {"Độ nhạy", "Triển vọng", "Đóng góp", "Độ lệch điểm %", "Điểm tinh chỉnh"}
_COT_DIEM_HEAT = {"Điểm tổng hợp", "Điểm kinh tế", "Điểm chính trị", "Điểm tâm lý", "Điểm chu kỳ", "Điểm sau tinh chỉnh", "Điểm thừa hưởng"}
_COT_TIN_HIEU = {
    "Khuyến nghị",
    "Phân bổ thực tế",
    "Tình trạng",
    "Kết quả",
    "Mức độ",
    "Tính chất",
}


def _class_diem(value) -> str:
    v = _num(value)
    if v is None:
        return ""
    if v >= 80:
        return "heat-green-strong"
    if v >= 65:
        return "heat-green"
    if v >= 45:
        return "heat-yellow"
    if v >= 30:
        return "heat-orange"
    return "heat-red"


def _class_tin_hieu(value) -> str:
    t = str(value or "").strip().lower()
    if not t:
        return ""
    if any(k in t for k in ["tăng tỷ trọng mạnh"]):
        return "heat-green-strong"
    if any(k in t for k in ["tăng tỷ trọng", "đạt", "phòng thủ"]):
        return "sig-ok" if t in {"đạt"} else "heat-green"
    if any(k in t for k in ["trung lập", "chưa nhập", "trung bình"]):
        return "heat-yellow"
    if any(k in t for k in ["giảm tỷ trọng mạnh", "không đạt", "cảnh báo"]):
        return "heat-red" if "mạnh" in t else "sig-bad"
    if "giảm tỷ trọng" in t:
        return "heat-orange"
    if t == "cao":
        return "sig-bad"
    if t == "thấp":
        return "sig-ok"
    return ""


def _fmt_cell(col: str, value) -> str:
    """Định dạng hiển thị theo nguyên tắc số 4."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "N/A" if any(k in col for k in ["%", "lần", "tỷ đồng", "Điểm", "Độ nhạy", "Triển vọng", "Đóng góp"]) else ""
    c = str(col)
    if "%" in c or c.startswith("Điểm"):
        return E.fmt_pct(value)
    if "(lần)" in c or c in {"Hệ số tilt", "Độ nhạy", "Triển vọng", "Đóng góp", "Điểm tinh chỉnh"}:
        return E.fmt_ratio(value)
    if "tỷ đồng" in c:
        return E.fmt_ty(value)
    if c in {"STT", "Xếp hạng", "Số ngành cấp 3"}:
        v = _num(value)
        return f"{int(v)}" if v is not None else ""
    return str(value)


def render_bang_giai_thich(
    df: pd.DataFrame,
    notes: list[str],
    table_key: str,
    height: int = 420,
    hint: str = "Nhấp đôi vào một dòng để xem diễn giải chi tiết. Quét chọn một thuật ngữ bất kỳ để hiện chú thích.",
) -> None:
    """Bảng HTML: click đôi vào dòng → hiện note; quét chọn chữ → hiện diễn giải thuật ngữ.

    Đây là hiện thực của nguyên tắc số 6 (click đôi để xem note có số liệu cụ thể) và
    nguyên tắc số 9 (quét chọn thuật ngữ để hiện diễn giải dạng comment).
    """
    if df is None or df.empty:
        st.info("Chưa có dữ liệu để hiển thị.")
        return

    display_df = df.drop(columns=[c for c in df.columns if str(c).startswith("_")], errors="ignore")

    # Tính biên độ để tô gradient cho các cột dương/âm.
    grad_ranges: dict[str, tuple[float, float]] = {}
    for c in display_df.columns:
        if c in _COT_SO_DUONG_AM:
            vals = [v for v in (_num(x) for x in display_df[c]) if v is not None]
            grad_ranges[c] = (
                max([v for v in vals if v > 0], default=1.0),
                abs(min([v for v in vals if v < 0], default=-1.0)),
            )

    headers = "".join(f"<th>{html.escape(str(c))}</th>" for c in display_df.columns)
    rows_html = []
    for i, (_, row) in enumerate(display_df.iterrows()):
        tds = []
        for c in display_df.columns:
            raw = row.get(c)
            text = _fmt_cell(c, raw)
            cls, style = "", ""
            if c in _COT_DIEM_HEAT:
                cls = _class_diem(raw)
            elif c in _COT_TIN_HIEU:
                cls = _class_tin_hieu(raw)
            elif c in grad_ranges:
                style = _grad_color(_num(raw), *grad_ranges[c])
            tds.append(f"<td class='{cls}' style='{style}'>{html.escape(text)}</td>")
        note = notes[i] if i < len(notes) else "Chưa có ghi chú cho dòng này."
        rows_html.append(
            f"<tr data-note='{html.escape(json.dumps(note, ensure_ascii=False), quote=True)}'>{''.join(tds)}</tr>"
        )

    tid = "tbl_" + str(abs(hash((table_key, tuple(display_df.columns), len(display_df)))))[:10]
    glossary_json = json.dumps(E.glossary_terms(), ensure_ascii=False)
    component_height = min(max(height + 300, 520), 1200)

    html_doc = f"""
    <div class='hint'>{html.escape(hint)}</div>
    <div class='wrap'>
      <table id='{tid}'>
        <thead><tr>{headers}</tr></thead>
        <tbody>{''.join(rows_html)}</tbody>
      </table>
    </div>
    <div id='{tid}_note' class='note'>Chưa chọn chỉ tiêu. Hãy nhấp đôi vào một dòng trong bảng để xem diễn giải.</div>
    <div id='{tid}_tip' class='termtip'></div>
    <script>
      (function() {{
        const GLOSSARY = {glossary_json};
        const table = document.getElementById('{tid}');
        const note  = document.getElementById('{tid}_note');
        const tip   = document.getElementById('{tid}_tip');

        function showNote(row) {{
          table.querySelectorAll('tbody tr').forEach(r => r.classList.remove('selected'));
          row.classList.add('selected');
          let raw = row.getAttribute('data-note') || '""';
          let msg = '';
          try {{ msg = JSON.parse(raw); }} catch(e) {{ msg = raw; }}
          note.innerText = msg;
        }}

        if (table && note) {{
          table.querySelectorAll('tbody tr').forEach(function(row) {{
            // Nguyên tắc số 6: click đôi để hiện note.
            row.addEventListener('dblclick', function() {{ showNote(row); }});
            // Giữ thêm click đơn cho thiết bị cảm ứng, không phá hành vi click đôi.
            row.addEventListener('click', function() {{ showNote(row); }});
          }});
        }}

        // Nguyên tắc số 9: quét chọn thuật ngữ -> hiện diễn giải dạng comment.
        function lookupTerm(text) {{
          if (!text) return null;
          const s = text.trim().replace(/\\s+/g, ' ');
          if (s.length < 2 || s.length > 60) return null;
          if (GLOSSARY[s]) return [s, GLOSSARY[s]];
          const lower = s.toLowerCase();
          for (const k in GLOSSARY) {{
            if (k.toLowerCase() === lower) return [k, GLOSSARY[k]];
          }}
          for (const k in GLOSSARY) {{
            if (lower.indexOf(k.toLowerCase()) >= 0 && k.length >= 3) return [k, GLOSSARY[k]];
          }}
          return null;
        }}

        document.addEventListener('mouseup', function(ev) {{
          const sel = window.getSelection();
          const text = sel ? sel.toString() : '';
          const hit = lookupTerm(text);
          if (!hit) {{ tip.style.display = 'none'; return; }}
          tip.innerHTML = "<div class='termtip-title'>" + hit[0] + "</div><div>" + hit[1] + "</div>";
          tip.style.display = 'block';
          const maxLeft = Math.max(8, (document.body.clientWidth || 900) - 380);
          tip.style.left = Math.min(ev.pageX + 12, maxLeft) + 'px';
          tip.style.top  = (ev.pageY + 12) + 'px';
        }});

        document.addEventListener('mousedown', function(ev) {{
          if (tip && !tip.contains(ev.target)) tip.style.display = 'none';
        }});
      }})();
    </script>
    <style>
      body {{font-family: system-ui, -apple-system, 'Segoe UI', sans-serif;}}
      .hint {{font-size:13px; color:#0B7F75; margin:2px 0 8px 0; font-weight:700;}}
      .wrap {{max-height:{height}px; overflow:auto; border:1px solid #E2E8F0; border-radius:12px; background:#FFFFFF;}}
      table {{border-collapse:collapse; width:100%; font-size:13px;}}
      th {{position:sticky; top:0; background:#EAF7F1; color:#123D3A; text-align:left; padding:8px;
           border-bottom:1px solid #E2E8F0; z-index:8; font-weight:950; box-shadow:0 2px 0 rgba(11,127,117,.18); white-space:nowrap;}}
      td {{border-bottom:1px solid #EDF2F7; padding:7px 8px; vertical-align:top; color:#123D3A; line-height:1.40;}}
      tbody tr:nth-child(even) td {{background:#FBFDFB;}}
      tr:hover td {{background:#F7FBF8; cursor:pointer;}}
      tr.selected td {{outline:2px solid #F5B21B; outline-offset:-2px;}}
{_HEAT_CSS}
      .note {{white-space:pre-wrap; margin-top:10px; padding:13px 15px; border-radius:14px; background:#FFF7E6;
              border:1px solid rgba(245,178,27,.52); color:#5F3B00; font-size:13px; line-height:1.52;
              max-height:300px; overflow-y:auto;}}
      .termtip {{display:none; position:absolute; z-index:9999; max-width:360px; padding:11px 13px; border-radius:12px;
                 background:#FFFDF5; border:2px solid #F5B21B; box-shadow:0 12px 28px rgba(11,127,117,.20);
                 font-size:12.5px; line-height:1.5; color:#3F2D06;}}
      .termtip-title {{font-weight:950; color:#064E47; margin-bottom:5px; font-size:13px;}}
    </style>
    """
    components.html(html_doc, height=component_height, scrolling=True)


def render_bang_tinh(df: pd.DataFrame, height: int = 320) -> None:
    """Bảng đọc nhanh không có note, dùng cho các bảng tra cứu ngắn."""
    if df is None or df.empty:
        st.info("Chưa có dữ liệu.")
        return
    st.dataframe(df, use_container_width=True, height=height, hide_index=True)


def render_bang_thuat_ngu(df: pd.DataFrame) -> None:
    """Render glossary with fully wrapped text and no clipped description cells on tablets."""
    if df is None or df.empty:
        st.info("Chưa có dữ liệu.")
        return
    table_html = df.to_html(index=False, escape=True, border=0, classes=["tre-glossary-table"])
    st.html(
        f"""
        <style>
          .tre-glossary-wrap{{
            width:100%;max-width:100%;overflow-x:auto;-webkit-overflow-scrolling:touch;
            margin:.35rem 0 1rem;border:1px solid #D8E5DF;border-radius:.6rem;background:#FFFFFF;
          }}
          table.tre-glossary-table{{
            width:100%;max-width:100%;table-layout:fixed;border-collapse:collapse;
            font-size:.84rem;line-height:1.42;color:#123D3A;
          }}
          table.tre-glossary-table th{{
            position:sticky;top:0;z-index:2;background:#EAF7F1;color:#123D3A;font-weight:900;
            padding:.55rem;border:1px solid #D8E5DF;white-space:normal!important;
            word-break:normal;overflow-wrap:anywhere;vertical-align:top;
          }}
          table.tre-glossary-table td{{
            padding:.52rem;border:1px solid #E5EDEA;white-space:normal!important;
            word-break:normal;overflow-wrap:anywhere;vertical-align:top;
          }}
          table.tre-glossary-table th:nth-child(1),table.tre-glossary-table td:nth-child(1){{
            width:6%;text-align:center;
          }}
          table.tre-glossary-table th:nth-child(2),table.tre-glossary-table td:nth-child(2){{width:22%;}}
          table.tre-glossary-table th:nth-child(3),table.tre-glossary-table td:nth-child(3){{width:72%;}}
          table.tre-glossary-table tbody tr:nth-child(even){{background:#FBFDFB;}}
          @media (max-width:760px){{
            table.tre-glossary-table{{font-size:.78rem;}}
            table.tre-glossary-table th,table.tre-glossary-table td{{padding:.42rem;}}
            table.tre-glossary-table th:nth-child(1),table.tre-glossary-table td:nth-child(1){{width:9%;}}
            table.tre-glossary-table th:nth-child(2),table.tre-glossary-table td:nth-child(2){{width:27%;}}
            table.tre-glossary-table th:nth-child(3),table.tre-glossary-table td:nth-child(3){{width:64%;}}
          }}
        </style>
        <div class="tre-glossary-wrap">{table_html}</div>
        """
    )


# ======================================================================================
# C. Trạng thái phiên (đồng bộ tuyệt đối giữa các bước — nguyên tắc số 7)
# ======================================================================================

SS_TRIEN_VONG = "topdown_trien_vong"
SS_PHA = "topdown_pha_chu_ky"
SS_BM_ID = "topdown_benchmark_id"
SS_BM_W = "topdown_benchmark_weights"
SS_LECH = "topdown_lech_toi_da"
SS_TRONG_SO = "topdown_trong_so"
SS_NGANH_CHON = "topdown_nganh_dang_chon"
SS_SANG_LOC = "topdown_bang_sang_loc"


def _init_state() -> None:
    d = E.default_input()
    st.session_state.setdefault(SS_TRIEN_VONG, dict(d.trien_vong_driver))
    st.session_state.setdefault(SS_PHA, d.pha_chu_ky)
    st.session_state.setdefault(SS_BM_ID, d.benchmark_id)
    st.session_state.setdefault(SS_BM_W, dict(d.benchmark_weights))
    st.session_state.setdefault(SS_LECH, d.lech_toi_da)
    st.session_state.setdefault(SS_TRONG_SO, dict(d.trong_so))
    st.session_state.setdefault(SS_NGANH_CHON, E.sector_codes()[0] if E.sector_codes() else "FIN")
    st.session_state.setdefault(SS_SANG_LOC, E.mau_bang_sang_loc(8))


def _current_input() -> E.TopDownInput:
    """Một nguồn sự thật duy nhất cho mọi tab — đây là cách app đảm bảo đồng bộ dữ liệu."""
    return E.TopDownInput(
        trien_vong_driver=dict(st.session_state.get(SS_TRIEN_VONG, {})),
        pha_chu_ky=st.session_state.get(SS_PHA, "mid"),
        benchmark_id=st.session_state.get(SS_BM_ID, ""),
        benchmark_weights=dict(st.session_state.get(SS_BM_W, {})),
        lech_toi_da=float(st.session_state.get(SS_LECH, 8.0)),
        trong_so=dict(st.session_state.get(SS_TRONG_SO, {})),
    )


def _governed_snapshot_payload(
    inp: E.TopDownInput,
    diem_df: pd.DataFrame,
    tt_df: pd.DataFrame,
    kt_df: pd.DataFrame,
) -> dict:
    """Build the versioned, source-traceable payload consumed by Investment Checklist.

    This is context only. It contains no ticker-level assessment and no buy/sell decision.
    """
    bm_meta = next(
        (b for b in E.benchmark_config().get("benchmarks", []) if b.get("id") == inp.benchmark_id),
        {},
    )
    source_mapping_path = APP_ROOT / "docs" / "SOURCE_MAPPING_FISHER.md"
    source_mapping_hash = hashlib.sha256(source_mapping_path.read_bytes()).hexdigest()
    ranking = [
        {
            "rank": int(row["Xếp hạng"]),
            "sector_code": str(row["Mã ngành"]),
            "sector_name": str(row["Ngành"]),
            "character": str(row.get("Tính chất", "")),
            "economy_score": float(row["Điểm kinh tế"]),
            "politics_score": float(row["Điểm chính trị"]),
            "sentiment_score": float(row["Điểm tâm lý"]),
            "cycle_score": float(row["Điểm chu kỳ"]),
            "score": float(row["Điểm tổng hợp"]),
        }
        for _, row in diem_df.iterrows()
    ]
    weights = [
        {
            "sector_code": str(row["Mã ngành"]),
            "sector_name": str(row["Ngành"]),
            "sector_score": float(row["Điểm tổng hợp"]),
            "signal": str(row["Khuyến nghị"]),
            "tilt_factor": float(row["Hệ số tilt"]),
            "benchmark_weight_pct": float(row["Tỷ trọng benchmark %"]),
            "proposed_weight_pct": float(row["Tỷ trọng đề xuất %"]),
            "tilt_pct": float(row["Độ lệch điểm %"]),
        }
        for _, row in tt_df.iterrows()
    ]
    checks = kt_df.to_dict("records") if kt_df is not None and not kt_df.empty else []
    return {
        "schema": "trecapital-topdown-sector-context-v1",
        "methodology_version": E.APP_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cycle_phase": inp.pha_chu_ky,
        "benchmark": {
            "id": inp.benchmark_id,
            "name": str(bm_meta.get("ten", inp.benchmark_id)),
            "reliability_note": str(bm_meta.get("do_tin_cay", "")),
            "requires_update": bool(bm_meta.get("can_nguoi_dung_cap_nhat", True)),
            "weights": {str(key): float(value) for key, value in inp.benchmark_weights.items()},
        },
        "parameters": {
            "max_deviation_pct": float(inp.lech_toi_da),
            "scoring_weights": {str(key): float(value) for key, value in inp.trong_so.items()},
            "driver_outlook": {str(key): float(value) for key, value in inp.trien_vong_driver.items()},
        },
        "ranking": ranking,
        "weights": weights,
        "sync_checks": checks,
        "source_mapping_sha256": source_mapping_hash,
    }


def _bridge_to_other_modules(
    inp: E.TopDownInput,
    diem_df: pd.DataFrame,
    tt_df: pd.DataFrame,
    kt_df: pd.DataFrame,
) -> None:
    """Đẩy kết quả sang session chung để module 1, 2, 3 của Trecapital dùng lại."""
    try:
        st.session_state["topdown_ranking"] = diem_df.to_dict("records")
        st.session_state["topdown_weights"] = tt_df.to_dict("records")
        if not diem_df.empty:
            top = diem_df.iloc[0]
            st.session_state["topdown_top_sector_code"] = top["Mã ngành"]
            st.session_state["topdown_top_sector_name"] = top["Ngành"]
        st.session_state["topdown_cycle_phase"] = st.session_state.get(SS_PHA)
        st.session_state["topdown_governed_snapshot_payload"] = _governed_snapshot_payload(
            inp, diem_df, tt_df, kt_df
        )
        log_event("DEBUG", "sync", "Đã đẩy kết quả top-down sang session dùng chung.")
    except Exception as exc:  # noqa: BLE001
        log_event("ERROR", "sync", f"Không đồng bộ được sang session chung: {exc}")


# ======================================================================================
# D. Sidebar
# ======================================================================================


def _render_sidebar() -> None:
    with st.sidebar:
        try:
            from tre_sidebar_nav import render_tre_sidebar_nav

            render_tre_sidebar_nav()
        except Exception:  # noqa: BLE001
            st.markdown("### 🧭 Trecapital")
            st.page_link("app.py", label="Phân tích Top-Down theo ngành", icon="🧭")

        st.divider()
        st.markdown("#### ⚙️ Tham số phân tích")

        # 1. Pha chu kỳ
        phases = E.cycle_config().get("pha_chu_ky", [])
        ids = [p["id"] for p in phases]
        labels = {p["id"]: p["ten_vi"] for p in phases}
        cur = st.session_state.get(SS_PHA, "mid")
        idx = ids.index(cur) if cur in ids else 0
        chosen = st.selectbox("Pha chu kỳ kinh tế", ids, index=idx, format_func=lambda x: labels.get(x, x), key="sb_pha")
        if chosen != st.session_state.get(SS_PHA):
            st.session_state[SS_PHA] = chosen
            log_event("INFO", "ui", f"Người dùng đổi pha chu kỳ sang: {labels.get(chosen, chosen)}")

        # 2. Benchmark
        bms = E.benchmark_config().get("benchmarks", [])
        bm_ids = [b["id"] for b in bms]
        bm_labels = {b["id"]: b["ten"] for b in bms}
        cur_bm = st.session_state.get(SS_BM_ID, bm_ids[0] if bm_ids else "")
        bidx = bm_ids.index(cur_bm) if cur_bm in bm_ids else 0
        new_bm = st.selectbox("Benchmark tham chiếu", bm_ids, index=bidx, format_func=lambda x: bm_labels.get(x, x), key="sb_bm")
        if new_bm != st.session_state.get(SS_BM_ID):
            st.session_state[SS_BM_ID] = new_bm
            bm = next((b for b in bms if b["id"] == new_bm), {})
            st.session_state[SS_BM_W] = dict(bm.get("ty_trong", {}))
            log_event("INFO", "ui", f"Đổi benchmark sang: {bm_labels.get(new_bm, new_bm)}")

        bm_meta = next((b for b in bms if b["id"] == st.session_state.get(SS_BM_ID)), {})
        if bm_meta.get("can_nguoi_dung_cap_nhat", False):
            st.warning("Benchmark này là giá trị khởi tạo, chưa kiểm chứng. Hãy cập nhật ở tab Tỷ trọng danh mục.", icon="⚠️")

        # 3. Giới hạn độ lệch
        st.session_state[SS_LECH] = float(
            st.slider("Độ lệch tối đa so với benchmark (điểm %)", 1.0, 20.0, float(st.session_state.get(SS_LECH, 8.0)), 0.5)
        )

        st.divider()
        st.markdown("#### ⚖️ Trọng số điểm ngành")
        ts = dict(st.session_state.get(SS_TRONG_SO, {}))
        ts["driver_kinh_te"] = float(st.slider("Driver kinh tế", 0.0, 100.0, float(ts.get("driver_kinh_te", 40.0)), 5.0))
        ts["driver_chinh_tri"] = float(st.slider("Driver chính trị", 0.0, 100.0, float(ts.get("driver_chinh_tri", 20.0)), 5.0))
        ts["driver_tam_ly"] = float(st.slider("Driver tâm lý", 0.0, 100.0, float(ts.get("driver_tam_ly", 20.0)), 5.0))
        ts["vi_the_chu_ky"] = float(st.slider("Vị thế chu kỳ", 0.0, 100.0, float(ts.get("vi_the_chu_ky", 20.0)), 5.0))
        st.session_state[SS_TRONG_SO] = ts
        st.caption(f"Tổng trọng số hiện tại: {E.fmt_ratio(sum(ts.values()))} (app tự chuẩn hóa về 100%).")

        st.divider()
        if st.button("↺ Đặt lại toàn bộ tham số", use_container_width=True):
            for k in [SS_TRIEN_VONG, SS_PHA, SS_BM_ID, SS_BM_W, SS_LECH, SS_TRONG_SO, SS_SANG_LOC]:
                st.session_state.pop(k, None)
            log_event("INFO", "ui", "Người dùng đặt lại toàn bộ tham số.")
            st.rerun()

        st.caption(f"Phiên bản: {E.APP_VERSION}")


# ======================================================================================
# E. Các tab nội dung
# ======================================================================================


def _tab_khung_phuong_phap() -> None:
    st.markdown("<div class='tre-section-title'>Quy trình top-down ba bước</div>", unsafe_allow_html=True)
    cfg = E.scoring_config().get("phan_bo_70_20_10", {})
    c1, c2, c3 = st.columns(3)
    c1.metric("Phân bổ tài sản", E.fmt_pct(cfg.get("asset_allocation", 70)), "Quyết định lớn nhất")
    c2.metric("Phân bổ tiểu nhóm", E.fmt_pct(cfg.get("sub_asset_allocation", 20)), "Ngành / quốc gia / phong cách")
    c3.metric("Lựa chọn cổ phiếu", E.fmt_pct(cfg.get("security_selection", 10)), "Phần nhỏ nhất")

    _render_important_red(
        "Nguyên lý 70 – 20 – 10",
        cfg.get("dien_giai", "")
        + "\n\nHệ quả trực tiếp: dành phần lớn thời gian cho việc chọn ĐÚNG NGÀNH thay vì "
        "dò tìm từng cổ phiếu. App này phục vụ trực tiếp phần 20% và định hướng cho phần 10%.",
    )

    st.markdown("<div class='tre-section-title'>Ba bước và bảy tab của module</div>", unsafe_allow_html=True)
    quy_trinh = pd.DataFrame(
        [
            {
                "Bước": "Bước 1",
                "Tên bước": "Phân tích Portfolio Drivers và chọn ngành",
                "Việc phải làm": "Chấm triển vọng 12 tháng cho từng driver Kinh tế, Chính trị, Tâm lý; xác định pha chu kỳ.",
                "Tab tương ứng": "Portfolio Drivers → Chu kỳ kinh tế → Xếp hạng ngành → Tỷ trọng danh mục",
                "Tỷ trọng đóng góp": 20.0,
            },
            {
                "Bước": "Bước 2",
                "Tên bước": "Sàng lọc định lượng",
                "Việc phải làm": "Thu hẹp danh sách cổ phiếu bằng vốn hóa, định giá, khả năng trả nợ và thanh khoản.",
                "Tab tương ứng": "Đào sâu nhóm ngành → Sàng lọc định lượng",
                "Tỷ trọng đóng góp": 5.0,
            },
            {
                "Bước": "Bước 3",
                "Tên bước": "Lựa chọn cổ phiếu",
                "Việc phải làm": "Phân tích cơ bản 5 bước, tìm thuộc tính chiến lược phù hợp với driver đang thắng thế.",
                "Tab tương ứng": "Phân tích cổ phiếu 5 bước → chuyển sang module Định giá chuyên sâu",
                "Tỷ trọng đóng góp": 10.0,
            },
        ]
    )
    notes = [
        "BƯỚC 1 — PHÂN TÍCH PORTFOLIO DRIVERS\n\n"
        "Đây là bước quan trọng nhất và cũng là bước nhiều nhà đầu tư bỏ qua.\n\n"
        "Ba nhóm driver theo Fisher:\n"
        "  • Kinh tế: GDP, lãi suất, đường cong lãi suất, lạm phát, giá hàng hóa, chu kỳ đầu tư, tín dụng, tỷ giá.\n"
        "  • Chính trị: thuế, quản lý ngành, chính sách thương mại, chính sách công nghiệp, chi ngân sách, kiểm soát giá.\n"
        "  • Tâm lý: mức ngại rủi ro, chu kỳ Value–Growth, định giá tương đối, độ phủ truyền thông, dòng tiền.\n\n"
        "Câu hỏi cốt lõi không phải 'driver này tốt hay xấu' mà là 'driver này sẽ diễn biến KHÁC "
        "với kỳ vọng thị trường đang định giá sẵn hay không'. Thị trường đã phản ánh thông tin phổ biến.\n\n"
        "Đầu ra: bảng xếp hạng 11 ngành và tỷ trọng đề xuất so với benchmark.",
        "BƯỚC 2 — SÀNG LỌC ĐỊNH LƯỢNG\n\n"
        "Mục đích duy nhất là thu hẹp phạm vi để bước 3 làm được. Fisher ví von: quy trình bottom-up "
        "giống mò kim đáy bể; quy trình top-down là tìm đống rơm có mật độ kim cao nhất.\n\n"
        "Bốn lớp sàng lọc theo sơ đồ trong sách:\n"
        "  • Capitalization — vốn hóa tối thiểu\n"
        "  • Valuation — P/E, P/B, P/CF, P/S\n"
        "  • Solvency — đòn bẩy, khả năng trả nợ\n"
        "  • Liquidity — thanh khoản đủ để mua bán\n\n"
        "Độ chặt của bộ lọc hoàn toàn do bạn quyết định. Bộ lọc càng chặt thì danh sách càng ngắn "
        "và bước 3 càng nhẹ, nhưng rủi ro bỏ sót cơ hội càng cao.\n\n"
        "Cảnh báo: vượt qua sàng lọc KHÔNG có nghĩa là nên mua.",
        "BƯỚC 3 — LỰA CHỌN CỔ PHIẾU\n\n"
        "Quy trình 5 bước của Fisher:\n"
        "  1. Hiểu mô hình kinh doanh và động lực lợi nhuận\n"
        "  2. Xác định các thuộc tính chiến lược (lợi thế cạnh tranh)\n"
        "  3. Phân tích cơ bản và diễn biến giá cổ phiếu\n"
        "  4. Nhận diện rủi ro\n"
        "  5. Phân tích định giá và kỳ vọng đồng thuận\n\n"
        "Hai mục tiêu của bước chọn cổ phiếu:\n"
        "  (a) Tìm doanh nghiệp có thuộc tính chiến lược PHÙ HỢP với driver đang thắng thế.\n"
        "  (b) Tối đa hóa xác suất thắng cả NHÓM ngành, chứ không phải cố chọn ra 'mã tốt nhất'.\n\n"
        "Điểm (b) rất phản trực giác nhưng quan trọng: tránh các mã quá dị biệt so với nhóm giúp "
        "giảm rủi ro danh mục trong khi vẫn tạo giá trị ở cấp lựa chọn cổ phiếu.\n\n"
        "Sau bước này, chuyển sang module Tổng quan doanh nghiệp và Định giá chuyên sâu của Trecapital "
        "để định giá và tính biên an toàn.",
    ]
    render_bang_giai_thich(quy_trinh, notes, "quy_trinh", height=260)

    st.markdown("<div class='tre-section-title'>Nguyên tắc benchmark</div>", unsafe_allow_html=True)
    _render_warning_card(
        "Ba điều dễ hiểu sai nhất về benchmark",
        "1. Mục tiêu của danh mục là tối đa hóa XÁC SUẤT THẮNG BENCHMARK, không phải tối đa hóa lợi nhuận "
        "tuyệt đối. Đặt mục tiêu lợi nhuận cố định mỗi năm sẽ gây thất vọng khi thị trường rất mạnh và "
        "phi thực tế khi thị trường rất yếu.\n\n"
        "2. Giảm tỷ trọng KHÔNG có nghĩa là bán hết về 0%. Nếu một ngành chiếm 20% benchmark và bạn bi quan, "
        "bạn có thể giữ 12% — vẫn là quyết định chủ động nhưng giữ được đa dạng hóa.\n\n"
        "3. Độ lệch càng lớn so với benchmark thì benchmark risk càng cao. Chỉ đặt cược lớn khi bạn thực sự "
        "biết điều mà thị trường chưa biết.",
    )


def _tab_drivers() -> None:
    inp = _current_input()
    cfg = E.drivers_config()
    thang = cfg.get("thang_trien_vong", {})

    st.markdown("<div class='tre-section-title'>Bước 1 — Chấm triển vọng 12 tháng cho từng driver</div>", unsafe_allow_html=True)
    st.caption(
        "Thang điểm: −2 rất tiêu cực · −1 tiêu cực · 0 trung tính · +1 tích cực · +2 rất tích cực. "
        "Chấm theo mức độ LỆCH so với kỳ vọng đồng thuận, không phải theo mức tuyệt đối."
    )

    groups = {E.NHOM_KT: [], E.NHOM_CT: [], E.NHOM_TL: []}
    for d in cfg.get("drivers", []):
        groups.setdefault(d.get("nhom", E.NHOM_KT), []).append(d)

    tv = dict(st.session_state.get(SS_TRIEN_VONG, {}))
    changed = False
    for nhom, icon in [(E.NHOM_KT, "📈"), (E.NHOM_CT, "🏛️"), (E.NHOM_TL, "🧠")]:
        with st.expander(f"{icon} Driver {nhom} ({len(groups.get(nhom, []))} yếu tố)", expanded=(nhom == E.NHOM_KT)):
            cols = st.columns(2)
            for i, d in enumerate(groups.get(nhom, [])):
                with cols[i % 2]:
                    old = float(tv.get(d["id"], 0.0))
                    new = st.select_slider(
                        d["ten_vi"],
                        options=[-2.0, -1.0, 0.0, 1.0, 2.0],
                        value=old if old in {-2.0, -1.0, 0.0, 1.0, 2.0} else 0.0,
                        format_func=lambda x: f"{int(x):+d}  {thang.get(str(int(x)), '')}",
                        key=f"drv_{d['id']}",
                    )
                    if new != old:
                        tv[d["id"]] = float(new)
                        changed = True
                    else:
                        tv[d["id"]] = float(new)
    st.session_state[SS_TRIEN_VONG] = tv
    if changed:
        log_event("INFO", "ui", "Người dùng cập nhật triển vọng driver.")

    inp = _current_input()
    st.markdown("<div class='tre-section-title'>Bảng tổng hợp driver và tác động</div>", unsafe_allow_html=True)

    rows, notes = [], []
    sens_map = cfg.get("do_nhay_theo_nganh", {})
    names = E.sector_name_map()
    for d in cfg.get("drivers", []):
        did = d["id"]
        outlook = float(inp.trien_vong_driver.get(did, 0.0))
        tac_dong = {c: float(sens_map.get(c, {}).get(did, 0)) * outlook for c in E.sector_codes()}
        loi_nhat = max(tac_dong.items(), key=lambda x: x[1]) if tac_dong else ("", 0.0)
        hai_nhat = min(tac_dong.items(), key=lambda x: x[1]) if tac_dong else ("", 0.0)
        rows.append(
            {
                "Nhóm": d["nhom"],
                "Driver": d["ten_vi"],
                "Triển vọng": E.round_ratio(outlook),
                "Ngành hưởng lợi nhất": names.get(loi_nhat[0], "—") if loi_nhat[1] > 0 else "—",
                "Đóng góp": E.round_ratio(loi_nhat[1]) if loi_nhat[1] > 0 else 0.0,
                "Ngành chịu thiệt nhất": names.get(hai_nhat[0], "—") if hai_nhat[1] < 0 else "—",
            }
        )
        notes.append(E.note_driver(did, inp))
    render_bang_giai_thich(pd.DataFrame(rows), notes, "drivers", height=440)

    n_active = sum(1 for v in inp.trien_vong_driver.values() if v != 0)
    if n_active == 0:
        _render_warning_card(
            "Chưa chấm driver nào",
            "Toàn bộ driver đang ở mức 0 nên điểm ngành sẽ chỉ phản ánh vị thế chu kỳ. "
            "Hãy chấm ít nhất 5–8 driver mà bạn có quan điểm rõ ràng để bảng xếp hạng ngành có ý nghĩa.",
        )
    else:
        _render_ok_card(
            "Đã có quan điểm driver",
            f"Bạn đã chấm {n_active}/{len(inp.trien_vong_driver)} driver khác 0. "
            "Kết quả đã được đồng bộ sang tất cả các tab còn lại.",
        )


def _tab_chu_ky() -> None:
    inp = _current_input()
    phases = E.cycle_config().get("pha_chu_ky", [])
    cur = next((p for p in phases if p["id"] == inp.pha_chu_ky), {})

    st.markdown("<div class='tre-section-title'>Bước 2 — Định vị chu kỳ kinh tế</div>", unsafe_allow_html=True)
    _render_ok_card(f"Pha đang chọn: {cur.get('ten_vi','')}", cur.get("dac_diem", ""))

    names = E.sector_name_map()
    rows, notes = [], []
    for s in E.sector_list():
        code = s["code"]
        r = {"Mã ngành": code, "Ngành": s["ten_vi"], "Tính chất": s.get("tinh_chat", "")}
        for p in phases:
            r[p["ten_vi"]] = E.round_pct(E.diem_chu_ky(code, p["id"]))
        rows.append(r)
        chi_tiet = "\n".join(
            f"   {p['ten_vi']:<32} điểm {E.fmt_pct(E.diem_chu_ky(code, p['id']))}" for p in phases
        )
        notes.append(
            f"NGÀNH: {s['ten_vi']} — mã {code}\n"
            f"Tính chất: {s.get('tinh_chat','')}\n\n"
            "1) ĐIỂM CHU KỲ QUA CÁC PHA\n"
            f"{chi_tiet}\n\n"
            "2) CÔNG THỨC\n"
            "   điểm chu kỳ = 50 + 50 × điểm_pha / 3, với điểm_pha nằm trong khoảng [−3; +3].\n"
            "   Mốc 50.0% là trung tính: ngành không có lợi thế cũng không bất lợi trong pha đó.\n\n"
            "3) CÁCH ĐỌC\n"
            "   Ngành phòng thủ (Tiêu dùng thiết yếu, Tiện ích, Chăm sóc sức khỏe, Viễn thông) đạt điểm cao\n"
            "   trong pha Suy thoái và thấp trong pha Đầu chu kỳ. Ngành chu kỳ thì ngược lại.\n\n"
            "4) CẢNH BÁO QUAN TRỌNG\n"
            f"   {E.cycle_config().get('_meta', {}).get('canh_bao_quan_trong', '')}"
        )
    render_bang_giai_thich(pd.DataFrame(rows), notes, "chu_ky", height=420)

    st.markdown("<div class='tre-section-title'>Phân loại chu kỳ và phòng thủ</div>", unsafe_allow_html=True)
    pl = E.cycle_config().get("phan_loai_phong_thu_chu_ky", {})
    c1, c2, c3 = st.columns(3)
    for col, key, ten in [
        (c1, "chu_ky_manh", "Chu kỳ mạnh"),
        (c2, "chu_ky_vua", "Chu kỳ vừa"),
        (c3, "phong_thu", "Phòng thủ"),
    ]:
        with col:
            st.markdown(f"**{ten}**")
            for c in pl.get(key, []):
                st.markdown(f"- {names.get(c, c)}")


def _tab_xep_hang(diem_df: pd.DataFrame) -> None:
    inp = _current_input()
    st.markdown("<div class='tre-section-title'>Bước 3 — Xếp hạng 11 ngành</div>", unsafe_allow_html=True)

    if not diem_df.empty:
        top = diem_df.iloc[0]
        bot = diem_df.iloc[-1]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Ngành điểm cao nhất", top["Ngành"], E.fmt_pct(top["Điểm tổng hợp"]))
        c2.metric("Ngành điểm thấp nhất", bot["Ngành"], E.fmt_pct(bot["Điểm tổng hợp"]))
        c3.metric("Điểm trung vị", E.fmt_pct(diem_df["Điểm tổng hợp"].median()))
        c4.metric("Độ phân tán", E.fmt_pct(diem_df["Điểm tổng hợp"].max() - diem_df["Điểm tổng hợp"].min()))

    notes = [E.note_xep_hang_nganh(r.to_dict(), inp) for _, r in diem_df.iterrows()]
    render_bang_giai_thich(diem_df, notes, "xep_hang", height=430)

    st.markdown("<div class='tre-section-title'>Biểu đồ điểm tổng hợp</div>", unsafe_allow_html=True)
    try:
        chart_df = diem_df.set_index("Ngành")[["Điểm kinh tế", "Điểm chính trị", "Điểm tâm lý", "Điểm chu kỳ"]]
        st.bar_chart(chart_df, height=380)
        st.caption("Mốc 50.0% là trung tính. Cột càng cao trên 50 thì trục đó càng thuận lợi cho ngành.")
    except Exception as exc:  # noqa: BLE001
        log_event("ERROR", "ui", f"Lỗi vẽ biểu đồ xếp hạng: {exc}")
        st.info("Không vẽ được biểu đồ với dữ liệu hiện tại.")


def _tab_ty_trong(diem_df: pd.DataFrame, tt_df: pd.DataFrame) -> None:
    inp = _current_input()
    st.markdown("<div class='tre-section-title'>Tỷ trọng danh mục đề xuất so với benchmark</div>", unsafe_allow_html=True)

    bm_meta = next((b for b in E.benchmark_config().get("benchmarks", []) if b["id"] == inp.benchmark_id), {})
    if bm_meta.get("can_nguoi_dung_cap_nhat", False):
        _render_important_red(
            "Cảnh báo chất lượng dữ liệu benchmark",
            f"{bm_meta.get('do_tin_cay','')}\n\n"
            "Toàn bộ tỷ trọng đề xuất bên dưới được nhân từ tỷ trọng benchmark này. "
            "Nếu tỷ trọng benchmark sai thì kết quả cũng sai. Hãy cập nhật ngay bên dưới trước khi dùng.",
        )

    with st.expander("✏️ Cập nhật tỷ trọng benchmark (bắt buộc trước khi ra quyết định)", expanded=False):
        st.caption("Nhập tỷ trọng ngành theo % vốn hóa, lấy từ HOSE hoặc nhà cung cấp dữ liệu chính thống. Tổng phải bằng 100.0%.")
        w = dict(st.session_state.get(SS_BM_W, {}))
        cols = st.columns(3)
        names = E.sector_name_map()
        for i, code in enumerate(E.sector_codes()):
            with cols[i % 3]:
                w[code] = float(
                    st.number_input(
                        f"{names.get(code, code)} ({code})",
                        min_value=0.0,
                        max_value=100.0,
                        value=float(w.get(code, 0.0)),
                        step=0.1,
                        format="%.1f",
                        key=f"bmw_{code}",
                    )
                )
        st.session_state[SS_BM_W] = w
        tong = sum(w.values())
        if abs(tong - 100.0) <= 0.5:
            st.success(f"Tổng tỷ trọng benchmark = {E.fmt_pct(tong)}. Hợp lệ.")
        else:
            st.error(f"Tổng tỷ trọng benchmark = {E.fmt_pct(tong)}, chưa bằng 100.0%. Kết quả sẽ bị lệch.")

    if tt_df.empty:
        st.info("Chưa tính được tỷ trọng.")
        return

    n_tang = int((tt_df["Độ lệch điểm %"] > 0.05).sum())
    n_giam = int((tt_df["Độ lệch điểm %"] < -0.05).sum())
    c1, c2, c3 = st.columns(3)
    c1.metric("Số ngành tăng tỷ trọng", f"{n_tang}")
    c2.metric("Số ngành giảm tỷ trọng", f"{n_giam}")
    c3.metric("Tổng tỷ trọng đề xuất", E.fmt_pct(tt_df["Tỷ trọng đề xuất %"].sum()))
    st.caption(
        "`Khuyến nghị` là tín hiệu từ điểm ngành và hệ số tilt trước chuẩn hóa. "
        "`Phân bổ thực tế` được xác định từ tỷ trọng cuối cùng sau khi danh mục được đưa về 100% "
        "và áp dụng giới hạn độ lệch benchmark."
    )

    notes = [E.note_ty_trong(r.to_dict(), inp) for _, r in tt_df.iterrows()]
    render_bang_giai_thich(tt_df, notes, "ty_trong", height=430)

    st.markdown("<div class='tre-section-title'>So sánh trực quan</div>", unsafe_allow_html=True)
    try:
        cmp_df = tt_df.set_index("Ngành")[["Tỷ trọng benchmark %", "Tỷ trọng đề xuất %"]]
        st.bar_chart(cmp_df, height=380)
    except Exception as exc:  # noqa: BLE001
        log_event("ERROR", "ui", f"Lỗi vẽ biểu đồ tỷ trọng: {exc}")

    canh_bao = float(E.scoring_config().get("gioi_han_lech_benchmark", {}).get("canh_bao_do_lech", 5.0))
    lon = tt_df[tt_df["Độ lệch điểm %"].abs() > canh_bao]
    if not lon.empty:
        chi_tiet = "\n".join(
            f"• {r['Ngành']}: {E.fmt_pct(r['Độ lệch điểm %'])} điểm phần trăm so với benchmark" for _, r in lon.iterrows()
        )
        _render_warning_card(
            f"{len(lon)} ngành đang lệch trên {E.fmt_pct(canh_bao)} so với benchmark",
            chi_tiet
            + "\n\nĐây là các cuộc đánh cược lớn. Hãy tự hỏi: bạn biết điều gì mà thị trường chưa biết, "
            "hoặc bạn đọc thông tin công khai khác đám đông ở điểm nào?",
        )


def _tab_dao_sau() -> None:
    inp = _current_input()
    names = E.sector_name_map()
    codes = E.sector_codes()

    st.markdown("<div class='tre-section-title'>Bước 4 — Đào sâu vào nhóm ngành cấp 2</div>", unsafe_allow_html=True)
    cur = st.session_state.get(SS_NGANH_CHON, codes[0] if codes else "")
    idx = codes.index(cur) if cur in codes else 0
    chosen = st.selectbox("Chọn ngành cấp 1 để đào sâu", codes, index=idx, format_func=lambda c: f"{names.get(c, c)} ({c})")
    if chosen != st.session_state.get(SS_NGANH_CHON):
        st.session_state[SS_NGANH_CHON] = chosen
        log_event("INFO", "ui", f"Người dùng chọn đào sâu ngành: {names.get(chosen, chosen)}")

    s = E.sector_by_code(chosen)
    d = E.diem_mot_nganh(chosen, inp)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Điểm tổng hợp", E.fmt_pct(d["tong"]))
    c2.metric("Kinh tế", E.fmt_pct(d["kt"]))
    c3.metric("Chính trị", E.fmt_pct(d["ct"]))
    c4.metric("Tâm lý", E.fmt_pct(d["tl"]))
    c5.metric("Chu kỳ", E.fmt_pct(d["ck"]))

    _render_ok_card(f"{s.get('ten_vi','')} ({s.get('ten_en','')})", s.get("mo_ta", ""))

    base = E.bang_industry_group(chosen, inp)
    st.caption("Cột Điểm tinh chỉnh cho phép bạn sửa trực tiếp (−20 đến +20) theo hiểu biết riêng về thị trường Việt Nam.")
    edited = st.data_editor(
        base,
        use_container_width=True,
        hide_index=True,
        disabled=["STT", "Nhóm ngành cấp 2", "Tên quốc tế", "Số ngành cấp 3", "Điểm thừa hưởng", "Điểm sau tinh chỉnh"],
        column_config={
            "Điểm tinh chỉnh": st.column_config.NumberColumn(
                "Điểm tinh chỉnh", min_value=-20.0, max_value=20.0, step=1.0, format="%.1f"
            )
        },
        key=f"ig_editor_{chosen}",
    )
    final = E.ap_dung_tinh_chinh(edited)
    notes = [E.note_industry_group(r.to_dict(), chosen) for _, r in final.iterrows()]
    render_bang_giai_thich(final, notes, f"ig_{chosen}", height=320)

    st.markdown("<div class='tre-section-title'>Danh sách ngành cấp 3 trong ngành đang chọn</div>", unsafe_allow_html=True)
    rows = []
    for g in s.get("industry_groups", []):
        for ind in g.get("industries", []):
            rows.append({"Nhóm ngành cấp 2": g["ten_vi"], "Ngành cấp 3": ind})
    render_bang_tinh(pd.DataFrame(rows), height=300)


def _tab_sang_loc() -> None:
    st.markdown("<div class='tre-section-title'>Bước 5 — Sàng lọc định lượng</div>", unsafe_allow_html=True)
    cfg = E.scoring_config().get("sang_loc_dinh_luong_mac_dinh", {})
    _render_ok_card("Bốn lớp sàng lọc theo Fisher", cfg.get("dien_giai", ""))

    bo = st.radio(
        "Chọn bộ tiêu chí",
        ["chat_che", "rong", "tuy_chinh"],
        horizontal=True,
        format_func=lambda k: {"chat_che": "Chặt chẽ", "rong": "Rộng", "tuy_chinh": "Tùy chỉnh"}[k],
    )
    base = dict(cfg.get("chat_che" if bo == "chat_che" else "rong", {}))
    base.pop("ten", None)

    if bo == "tuy_chinh":
        c = st.columns(4)
        base["von_hoa_toi_thieu_ty"] = float(c[0].number_input("Vốn hóa tối thiểu (tỷ đồng)", 0.0, 1e7, float(base.get("von_hoa_toi_thieu_ty", 1000)), 100.0, format="%.0f"))
        base["pe_toi_da"] = float(c[1].number_input("P/E tối đa (lần)", 0.0, 200.0, float(base.get("pe_toi_da", 20.0)), 0.5, format="%.1f"))
        base["pb_toi_da"] = float(c[2].number_input("P/B tối đa (lần)", 0.0, 50.0, float(base.get("pb_toi_da", 5.0)), 0.1, format="%.1f"))
        base["pcf_toi_da"] = float(c[3].number_input("P/CF tối đa (lần)", 0.0, 100.0, float(base.get("pcf_toi_da", 15.0)), 0.5, format="%.1f"))
        c2 = st.columns(3)
        base["ps_toi_da"] = float(c2[0].number_input("P/S tối đa (lần)", 0.0, 50.0, float(base.get("ps_toi_da", 5.0)), 0.1, format="%.1f"))
        base["no_vay_tren_von_chu_toi_da"] = float(c2[1].number_input("Nợ vay/Vốn chủ tối đa (lần)", 0.0, 20.0, float(base.get("no_vay_tren_von_chu_toi_da", 1.5)), 0.1, format="%.1f"))
        base["thanh_khoan_binh_quan_ty_toi_thieu"] = float(c2[2].number_input("Thanh khoản tối thiểu (tỷ đồng/phiên)", 0.0, 1000.0, float(base.get("thanh_khoan_binh_quan_ty_toi_thieu", 5.0)), 1.0, format="%.0f"))

    nguong_df = pd.DataFrame(
        [
            {"Tiêu chí": "Vốn hóa tối thiểu (tỷ đồng)", "Ngưỡng": E.fmt_ty(base.get("von_hoa_toi_thieu_ty")), "Lớp": "Capitalization"},
            {"Tiêu chí": "P/E tối đa (lần)", "Ngưỡng": E.fmt_ratio(base.get("pe_toi_da")), "Lớp": "Valuation"},
            {"Tiêu chí": "P/B tối đa (lần)", "Ngưỡng": E.fmt_ratio(base.get("pb_toi_da")), "Lớp": "Valuation"},
            {"Tiêu chí": "P/CF tối đa (lần)", "Ngưỡng": E.fmt_ratio(base.get("pcf_toi_da")), "Lớp": "Valuation"},
            {"Tiêu chí": "P/S tối đa (lần)", "Ngưỡng": E.fmt_ratio(base.get("ps_toi_da")), "Lớp": "Valuation"},
            {"Tiêu chí": "Nợ vay/Vốn chủ tối đa (lần)", "Ngưỡng": E.fmt_ratio(base.get("no_vay_tren_von_chu_toi_da")), "Lớp": "Solvency"},
            {"Tiêu chí": "Thanh khoản tối thiểu (tỷ đồng/phiên)", "Ngưỡng": E.fmt_ty(base.get("thanh_khoan_binh_quan_ty_toi_thieu")), "Lớp": "Liquidity"},
        ]
    )
    render_bang_tinh(nguong_df, height=290)

    st.markdown("<div class='tre-section-title'>Nhập danh sách cổ phiếu cần sàng lọc</div>", unsafe_allow_html=True)
    st.caption("Nhập trực tiếp vào bảng, hoặc tải file CSV có đúng các cột dưới đây. Đơn vị vốn hóa và thanh khoản: tỷ đồng.")

    up = st.file_uploader("Tải lên CSV danh sách cổ phiếu (tùy chọn)", type=["csv"])
    if up is not None:
        try:
            df_up = pd.read_csv(up)
            thieu = [c for c in E.COT_SANG_LOC if c not in df_up.columns]
            if thieu:
                st.error(f"File thiếu các cột: {', '.join(thieu)}")
                log_event("WARNING", "sang_loc", f"File tải lên thiếu cột: {thieu}")
            else:
                st.session_state[SS_SANG_LOC] = df_up[E.COT_SANG_LOC].copy()
                st.success(f"Đã nạp {len(df_up)} dòng từ file.")
                log_event("INFO", "sang_loc", f"Nạp {len(df_up)} dòng từ CSV.")
        except Exception as exc:  # noqa: BLE001
            st.error(f"Không đọc được file: {exc}")
            log_event("ERROR", "sang_loc", f"Lỗi đọc CSV: {exc}")

    st.download_button(
        "⬇️ Tải mẫu CSV trống",
        E.mau_bang_sang_loc(3).to_csv(index=False).encode("utf-8-sig"),
        file_name="mau_sang_loc_topdown.csv",
        mime="text/csv",
    )

    cur = st.session_state.get(SS_SANG_LOC, E.mau_bang_sang_loc(8))
    edited = st.data_editor(
        cur,
        use_container_width=True,
        num_rows="dynamic",
        hide_index=True,
        column_config={
            "Mã ngành": st.column_config.SelectboxColumn("Mã ngành", options=E.sector_codes()),
            "Vốn hóa (tỷ đồng)": st.column_config.NumberColumn("Vốn hóa (tỷ đồng)", format="%.0f"),
            "P/E (lần)": st.column_config.NumberColumn("P/E (lần)", format="%.1f"),
            "P/B (lần)": st.column_config.NumberColumn("P/B (lần)", format="%.1f"),
            "P/CF (lần)": st.column_config.NumberColumn("P/CF (lần)", format="%.1f"),
            "P/S (lần)": st.column_config.NumberColumn("P/S (lần)", format="%.1f"),
            "Nợ vay/Vốn chủ (lần)": st.column_config.NumberColumn("Nợ vay/Vốn chủ (lần)", format="%.1f"),
            "GTGD bình quân 20 phiên (tỷ đồng)": st.column_config.NumberColumn("GTGD bình quân 20 phiên (tỷ đồng)", format="%.0f"),
        },
        key="sang_loc_editor",
    )
    st.session_state[SS_SANG_LOC] = edited

    ket_qua = E.chay_sang_loc(edited, base)
    da_nhap = ket_qua[ket_qua["Kết quả"] != "Chưa nhập"]
    if da_nhap.empty:
        st.info("Chưa có mã nào được nhập. Hãy điền ít nhất một mã chứng khoán để chạy sàng lọc.")
        return

    n_dat = int((da_nhap["Kết quả"] == "Đạt").sum())
    c1, c2, c3 = st.columns(3)
    c1.metric("Số mã đã nhập", f"{len(da_nhap)}")
    c2.metric("Số mã đạt", f"{n_dat}")
    c3.metric("Tỷ lệ đạt", E.fmt_pct(n_dat / max(len(da_nhap), 1) * 100))

    st.markdown("<div class='tre-section-title'>Kết quả sàng lọc</div>", unsafe_allow_html=True)
    notes = [E.note_sang_loc(r.to_dict(), base) for _, r in da_nhap.iterrows()]
    render_bang_giai_thich(da_nhap.reset_index(drop=True), notes, "sang_loc", height=400)

    _render_warning_card(
        "Vượt qua sàng lọc không có nghĩa là nên mua",
        "Sàng lọc định lượng chỉ làm một việc: thu hẹp phạm vi để bước phân tích cơ bản khả thi. "
        "Quyết định mua bán phải đến từ Bước 3 — phân tích 5 bước và định giá. "
        "Hãy chuyển các mã đạt sang module Tổng quan doanh nghiệp và Định giá chuyên sâu của Trecapital.",
    )


def _tab_phan_tich_5_buoc() -> None:
    cfg = E.scoring_config()
    st.markdown("<div class='tre-section-title'>Bước 6 — Quy trình phân tích cổ phiếu 5 bước</div>", unsafe_allow_html=True)

    steps = cfg.get("nam_buoc_phan_tich_co_phieu", [])
    df = pd.DataFrame([{"Bước": s["buoc"], "Nội dung": s["ten"], "Việc cụ thể": s["chi_tiet"]} for s in steps])
    chi_tiet_map = {
        1: "BƯỚC 1 — HIỂU MÔ HÌNH KINH DOANH VÀ ĐỘNG LỰC LỢI NHUẬN\n\n"
        "Các việc phải làm theo Fisher:\n"
        "  • Tổng quan ngành: driver và rủi ro của ngành, xu hướng kinh tế đang tác động thế nào.\n"
        "  • Mô tả doanh nghiệp: sản phẩm, dịch vụ trong từng mảng — đọc thẳng từ báo cáo tài chính.\n"
        "  • Lịch sử doanh nghiệp: họ dẫn đầu ngành nhiều thập kỷ hay mới gia nhập? Có hay đổi chiến lược không?\n"
        "  • Tách doanh thu và lợi nhuận theo mảng và theo địa bàn: họ kiếm tiền ở đâu và bằng cách nào.\n"
        "  • Tin tức và công bố gần đây: truyền thông đánh giá doanh nghiệp thế nào.\n"
        "  • Khách hàng và thị trường: có phụ thuộc một khách hàng lớn không.\n"
        "  • Cạnh tranh: thị phần so với đối thủ. Lưu ý đối thủ lớn nhất đôi khi nằm ở ngành khác, thậm chí lĩnh vực khác.\n\n"
        "Liên kết với Trecapital: dùng module Tổng quan doanh nghiệp để lấy số liệu nhiều kỳ.",
        2: "BƯỚC 2 — XÁC ĐỊNH THUỘC TÍNH CHIẾN LƯỢC\n\n"
        "Thuộc tính chiến lược là đặc điểm riêng cho phép doanh nghiệp vượt trội so với chính nhóm ngành của nó. "
        "Vì các doanh nghiệp cùng ngành chịu chung driver vĩ mô, thuộc tính chiến lược mới là thứ tạo khác biệt.\n\n"
        "Điểm mấu chốt mà Fisher nhấn mạnh: KHÔNG phải thuộc tính nào cũng có lợi trong mọi môi trường.\n"
        "Ví dụ tích hợp dọc: khi cầu mạnh, doanh nghiệp kiểm soát được sản lượng, chạy nhà máy công suất cao, "
        "chi phí cố định trên mỗi đơn vị giảm và lợi nhuận tăng vọt. Nhưng khi cầu yếu, chính doanh nghiệp đó "
        "gánh toàn bộ thiệt hại từ công suất thấp, trong khi doanh nghiệp thuê ngoài thì không.\n\n"
        "Vì vậy phải chọn thuộc tính chiến lược PHÙ HỢP với driver đang thắng thế ở Bước 1.\n\n"
        "Thuộc tính chỉ có giá trị khi ban điều hành nhận ra và khai thác được nó. Thực thi mới là điều quyết định.",
        3: "BƯỚC 3 — PHÂN TÍCH CƠ BẢN VÀ DIỄN BIẾN GIÁ\n\n"
        "So sánh với chính nhóm ngành, không so với thị trường chung:\n"
        "  • Tăng trưởng doanh thu và lợi nhuận nhiều kỳ\n"
        "  • Biên lợi nhuận gộp và biên lợi nhuận ròng\n"
        "  • ROIC và ROE — hiệu quả sử dụng vốn\n"
        "  • Chất lượng dòng tiền: CFO so với lợi nhuận sau thuế\n"
        "  • Diễn biến giá tương đối so với nhóm ngành\n\n"
        "Liên kết với Trecapital: module Định giá chuyên sâu và module So sánh doanh nghiệp làm sẵn phần này.",
        4: "BƯỚC 4 — NHẬN DIỆN RỦI RO\n\n"
        "Bốn tầng rủi ro cần tách bạch:\n"
        "  • Rủi ro đặc thù doanh nghiệp: phụ thuộc khách hàng lớn, đòn bẩy cao, quản trị yếu, thao túng số liệu.\n"
        "  • Rủi ro ngành: chu kỳ giá hàng hóa, dư cung, công nghệ thay thế, hết hạn bằng sáng chế.\n"
        "  • Rủi ro hệ thống: suy thoái, khủng hoảng thanh khoản, biến động tỷ giá.\n"
        "  • Rủi ro chính sách: thay đổi thuế, siết quản lý, kiểm soát giá, rào cản thương mại.\n\n"
        "Liên kết với Trecapital: module Định giá chuyên sâu có phần phát hiện thao túng tài chính 4 lớp.",
        5: "BƯỚC 5 — ĐỊNH GIÁ VÀ KỲ VỌNG ĐỒNG THUẬN\n\n"
        "Hai câu hỏi phải trả lời:\n"
        "  1. Doanh nghiệp đang được định giá bao nhiêu so với nhóm ngành?\n"
        "  2. Thị trường đang định giá sẵn kỳ vọng gì, và bạn có tin kỳ vọng đó sai không?\n\n"
        "Câu hỏi thứ hai mới là nơi tạo ra lợi nhuận vượt trội. Một doanh nghiệp tốt với giá đã phản ánh "
        "hết mọi điều tốt đẹp thì không còn là cơ hội đầu tư.\n\n"
        "Liên kết với Trecapital: chuyển sang module Định giá chuyên sâu để tính dải giá trị nội tại và biên an toàn.",
    }
    notes = [chi_tiet_map.get(int(s["buoc"]), "") for s in steps]
    render_bang_giai_thich(df, notes, "5buoc", height=280)

    st.markdown("<div class='tre-section-title'>Danh mục thuộc tính chiến lược</div>", unsafe_allow_html=True)
    st.caption(
        "Đánh dấu các thuộc tính mà doanh nghiệp bạn đang xem xét thực sự sở hữu, rồi đối chiếu xem chúng có "
        "phù hợp với driver đang thắng thế ở Bước 1 hay không."
    )
    attrs = cfg.get("strategic_attributes", [])
    cols = st.columns(3)
    chon = []
    for i, a in enumerate(attrs):
        with cols[i % 3]:
            if st.checkbox(a, key=f"attr_{i}"):
                chon.append(a)
    if chon:
        _render_ok_card(
            f"Đã chọn {len(chon)} thuộc tính chiến lược",
            "\n".join(f"• {a}" for a in chon)
            + "\n\nCâu hỏi tiếp theo: mỗi thuộc tính này sẽ gặp thuận gió hay ngược gió với bộ driver bạn đã chấm ở Bước 1?",
        )


def _tab_bao_cao(diem_df: pd.DataFrame, tt_df: pd.DataFrame, kt_df: pd.DataFrame) -> None:
    inp = _current_input()
    st.markdown("<div class='tre-section-title'>Báo cáo tổng hợp Top-Down</div>", unsafe_allow_html=True)

    phases = E.cycle_config().get("pha_chu_ky", [])
    pha = next((p for p in phases if p["id"] == inp.pha_chu_ky), {})
    bm_meta = next((b for b in E.benchmark_config().get("benchmarks", []) if b["id"] == inp.benchmark_id), {})

    st.markdown("**Tham số đang dùng**")
    render_bang_tinh(
        pd.DataFrame(
            [
                {"Tham số": "Thời điểm lập báo cáo", "Giá trị": datetime.now().strftime("%d/%m/%Y %H:%M")},
                {"Tham số": "Pha chu kỳ", "Giá trị": pha.get("ten_vi", inp.pha_chu_ky)},
                {"Tham số": "Benchmark", "Giá trị": bm_meta.get("ten", inp.benchmark_id)},
                {"Tham số": "Độ lệch tối đa cho phép", "Giá trị": E.fmt_pct(inp.lech_toi_da)},
                {
                    "Tham số": "Số driver đã chấm",
                    "Giá trị": f"{sum(1 for v in inp.trien_vong_driver.values() if v != 0)}/{len(inp.trien_vong_driver)}",
                },
            ]
        ),
        height=230,
    )

    st.markdown("**Kết luận phân bổ ngành**")
    if not tt_df.empty:
        tang = tt_df[tt_df["Độ lệch điểm %"] > 0.05]
        giam = tt_df[tt_df["Độ lệch điểm %"] < -0.05]
        ket_luan = []
        if not tang.empty:
            ket_luan.append(
                "TĂNG TỶ TRỌNG: "
                + "; ".join(f"{r['Ngành']} ({E.fmt_pct(r['Tỷ trọng đề xuất %'])}, lệch {E.fmt_pct(r['Độ lệch điểm %'])})" for _, r in tang.iterrows())
            )
        if not giam.empty:
            ket_luan.append(
                "GIẢM TỶ TRỌNG: "
                + "; ".join(f"{r['Ngành']} ({E.fmt_pct(r['Tỷ trọng đề xuất %'])}, lệch {E.fmt_pct(r['Độ lệch điểm %'])})" for _, r in giam.iterrows())
            )
        _render_important_red("Quan điểm phân bổ ngành 12 tháng tới", "\n\n".join(ket_luan) if ket_luan else "Danh mục đang trung lập hoàn toàn so với benchmark.")

    st.markdown("**Bảng xếp hạng ngành**")
    render_bang_tinh(diem_df, height=430)

    st.markdown("**Bảng tỷ trọng đề xuất**")
    render_bang_tinh(tt_df, height=430)

    st.markdown("**Tự kiểm tra tính nhất quán dữ liệu**")
    notes = [
        f"HẠNG MỤC: {r['Hạng mục kiểm tra']}\n\n"
        f"Tình trạng: {r['Tình trạng']}\n"
        f"Mức độ quan trọng: {r['Mức độ']}\n\n"
        f"Chi tiết: {r['Chi tiết']}\n\n"
        "Vì sao app kiểm tra hạng mục này: nguyên tắc xây dựng app yêu cầu các module tự đồng bộ dữ liệu "
        "với nhau và giữ tính thống nhất tuyệt đối. Bảng này chạy lại sau mỗi thay đổi tham số."
        for _, r in kt_df.iterrows()
    ]
    render_bang_giai_thich(kt_df, notes, "kiem_tra", height=300)

    st.markdown("<div class='tre-section-title'>Xuất dữ liệu</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c1.download_button("⬇️ Xếp hạng ngành (CSV)", diem_df.to_csv(index=False).encode("utf-8-sig"), "topdown_xep_hang_nganh.csv", "text/csv", use_container_width=True)
    c2.download_button("⬇️ Tỷ trọng đề xuất (CSV)", tt_df.to_csv(index=False).encode("utf-8-sig"), "topdown_ty_trong.csv", "text/csv", use_container_width=True)

    try:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            diem_df.to_excel(w, sheet_name="Xep hang nganh", index=False)
            tt_df.to_excel(w, sheet_name="Ty trong de xuat", index=False)
            kt_df.to_excel(w, sheet_name="Kiem tra du lieu", index=False)
        c3.download_button("⬇️ Toàn bộ (Excel)", buf.getvalue(), "topdown_bao_cao.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    except Exception as exc:  # noqa: BLE001
        log_event("WARNING", "export", f"Không tạo được file Excel: {exc}")
        c3.info("Chưa xuất được Excel.")


def _tab_thuat_ngu() -> None:
    st.markdown("<div class='tre-section-title'>Thuật ngữ và từ viết tắt</div>", unsafe_allow_html=True)
    st.caption(
        "Ngoài bảng tra cứu này, bạn có thể quét chọn bất kỳ thuật ngữ nào trong các bảng của app "
        "để hiện diễn giải dạng chú thích ngay tại chỗ."
    )
    terms = E.glossary_terms()
    q = st.text_input("Tìm thuật ngữ", "")
    items = sorted(terms.items(), key=lambda x: x[0].lower())
    if q.strip():
        ql = q.strip().lower()
        items = [(k, v) for k, v in items if ql in k.lower() or ql in v.lower()]
    df = pd.DataFrame([{"Thuật ngữ": k, "Diễn giải": v} for k, v in items])
    if df.empty:
        st.info("Không tìm thấy thuật ngữ phù hợp.")
        return
    df.insert(0, "STT", range(1, len(df) + 1))
    st.download_button("⬇️ Tải bảng thuật ngữ", df.to_csv(index=False).encode("utf-8-sig"), "glossary_topdown.csv", "text/csv")
    render_bang_thuat_ngu(df)


def _tab_nhat_ky() -> None:
    st.markdown("<div class='tre-section-title'>Nhật ký chạy app</div>", unsafe_allow_html=True)
    st.caption("Nguyên tắc xây dựng app số 10: luôn ghi log để phát hiện và sửa lỗi. Log được ghi song song ra thư mục logs/.")

    rows = memory_log_rows()
    c1, c2, c3 = st.columns([2, 2, 1])
    muc_do = c1.multiselect("Lọc theo mức độ", ["DEBUG", "INFO", "WARNING", "ERROR"], default=["INFO", "WARNING", "ERROR"])
    khu_vuc_all = sorted({r["Khu vực"] for r in rows}) or ["chung"]
    khu_vuc = c2.multiselect("Lọc theo khu vực", khu_vuc_all, default=khu_vuc_all)
    if c3.button("🗑️ Xóa nhật ký", use_container_width=True):
        clear_memory_log()
        st.rerun()

    loc = [r for r in rows if r["Mức độ"] in muc_do and r["Khu vực"] in khu_vuc]
    n_err = sum(1 for r in rows if r["Mức độ"] == "ERROR")
    n_warn = sum(1 for r in rows if r["Mức độ"] == "WARNING")
    m1, m2, m3 = st.columns(3)
    m1.metric("Tổng số dòng log", f"{len(rows)}")
    m2.metric("Số cảnh báo", f"{n_warn}")
    m3.metric("Số lỗi", f"{n_err}")

    if n_err:
        _render_important_red("Có lỗi trong phiên làm việc này", "Hãy mở bộ lọc mức độ ERROR bên trên để xem chi tiết và traceback.")

    df = pd.DataFrame(loc) if loc else pd.DataFrame(columns=["Thời điểm", "Mức độ", "Khu vực", "Nội dung"])
    render_bang_tinh(df, height=440)
    if not df.empty:
        st.download_button("⬇️ Tải nhật ký (CSV)", df.to_csv(index=False).encode("utf-8-sig"), "topdown_log.csv", "text/csv")


# ======================================================================================
# F. Điểm vào
# ======================================================================================


def render_dashboard() -> None:
    _inject_runtime_ui_css()
    _init_state()
    _render_sidebar()

    _render_brand_page_header(
        "Phân tích Top-Down theo ngành",
        "Chọn đúng ngành trước, chọn cổ phiếu sau. Quy trình ba bước theo phương pháp top-down của "
        "Fisher Investments: phân tích Portfolio Drivers, sàng lọc định lượng, rồi mới đến phân tích cổ phiếu.",
    )

    inp = _current_input()
    try:
        diem_df = E.cham_diem_tat_ca_nganh(inp)
        tt_df = E.bang_ty_trong_de_xuat(diem_df, inp)
        kt_df = E.kiem_tra_dong_bo(inp, diem_df, tt_df)
        _bridge_to_other_modules(inp, diem_df, tt_df, kt_df)
    except Exception as exc:  # noqa: BLE001
        log_event("ERROR", "dashboard", f"Lỗi tính toán chính: {exc}")
        st.error(f"Có lỗi khi tính toán: {exc}. Xem chi tiết ở tab Nhật ký.")
        diem_df = pd.DataFrame()
        tt_df = pd.DataFrame()
        kt_df = pd.DataFrame()

    n_canh_bao = int((kt_df["Tình trạng"] == "Cảnh báo").sum()) if not kt_df.empty else 0
    if n_canh_bao:
        st.warning(f"Có {n_canh_bao} hạng mục dữ liệu cần chú ý. Xem chi tiết ở tab Báo cáo tổng hợp.", icon="⚠️")

    tabs = st.tabs(
        [
            "🧭 Khung phương pháp",
            "📈 Portfolio Drivers",
            "🔄 Chu kỳ kinh tế",
            "🏆 Xếp hạng ngành",
            "⚖️ Tỷ trọng danh mục",
            "🔬 Đào sâu nhóm ngành",
            "🔎 Sàng lọc định lượng",
            "🏢 Phân tích cổ phiếu 5 bước",
            "📄 Báo cáo tổng hợp",
            "📖 Thuật ngữ",
            "🧾 Nhật ký",
        ]
    )

    with tabs[0]:
        _tab_khung_phuong_phap()
    with tabs[1]:
        _tab_drivers()
    with tabs[2]:
        _tab_chu_ky()
    with tabs[3]:
        _tab_xep_hang(diem_df)
    with tabs[4]:
        _tab_ty_trong(diem_df, tt_df)
    with tabs[5]:
        _tab_dao_sau()
    with tabs[6]:
        _tab_sang_loc()
    with tabs[7]:
        _tab_phan_tich_5_buoc()
    with tabs[8]:
        _tab_bao_cao(diem_df, tt_df, kt_df)
    with tabs[9]:
        _tab_thuat_ngu()
    with tabs[10]:
        _tab_nhat_ky()
