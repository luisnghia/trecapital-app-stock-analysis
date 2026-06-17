# V23.24 - Fix So sánh doanh nghiệp peer crawl và ẩn page app

## 1. Sửa lỗi mã cùng ngành

Bản V23.23 dùng regex quá rộng khi đọc HTML/JSON động của Vietstock/FireAnt nên có thể nhận nhầm các chuỗi kỹ thuật như `STOCK`, `HOSTC` thành mã cổ phiếu. V23.24 bổ sung:

- `PEER_TICKER_BLACKLIST` để loại các token kỹ thuật/menu.
- `_is_probable_vn_ticker()` để giới hạn ticker hợp lệ.
- Không dùng fallback theo ngành quá rộng nếu không đủ cơ sở.
- Bổ sung crawl trang ngành Vietstock theo GICS level 4/3/2/1 nếu cùng-ngành widget không trả bảng tĩnh.
- Bổ sung danh mục dự phòng có kiểm soát cho nhóm dịch vụ sân bay/hàng hóa hàng không: SCS, NCT, SGN, AST, ACV, SAS, CIA, MAS, NAS.

## 2. Ẩn page gốc app

`app.py` vẫn là entrypoint kỹ thuật của Streamlit và render Tổng quan doanh nghiệp mặc định. V23.24 ẩn dòng `app` trong sidebar bằng CSS để người dùng chỉ thấy Tổng quan doanh nghiệp, Định giá chuyên sâu, So sánh doanh nghiệp.

## 3. Kiểm tra

- `python -m py_compile`: OK.
- `tools/run_phần2_self_check.py`: OK nếu môi trường đã cài dependencies.
