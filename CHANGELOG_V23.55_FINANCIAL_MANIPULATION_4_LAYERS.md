# V23.55 - Financial Manipulation 4 Layers + Global Tab Color Fix

## Cập nhật chính

1. Mở rộng tab `Thao túng tài chính` thành 4 lớp:
   - Lớp 1: Beneish M-Score.
   - Lớp 2: Accrual Quality / Sloan.
   - Lớp 3: Modified Jones / Kothari discretionary accruals.
   - Lớp 4: Real Earnings Management (REM).

2. Bổ sung công thức, logic tính, diễn giải, ngưỡng cảnh báo và note từng dòng cho 4 lớp.

3. Bổ sung file hướng dẫn công thức:
   - `docs/FINANCIAL_MANIPULATION_4_LAYERS_GUIDE.md`.

4. Cập nhật bảng `Tóm tắt công thức chính` trong tab `Công thức & giả định`.

5. Bổ sung thuật ngữ/từ viết tắt:
   - AEM, REM, Sloan accrual ratio, Discretionary Accruals, Modified Jones, Kothari, Abnormal CFO, Abnormal PROD, Abnormal DISEXP.

6. Sửa màu tab mặc định trên toàn bộ app thông qua `ui_oaktree_theme.py`:
   - Tab thường có nền vàng/xanh nhạt.
   - Tab hover sáng hơn.
   - Tab active nền xanh đậm/vàng, chữ trắng rõ.

## Kiểm tra

- `python -m py_compile module2_engine.py module2_dashboard.py module1_dashboard.py ui_oaktree_theme.py`: OK.
- `python tools/run_module2_self_check.py`: OK.
