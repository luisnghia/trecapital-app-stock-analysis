# V23.16 - Việt hóa chỉ tiêu, sửa WACC theo từng năm và thêm biểu đồ nhiệt Chuỗi giá trị

## 1. Việt hóa giao diện
Các nhãn/chỉ tiêu tiếng Anh còn sót trong dashboard đã được chuyển sang tiếng Việt khi hiển thị: Owner Earnings → Owner Earnings, Moat score → Moat score, Moat level → Moat level, Internet evidence → Internet evidence, Cost advantage → Cost advantage, Differentiation → Differentiation, Low/Base/High/Weighted → Low/cơ sở/cao/trọng số.

## 2. Sửa WACC
V23.15 có thể cho WACC giống nhau qua các năm vì adapter Excel chưa lấy đúng các dòng nợ vay chịu lãi từ Bảng cân đối kế toán. Khi thiếu nợ vay, công thức rơi về 100% vốn chủ; nếu beta proxy cũng là một giá trị chung thì WACC sẽ trùng nhau.

V23.16 đã map thêm các dòng: vay và nợ thuê tài chính ngắn hạn, vay dài hạn đến hạn trả, vay và nợ thuê tài chính dài hạn, trái phiếu. Đồng thời beta proxy được tính rolling theo từng kỳ từ biến động doanh thu, biến động lợi nhuận và đòn bẩy, thay vì một số chung cho toàn bộ doanh nghiệp.

Công thức vẫn là: WACC = We × Ke + Wd × chi phí nợ vay × (1 - thuế suất).

## 3. Chuỗi giá trị có biểu đồ nhiệt
Tab Chuỗi giá trị đã có thêm Điểm nhiệt và Mức độ. Các ô tốt/theo dõi/cảnh báo được tô theo biểu đồ nhiệt để nhìn nhanh hoạt động nào là lợi thế, hoạt động nào cần kiểm tra thêm.
