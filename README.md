# Trecapital Stock Analysis App - Streamlit Community Cloud Ready

Gói này đã được làm gọn để đưa thẳng lên GitHub và deploy miễn phí bằng Streamlit Community Cloud.

## 1. Cấu trúc repo đúng

Sau khi giải nén gói này, thư mục repo phải nhìn thấy trực tiếp các file sau ở cấp gốc:

```text
app.py
requirements.txt
runtime.txt
.streamlit/config.toml
module1_dashboard.py
module2_dashboard.py
...
```

Không để lồng thêm một thư mục cha trước `app.py`, nếu không Streamlit Cloud dễ chọn sai entrypoint.

## 2. Deploy nhanh

1. Tạo GitHub repo mới, nên để `Private` nếu app/dữ liệu nội bộ.
2. Upload toàn bộ nội dung trong thư mục này lên repo.
3. Vào Streamlit Community Cloud: https://share.streamlit.io
4. Chọn `New app`.
5. Chọn repo vừa tạo.
6. Chọn branch: `main`.
7. Main file path: `app.py`.
8. Bấm `Deploy`.

## 3. Python version

Gói này có file `runtime.txt`:

```text
python-3.11
```

Mục tiêu là dùng Python 3.11 để khớp với các dependency đã pin trong `requirements.txt`.

## 4. Secrets/API key

Hiện app ưu tiên dữ liệu tích hợp và dữ liệu mẫu, không bắt buộc token để chạy cơ bản.
Nếu sau này thêm token/API key, không commit `.streamlit/secrets.toml` lên GitHub.
Hãy nhập vào:

```text
Streamlit Community Cloud -> Manage app -> Settings -> Secrets
```

File `.streamlit/secrets.toml.example` chỉ là mẫu tham khảo.

## 5. Lưu ý dữ liệu trên Streamlit Community Cloud

Các thư mục runtime như `data_cache/`, `raw_data/`, `reports/` chỉ là lưu tạm trong phiên chạy cloud.
Khi app sleep/rebuild, dữ liệu phát sinh có thể mất. Muốn lưu lâu dài nên chuyển sang Google Drive, Google Cloud Storage hoặc database.

## 6. Nếu deploy lỗi dependency

Kiểm tra tab log build của Streamlit Cloud. Các lỗi thường gặp:

- Thiếu package Python: bổ sung vào `requirements.txt`.
- Sai entrypoint: đảm bảo Main file path là `app.py`.
- Sai Python version: giữ `runtime.txt` là `python-3.11`.
- File quá lớn hoặc repo lồng thư mục: đưa `app.py` lên root repo.

## 7. Chạy local để kiểm tra

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

