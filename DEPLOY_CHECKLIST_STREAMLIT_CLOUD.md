# Checklist deploy Streamlit Community Cloud

## Trước khi upload GitHub

- [ ] Giải nén gói `Trecapital_Stock_App_Streamlit_Cloud_Ready.zip`.
- [ ] Đảm bảo `app.py` nằm ở root repo.
- [ ] Đảm bảo có `requirements.txt`.
- [ ] Đảm bảo có `runtime.txt` với nội dung `python-3.11`.
- [ ] Không commit `.streamlit/secrets.toml`, `.env`, token/API key.
- [ ] Commit và push lên GitHub.

## Trên Streamlit Community Cloud

- [ ] New app.
- [ ] Repository: repo GitHub của anh.
- [ ] Branch: `main`.
- [ ] Main file path: `app.py`.
- [ ] Deploy.

## Sau khi deploy

- [ ] App load được trang đầu.
- [ ] Chọn mã cổ phiếu được.
- [ ] Các tab hoạt động.
- [ ] Xuất báo cáo hoạt động.
- [ ] Ghi lại link dạng `https://ten-app.streamlit.app`.

## Nếu muốn dùng trecapital.org tạm thời

Tạo redirect trong Cloudflare:

```text
app.trecapital.org -> https://ten-app.streamlit.app
```
