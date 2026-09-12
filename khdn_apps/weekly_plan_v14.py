"""Weekly Plan V14: mobile/touch hardening and compact Q1-Q4 help.

This layer does not change business rules. It applies the final responsive CSS
for 360-430 px phones and adds a collapsed in-app glossary so users can
understand Q1-Q4 without leaving the workflow.
"""
from __future__ import annotations

from typing import Callable, Optional

import streamlit as st

from khdn_apps import weekly_plan_v13 as v13


def _inject_v14_mobile_css():
    st.html(
        """
        <style>
        /* Weekly Plan mobile QA hardening. Keep all changes local to the page
           render and avoid fixed widths that cause horizontal scrolling. */
        .weekly-hero,.weekly-task-card,.weekly-dashboard-card,.weekly-notification,
        .weekly-html-table-wrap,.weekly-warn-card,.weekly-glossary{
          box-sizing:border-box!important;max-width:100%!important;overflow-wrap:anywhere!important;
        }
        .weekly-task-head{min-width:0!important}
        .weekly-task-title{min-width:0!important;overflow-wrap:anywhere!important;word-break:break-word!important}
        .weekly-badge{max-width:100%!important;white-space:normal!important;text-align:center!important;line-height:1.15!important}
        [data-testid="stPlotlyChart"],[data-testid="stPlotlyChart"]>div{max-width:100%!important;overflow:hidden!important}
        div[class*="st-key-weekly"] button{min-height:44px!important;white-space:normal!important;line-height:1.2!important}
        div[class*="st-key-weekly"] input,div[class*="st-key-weekly"] textarea,
        div[class*="st-key-weekly"] [data-baseweb="select"]{max-width:100%!important;box-sizing:border-box!important}
        .weekly-q-help{background:#122624;border:1px solid rgba(164,232,219,.22);border-radius:12px;padding:9px 10px;margin:.25rem 0 .75rem;color:#E9FAF7;font-size:.78rem;line-height:1.38}
        .weekly-q-help-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-top:6px}
        .weekly-q-help-item{background:#17312F;border:1px solid rgba(164,232,219,.18);border-radius:9px;padding:7px;min-width:0;overflow-wrap:anywhere}
        .weekly-q-help-item b{color:#F4B41A!important}

        @media(max-width:700px){
          .block-container{padding-left:.82rem!important;padding-right:.82rem!important;padding-top:.65rem!important}
          .weekly-hero{padding:10px 11px!important;margin-bottom:.6rem!important}
          .weekly-task-card{padding:9px 9px!important;margin:6px 0!important}
          .weekly-task-head{display:grid!important;grid-template-columns:minmax(0,1fr) auto!important;gap:7px!important;align-items:start!important}
          .weekly-q-help-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important}
          .weekly-html-table-wrap{overflow-x:hidden!important;width:100%!important}
          .weekly-html-table{min-width:0!important;width:100%!important;table-layout:fixed!important}
          .weekly-html-table th,.weekly-html-table td{white-space:normal!important;overflow-wrap:anywhere!important;word-break:break-word!important}
        }
        @media(max-width:430px){
          .weekly-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:6px!important}
          .weekly-kpi{padding:7px 8px!important}.weekly-kpi .v{font-size:.96rem!important}.weekly-kpi .l{font-size:.66rem!important}
          .weekly-task-title{font-size:.84rem!important}.weekly-meta,.weekly-result{font-size:.72rem!important}
          .weekly-task-head{grid-template-columns:minmax(0,1fr) minmax(72px,34%)!important}
          .weekly-badge{justify-self:end!important;font-size:.64rem!important;padding:3px 5px!important}
          [data-testid="stPlotlyChart"]{width:100%!important}
        }
        @media(max-width:380px){
          .block-container{padding-left:.62rem!important;padding-right:.62rem!important}
          [data-testid="stHorizontalBlock"]{flex-wrap:wrap!important;gap:.4rem!important}
          [data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{min-width:0!important;flex:1 1 100%!important;width:100%!important}
          .weekly-task-head{grid-template-columns:1fr!important}
          .weekly-badge{justify-self:start!important;max-width:100%!important}
          .weekly-q-help-grid{grid-template-columns:1fr!important}
          div[data-testid="stTextInput"] input,div[data-testid="stNumberInput"] input,
          div[data-testid="stTextArea"] textarea,[data-baseweb="select"] input{font-size:16px!important}
        }
        </style>
        """
    )


def _render_q_help():
    with st.expander("ℹ️ Q1–Q4 được hệ thống xác định như thế nào?", expanded=False):
        st.html(
            """
            <div class="weekly-q-help">
              Cán bộ <b>không tự chọn</b> góc phần tư. Hệ thống suy ra từ danh mục trọng tâm,
              hạn hoàn thành và việc công việc có gắn chỉ tiêu/rủi ro trọng yếu hay không.
              <div class="weekly-q-help-grid">
                <div class="weekly-q-help-item"><b>Q2 · Trọng tâm</b><br>Thuộc danh mục trọng tâm của phòng.</div>
                <div class="weekly-q-help-item"><b>Q1 · Cấp thiết</b><br>Cấp bách và gắn chỉ tiêu/rủi ro trọng yếu.</div>
                <div class="weekly-q-help-item"><b>Q3 · Phân tâm</b><br>Cấp bách nhưng không gắn chỉ tiêu/rủi ro trọng yếu.</div>
                <div class="weekly-q-help-item"><b>Q4 · Giá trị thấp</b><br>Không thuộc trọng tâm và không cấp bách.</div>
              </div>
            </div>
            """
        )


def weekly_plan_page(u, get_conn: Callable, page_title: Callable, pill_nav: Optional[Callable] = None):
    def _title(title, subtitle):
        page_title(title, subtitle)
        # V13/core CSS has already been injected before page_title is invoked,
        # so these rules are intentionally later and win on phone breakpoints.
        _inject_v14_mobile_css()
        _render_q_help()

    return v13.weekly_plan_page(u, get_conn, _title, pill_nav)


def weekly_admin_panel(u, get_conn: Callable):
    result = v13.weekly_admin_panel(u, get_conn)
    _inject_v14_mobile_css()
    return result
