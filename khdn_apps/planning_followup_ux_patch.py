"""Follow-up planning UX corrections requested after the Monday-Friday board.

Guarantees:
- customer-work reschedule is date-only in the UI (17:00 remains an internal timestamp);
- missing required planning fields are visibly red after submit validation;
- each Monday-Friday column has a quick-add button that preselects that work date;
- staff navigation places Weekly Plan immediately after Today;
- expected-completion dates cannot be selected in the past.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
import html

from khdn_apps import customer_work_patch as customer_nav
from khdn_apps import planning_final_ux_patch as finalux
from khdn_apps import planning_usability_v2_patch as v2
from khdn_apps import planning_usability_v3_patch as v3
from khdn_apps import planning_week_board_focus_patch as weekboard

VERSION = "1.0.0"
_FLAG = "_PLANNING_FOLLOWUP_UX_PATCH_VERSION"


def _as_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value:
        try:
            return date.fromisoformat(str(value)[:10])
        except Exception:
            return None
    return None


def _missing_css(st, keys):
    """Strong, persistent red treatment for every invalid required widget key."""
    clean = [str(k) for k in (keys or []) if k]
    if not clean:
        return
    rules = []
    for key in clean:
        esc = key.replace("\\", "\\\\").replace('"', '\\"')
        root = f'div[class*="st-key-{esc}"]'
        rules.append(
            f"""
            {root} {{
                border-radius:10px!important;
                box-shadow:0 0 0 2px rgba(255,75,75,.30)!important;
            }}
            {root} [data-baseweb="input"] > div,
            {root} [data-baseweb="select"] > div,
            {root} [data-baseweb="textarea"] > div,
            {root} [data-testid="stDateInput"] > div,
            {root} [data-testid="stDateInput"] input,
            {root} [data-testid="stTimeInput"] > div,
            {root} [data-testid="stSelectbox"] [data-baseweb="select"] > div,
            {root} input,
            {root} textarea,
            {root} [role="combobox"] {{
                border-color:#FF4B4B!important;
                outline-color:#FF4B4B!important;
                box-shadow:0 0 0 2px rgba(255,75,75,.42)!important;
                background:rgba(255,75,75,.085)!important;
            }}
            {root} label,
            {root} label p,
            {root} [data-testid="stWidgetLabel"],
            {root} [data-testid="stWidgetLabel"] p {{
                color:#FF6B6B!important;
                -webkit-text-fill-color:#FF6B6B!important;
                font-weight:950!important;
            }}
            """
        )
    st.markdown("<style>" + "\n".join(rules) + "</style>", unsafe_allow_html=True)


class _DueGuardProxy:
    """Delegate Streamlit while enforcing non-past expected-completion dates."""
    def __init__(self, st):
        self._st = st

    def __getattr__(self, name):
        return getattr(self._st, name)

    def date_input(self, label, *args, **kwargs):
        key = str(kwargs.get("key") or "")
        guarded = (
            key.endswith("_due")
            or key.endswith("_due_date")
            or key.startswith("cw_rd_")
            or "Dự kiến hoàn thành" in str(label)
            or str(label).strip() == "Ngày mới"
        )
        if guarded:
            today = date.today()
            old_min = _as_date(kwargs.get("min_value"))
            min_value = max(today, old_min) if old_min else today
            kwargs["min_value"] = min_value
            kwargs.setdefault("format", "DD/MM/YYYY")

            current = _as_date(kwargs.get("value"))
            if current and current < min_value:
                kwargs["value"] = min_value

            if key and key in self._st.session_state:
                state_date = _as_date(self._st.session_state.get(key))
                if state_date and state_date < min_value:
                    self._st.session_state[key] = min_value

        return self._st.date_input(label, *args, **kwargs)


class _HiddenTimeColumn:
    def time_input(self, *args, **kwargs):
        # Business UI is date-only; 17:00 is kept for backwards-compatible storage.
        return time(17, 0)


class _RescheduleProxy(_DueGuardProxy):
    def __init__(self, st, case_id):
        super().__init__(st)
        self.case_id = int(case_id)
        self._date_only_columns = False

    @property
    def invalid_state(self):
        return f"cw_reschedule_invalid_{self.case_id}"

    def subheader(self, body, *args, **kwargs):
        if str(body).strip() == "Dời thời gian dự kiến hoàn thành":
            self._date_only_columns = True
            return self._st.subheader("Dời ngày dự kiến hoàn thành", *args, **kwargs)
        return self._st.subheader(body, *args, **kwargs)

    def columns(self, spec, *args, **kwargs):
        if self._date_only_columns and (spec == 2 or spec == [1, 1] or spec == (1, 1)):
            self._date_only_columns = False
            # No visual second column: the hidden object only supplies the internal 17:00.
            return [self, _HiddenTimeColumn()]
        return self._st.columns(spec, *args, **kwargs)

    def button(self, label, *args, **kwargs):
        key = str(kwargs.get("key") or "")
        if key == f"cw_req_move_{self.case_id}":
            label = "Gửi đề nghị dời ngày"
        clicked = self._st.button(label, *args, **kwargs)
        if clicked and key == f"cw_req_move_{self.case_id}":
            missing = []
            missing_keys = []
            reason_key = f"cw_rr_{self.case_id}"
            date_key = f"cw_rd_{self.case_id}"
            reason = str(self._st.session_state.get(reason_key) or "").strip()
            proposed = _as_date(self._st.session_state.get(date_key))
            if not reason:
                missing.append("Lý do dời")
                missing_keys.append(reason_key)
            if proposed is None or proposed < date.today():
                missing.append("Ngày mới")
                missing_keys.append(date_key)
            if missing:
                finalux._fail_validation(self._st, self.invalid_state, missing, missing_keys)
            finalux._clear_validation(self._st, self.invalid_state)
        return clicked

    def toast(self, body, *args, **kwargs):
        text = str(body).replace("Đã cập nhật thời gian.", "Đã cập nhật ngày dự kiến hoàn thành.")
        return self._st.toast(text, *args, **kwargs)


def _render_week_board(st, policy, get_conn, uid, ws, items, status):
    """Monday-Friday board with a quick-add action inside each weekday column."""
    st.markdown("### 🗓 Kế hoạch Thứ 2 → Thứ 6")
    live = [x for x in items if str(x.get("status") or "") != "CANCELLED"]
    day_cols = st.columns(5, gap="small")
    labels = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6"]
    can_add = status in ("NHAP", "DA_DUYET")

    for idx, (col, label) in enumerate(zip(day_cols, labels)):
        d = ws + timedelta(days=idx)
        day_items = [x for x in live if str(x.get("work_date") or "")[:10] == d.isoformat()]
        day_items.sort(key=lambda x: (
            policy.PRIORITY_ORDER.index(int(x.get("priority_quadrant") or 4))
            if int(x.get("priority_quadrant") or 4) in policy.PRIORITY_ORDER else 9,
            int(x.get("id") or 0),
        ))
        with col:
            st.markdown(
                f"<div class='wkday-head'><b>{label}</b><span>{d:%d/%m}</span><em>{len(day_items)} việc</em></div>",
                unsafe_allow_html=True,
            )
            if st.button(
                "＋ Thêm công việc",
                key=f"wkday_quick_add_{ws.isoformat()}_{idx}",
                use_container_width=True,
                disabled=not can_add,
            ):
                st.session_state[f"wp_quick_day_{ws.isoformat()}"] = d.isoformat()
                st.toast(f"Đã chọn {label} {d:%d/%m/%Y}. Ngày thực hiện đã được điền sẵn ở form bên dưới.", icon="➕")
                st.rerun()

            if not day_items:
                st.caption("Chưa có công việc")
            for x in day_items:
                iid = int(x.get("id") or 0)
                q = int(x.get("priority_quadrant") or 4)
                heat = weekboard._HEAT.get(q, weekboard._HEAT[4])
                title = html.escape(str(x.get("title") or "Công việc"))
                customer = html.escape(str(x.get("customer_text") or "Không gắn KH"))
                due = html.escape(weekboard._dmy(x.get("expected_complete_date")))
                focus = html.escape(str(x.get("focus_name_snapshot") or ""))
                emergent = " · ⚡ Phát sinh" if int(x.get("is_emergent") or 0) else ""
                with st.container(key=f"wkday_card_{iid}", border=True):
                    st.markdown(
                        f"<div class='wkday-title'>{title}</div>"
                        f"<div class='wkday-customer'>{customer}</div>"
                        f"<div class='wkday-meta' style='color:{heat['accent']}'>{heat['label']}{emergent}</div>"
                        f"<div class='wkday-due'>🎯 Hạn: {due}</div>"
                        + (f"<div class='wkday-focus'>📌 {focus}</div>" if focus else ""),
                        unsafe_allow_html=True,
                    )
                    if status == "NHAP" and not int(x.get("is_emergent") or 0):
                        if st.button("🗑 Bỏ", key=f"wkday_remove_{iid}", use_container_width=True):
                            with get_conn() as c:
                                c.execute(
                                    "UPDATE weekly_plan_items SET status='CANCELLED',updated_at=? WHERE id=? AND user_id=?",
                                    (policy._now(), iid, int(uid)),
                                )
                                c.execute(
                                    "INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,'DRAFT_REMOVE','Bỏ khỏi bản nháp',?)",
                                    (iid, int(uid), policy._now()),
                                )
                            st.rerun()
                    st.markdown(
                        f"<style>div[class*='st-key-wkday_card_{iid}']{{border-left:5px solid {heat['accent']}!important;background:{heat['bg']}!important}}"
                        ".wkday-title{font-weight:950;font-size:.88rem;line-height:1.25}.wkday-customer{font-size:.75rem;opacity:.82;margin-top:3px}"
                        ".wkday-meta{font-size:.73rem;font-weight:900;margin-top:6px}.wkday-due,.wkday-focus{font-size:.72rem;margin-top:5px}</style>",
                        unsafe_allow_html=True,
                    )

    weekend = [x for x in live if str(x.get("work_date") or "")[:10] in {
        (ws + timedelta(days=5)).isoformat(), (ws + timedelta(days=6)).isoformat()
    }]
    if weekend:
        with st.expander(f"Ngoài khung Thứ 2–Thứ 6 · {len(weekend)} việc", expanded=False):
            for x in weekend:
                st.write(f"• {weekboard._dmy(x.get('work_date'))} · {x.get('title')}")

    st.markdown(
        """<style>
        .wkday-head{display:flex;flex-direction:column;gap:2px;padding:9px 10px;margin-bottom:7px;border-radius:12px;
          background:linear-gradient(135deg,#075C57,#0F746B);border:1px solid #F4B41A;color:#fff;box-shadow:0 4px 12px rgba(0,0,0,.12)}
        .wkday-head b{font-size:.96rem}.wkday-head span{font-size:.78rem;opacity:.9}.wkday-head em{font-size:.70rem;opacity:.82;font-style:normal}
        div[class*='st-key-wkday_quick_add_'] button{min-height:34px!important;font-size:.76rem!important;font-weight:900!important;
          border:1px solid rgba(99,220,203,.55)!important;background:rgba(15,116,107,.55)!important;color:#fff!important;-webkit-text-fill-color:#fff!important}
        div[class*='st-key-wkday_quick_add_'] button *{color:#fff!important;-webkit-text-fill-color:#fff!important}
        @media(max-width:900px){.wkday-head{margin-top:5px}}
        </style>""",
        unsafe_allow_html=True,
    )


def install(policy, customer_core, customer_ui, refinement, worktype, logger=None):
    if getattr(policy, _FLAG, None) == VERSION:
        return

    # Strengthen all validation surfaces already used by Weekly Plan/Customer Work.
    finalux._missing_css = _missing_css
    v3._missing_css = _missing_css

    # Weekly quick-add preselects the chosen weekday, while due dates stay >= today.
    original_add = policy._add_item_form

    def add_item_form(st, u, core, get_conn, ws, focus_rows, emergent=False,
                      logger=None, logger_arg=None, **kwargs):
        quick_key = f"wp_quick_day_{ws.isoformat()}"
        quick_day = st.session_state.pop(quick_key, None)
        if quick_day:
            epoch_key = f"wp_refine_epoch_{ws.isoformat()}_{'ps' if emergent else 'plan'}"
            epoch = int(st.session_state.get(epoch_key, 0) or 0)
            prefix = f"wp_refined_{ws.isoformat()}_{'ps' if emergent else 'plan'}_{epoch}"
            try:
                st.session_state[f"{prefix}_day"] = date.fromisoformat(str(quick_day)[:10])
            except Exception:
                pass
        return original_add(
            _DueGuardProxy(st), u, core, get_conn, ws, focus_rows,
            emergent=emergent, logger=logger, logger_arg=logger_arg, **kwargs
        )

    policy._add_item_form = add_item_form
    weekboard._render_week_board = _render_week_board

    # Customer Work create form keeps the focus-catalog logic but blocks past due dates.
    def create_form(st, u, get_conn, core, ui, refinement_arg, worktype_arg, logger=None):
        return weekboard._customer_create_form(
            policy, _DueGuardProxy(st), u, get_conn, core, ui, refinement_arg, worktype_arg, logger
        )

    v3._create_form = create_form
    v2._create_form = create_form

    # Date-only reschedule UI with red validation for reason/date.
    original_case_detail = customer_ui._case_detail

    def case_detail(st, u, get_conn, case_id, logger=None):
        state_key = f"cw_reschedule_invalid_{int(case_id)}"
        finalux._render_validation(st, state_key)
        return original_case_detail(_RescheduleProxy(st, case_id), u, get_conn, case_id, logger)

    customer_ui._case_detail = case_detail

    # Staff command strip: Today | Weekly Plan | Customer Work.
    original_plan_options = customer_nav._plan_options

    def plan_options(role, admin):
        opts = list(original_plan_options(role, admin))
        if role != "Lãnh đạo phòng" and not bool(admin):
            order = ["work_today", "weekly_plan", "customer_work"]
            by_route = {route: (route, label) for route, label in opts}
            return [by_route[r] for r in order if r in by_route]
        return opts

    customer_nav._plan_options = plan_options

    setattr(policy, _FLAG, VERSION)
    if logger:
        logger.info(
            "PLANNING_FOLLOWUP_UX_INSTALLED version=%s date_only_reschedule=1 red_validation=1 quick_weekday_add=1 nav_weekly_second=1 no_past_due=1",
            VERSION,
        )
