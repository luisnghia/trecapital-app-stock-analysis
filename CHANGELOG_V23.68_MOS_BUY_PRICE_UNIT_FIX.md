# V23.68 - Sửa đơn vị cột Giá mua MOS trong Báo cáo tổng hợp

## Nội dung sửa

1. Sửa formatter của trang **Báo cáo tổng hợp toàn bộ nội dung** cho bảng **Bảng định giá theo từng phương pháp**.
2. Các cột như **Giá mua MOS 30%**, **Giá mua MOS 50%**, **Giá mua MOS chọn** được xác định là **giá mua theo đồng/cp**, không phải chỉ tiêu phần trăm.
3. Quy tắc định dạng mới: nếu tên cột có đồng thời `Giá` và `MOS`, ưu tiên định dạng giá trị tiền/cổ phiếu với 0 số thập phân, không thêm ký hiệu `%`.
4. Các cột phần trăm thật như **MOS hiện tại %**, **MOS chọn %**, **Chênh lệch so với MOS yêu cầu %**, **Trọng số %** vẫn giữ định dạng phần trăm.

## Phạm vi ảnh hưởng

- Chỉ thay đổi định dạng hiển thị trong báo cáo tổng hợp/print report.
- Không thay đổi công thức định giá, MOS, trọng số, dữ liệu, cấu trúc bảng hoặc UI các tab phân tích.
