# Deep Company Analysis - Báo cáo tiếng Việt V106

## Mục tiêu

V106 chuyển lớp trình bày báo cáo Deep Company Analysis sang **tiếng Việt mặc định** khi ứng dụng đang sử dụng giao diện tiếng Việt. Đây là thay đổi ở lớp export/presentation; không thay đổi dữ liệu, công thức, định giá hoặc logic ra quyết định đầu tư.

## Nguyên tắc khóa nguồn Q01-Q59

Appendix C tiếp tục là nguồn chuẩn duy nhất cho Q01-Q59 bằng tiếng Anh. V106 **không sửa** `appendix_c.py`, không thay đổi thứ tự, ID hay câu chữ khóa nguồn.

Trong báo cáo:

- `Câu hỏi (tiếng Việt)`: bản dịch phục vụ trình bày cho người dùng Việt Nam.
- `Nguyên văn nguồn (source lock)`: nguyên văn tiếng Anh từ Appendix C để kiểm tra đối chiếu.
- trạng thái, tiêu đề, mô tả, bảng tài chính, biểu đồ, chuẩn hóa chu kỳ và định tuyến sự kiện được trình bày bằng tiếng Việt.

Cách này bảo đảm báo cáo đọc được hoàn toàn bằng tiếng Việt nhưng vẫn giữ bằng chứng kiểm toán rằng source lock của Michael Shearn không bị thay đổi.

## Phạm vi Việt hóa

1. Trang bìa, metadata, tuyên bố ranh giới nghiên cứu.
2. `Thay đổi kể từ lần rà soát trước` và `Các điểm chưa rõ trọng yếu`.
3. 10 nhóm Q01-Q59 và bản dịch tiếng Việt của toàn bộ 59 câu hỏi.
4. Trạng thái hiển thị (`Unknown` -> `Chưa rõ`, `Reviewed` -> `Đã rà soát`, ...).
5. Bảng 10 năm + TTM: doanh thu, lợi nhuận, biên lợi nhuận, CFO/Capex/FCF, thanh khoản, nợ vay, ROIC/ROCE, vốn lưu động và CCC.
6. Tiêu đề và legend của toàn bộ biểu đồ định lượng.
7. Bảng chuẩn hóa chu kỳ và nhãn thống kê.
8. Định tuyến sự kiện -> Qxx cho nguyên liệu/chi phí, kiểm toán/quản trị và chậm tiến độ dự án.

Các trường kỹ thuật provenance `source_field`, `source_module`, `source_period`, `data_origin` được giữ nguyên tên schema để không phá contract liên mô-đun.

## Ranh giới kiến trúc giữ nguyên

- Trecapital Data Layer vẫn là financial SSOT.
- Appendix C / owner chapters vẫn là question/evidence SSOT.
- V100 vẫn sở hữu phép tính chuẩn hóa chu kỳ.
- V102 vẫn sở hữu phép biến đổi dữ liệu tài chính phục vụ report; V106 chỉ dùng lại dữ liệu/matrix đã có và Việt hóa trình bày.
- V103 vẫn sở hữu event -> question mapping; V106 chỉ Việt hóa cách hiển thị.
- V105 pagination hardening tiếp tục áp dụng cho mọi bảng và heading.
- Module 2 vẫn là chủ sở hữu duy nhất của định giá/MOS.
- AI vẫn là `Research Assistant`; chuyên viên phân tích sở hữu kết luận.
- Không weighted score, không MUA/GIỮ/BÁN tự động, không tự đổi MOS/giá trị nội tại, không tự đổi Investment Research Gate.

## QA

V106 có deterministic tests và acceptance riêng để xác minh:

- đủ 59 bản dịch Q01-Q59 theo đúng thứ tự;
- nguyên văn tiếng Anh source lock vẫn hiện diện để đối chiếu;
- các nhãn UI tiếng Anh cũ của V101-V103 không còn là nhãn chính trong báo cáo V106;
- Q33-Q52 thiếu bằng chứng vẫn hiển thị `Chưa rõ`;
- provenance schema không đổi;
- chart media còn đầy đủ;
- V105 `cantSplit`, repeated table header và keep-with-next heading vẫn hoạt động;
- full Deep Company Analysis regression và Streamlit health vẫn PASS.
