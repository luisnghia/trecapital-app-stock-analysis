# V23.70 - Deep audit loop and FCF table title final fix

## Nội dung kiểm tra
- Chạy kiểm thử tổng hợp theo nhóm: dữ liệu mẫu/loader, derived metrics, FCF/OE, WC vận hành, ROIC/ROCE, TTM, MOS, Module 2 valuation, bank valuation, Beneish/accrual/Jones/REM, Porter Moat, định dạng cột Giá mua MOS, format heatmap FCF, bỏ vnstock/KBS và vnstock/VCI.
- Chạy official tests: compileall, formula regression, module2 self-check.
- Chạy thêm 2 vòng formula regression sau khi sửa.

## Sửa lỗi phát hiện trong vòng deep audit
- Hai tiêu đề "Bảng phân tích sử dụng dòng tiền theo năm/quý" ở UI vẫn đang gọi `_render_bold_table_title(...)` thay vì `st.subheader(...)`.
- Đã sửa về `st.subheader(...)` để đồng bộ đúng với "Bảng PHÂN TÍCH CHỈ SỐ TC theo năm".

## Phạm vi chưa thể kiểm thử trong sandbox
- Không kiểm thử trực tiếp trình duyệt Streamlit do môi trường sandbox không có streamlit runtime.
- Không kiểm thử nguồn online thực tế do môi trường sandbox không có truy cập internet/API/token; đã kiểm tra nhánh dữ liệu offline/sample, loader CSV và loại bỏ option vnstock/KBS, vnstock/VCI trong code/UI.
