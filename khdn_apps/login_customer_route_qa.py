from __future__ import annotations

from khdn_apps.customer_work_signature_fix import install as install_signature
from khdn_apps.auto_remember_login_patch import install as install_login


def qa_signature():
    class UI:
        _CUSTOMER_WORK_SIGNATURE_FIX_INSTALLED = False

    calls = []
    def old(st_arg, u, get_conn, page_title=None, logger_arg=None):
        calls.append((st_arg, u, get_conn, page_title, logger_arg))
        return "ok"
    UI.render_cases_page = staticmethod(old)
    install_signature(UI)
    result = UI.render_cases_page(st="STREAMLIT", u="USER", get_conn="CONN", page_title="TITLE", logger="LOG")
    assert result == "ok"
    assert calls == [("STREAMLIT", "USER", "CONN", "TITLE", "LOG")]


def qa_auto_remember():
    class FakeSt:
        def __init__(self):
            self.captions=[]
            self.other_checkbox_calls=0
        def checkbox(self,label,*args,**kwargs):
            self.other_checkbox_calls += 1
            return False
        def caption(self,body,*args,**kwargs):
            self.captions.append(str(body))
            return None

    st=FakeSt()
    seen={}
    original_checkbox=st.checkbox
    original_caption=st.caption

    def login_ui():
        seen["remember"] = st.checkbox("Ghi nhớ đăng nhập trên thiết bị này trong 30 ngày", value=False)
        st.caption("Chỉ bật trên điện thoại cá nhân có khóa màn hình. Không bật trên thiết bị dùng chung.")
        return "login"

    ns={"st":st,"login_ui":login_ui,"LOGGER":None}
    install_login(ns)
    assert ns["login_ui"]() == "login"
    assert seen["remember"] is True
    assert st.other_checkbox_calls == 0
    assert st.captions[-1].startswith("Đăng nhập sẽ được tự động ghi nhớ")
    # The patch must not leave global Streamlit methods replaced after rendering.
    assert st.checkbox == original_checkbox
    assert st.caption == original_caption


def main():
    qa_signature()
    qa_auto_remember()
    print("LOGIN_CUSTOMER_ROUTE_QA_PASS")


if __name__ == "__main__":
    main()
