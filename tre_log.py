"""tre_log.py — Hệ thống log dùng chung cho module Top-Down.

Nguyên tắc xây dựng app số 10: luôn tạo log theo dõi khi app chạy để sửa lỗi.

Log được ghi ra file logs/topdown_YYYYMMDD.log và giữ một bản sao trong bộ nhớ để
tab "Nhật ký" hiển thị trực tiếp trên giao diện mà không cần mở file.

Lưu ý về tên cột: các khóa trong bản ghi log ("Thời điểm", "Mức độ", "Khu vực",
"Nội dung") được dùng trực tiếp làm tên cột của bảng nhật ký trên giao diện, nên
không được đổi tên nếu không sửa đồng thời ở module_topdown_dashboard.py.
"""

from __future__ import annotations

import logging
import traceback
from collections import deque
from datetime import datetime
from functools import wraps
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent
LOG_DIR = APP_ROOT / "logs"
try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
except Exception:  # noqa: BLE001
    pass

# Tên cột của bảng nhật ký — dùng chung giữa log và giao diện.
COT_THOI_DIEM = "Thời điểm"
COT_MUC_DO = "Mức độ"
COT_KHU_VUC = "Khu vực"
COT_NOI_DUNG = "Nội dung"

# Bộ đệm vòng: giữ 800 dòng log gần nhất để hiển thị trên giao diện.
_MEMORY_LOG: deque[dict] = deque(maxlen=800)

_LOGGER_NAME = "trecapital.topdown"
_INITIALIZED = False

# Ngưỡng thời gian (ms) để ghi log DEBUG cho một hàm được decorate.
# Các hàm tính toán lõi được gọi hàng trăm lần mỗi lần vẽ lại màn hình; nếu ghi log
# mọi lần gọi thì nhật ký sẽ bị ngập và mất tác dụng chẩn đoán. Chỉ những lần chạy
# chậm bất thường mới đáng được ghi lại.
NGUONG_LOG_CHAM_MS = 50.0


class _MemoryHandler(logging.Handler):
    """Ghi song song vào bộ nhớ để giao diện đọc được mà không phải đọc lại file."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            _MEMORY_LOG.append(
                {
                    COT_THOI_DIEM: datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S"),
                    COT_MUC_DO: record.levelname,
                    COT_KHU_VUC: getattr(record, "khu_vuc", "chung"),
                    COT_NOI_DUNG: record.getMessage(),
                }
            )
        except Exception:  # noqa: BLE001
            pass


def get_logger() -> logging.Logger:
    global _INITIALIZED
    logger = logging.getLogger(_LOGGER_NAME)
    if _INITIALIZED:
        return logger

    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")

    log_file = LOG_DIR / f"topdown_{datetime.now().strftime('%Y%m%d')}.log"
    try:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.INFO)  # File chỉ giữ INFO trở lên để không phình dung lượng.
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except Exception:  # noqa: BLE001
        # Môi trường chỉ đọc (một số sandbox cloud) vẫn phải chạy được.
        pass

    mh = _MemoryHandler()
    mh.setLevel(logging.DEBUG)
    logger.addHandler(mh)

    _INITIALIZED = True
    logger.info("[log] Khởi tạo hệ thống log Top-Down. File log: %s", log_file, extra={"khu_vuc": "log"})
    return logger


def log_event(muc_do: str, khu_vuc: str, noi_dung: str) -> None:
    """Ghi một sự kiện có gắn nhãn khu vực để dễ lọc khi sửa lỗi."""
    logger = get_logger()
    level = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
    }.get(str(muc_do).upper(), logging.INFO)
    logger.log(level, "[%s] %s", khu_vuc, noi_dung, extra={"khu_vuc": khu_vuc})


def memory_log_rows() -> list[dict]:
    """Trả về bản sao log trong bộ nhớ, mới nhất lên đầu."""
    return list(reversed(list(_MEMORY_LOG)))


def clear_memory_log() -> None:
    _MEMORY_LOG.clear()
    log_event("INFO", "log", "Người dùng đã xóa nhật ký hiển thị trên màn hình.")


def traced(khu_vuc: str):
    """Decorator: bắt và ghi lại lỗi của hàm tính toán kèm traceback đầy đủ.

    Khi app chạy sai ở bước nào, log sẽ chỉ rõ tên hàm và traceback thay vì để
    Streamlit ném lỗi thô ra màn hình.

    Về mức DEBUG: chỉ ghi khi hàm chạy chậm hơn NGUONG_LOG_CHAM_MS, vì các hàm lõi
    được gọi hàng trăm lần mỗi lần vẽ lại màn hình.
    """

    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            t0 = datetime.now()
            try:
                result = fn(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001
                log_event(
                    "ERROR",
                    khu_vuc,
                    f"{fn.__name__} lỗi: {exc.__class__.__name__}: {exc}\n{traceback.format_exc(limit=6)}",
                )
                raise
            dt = (datetime.now() - t0).total_seconds() * 1000
            if dt >= NGUONG_LOG_CHAM_MS:
                log_event("DEBUG", khu_vuc, f"{fn.__name__} chạy chậm: {dt:.1f} ms")
            return result

        return wrapper

    return deco
