from __future__ import annotations

"""Phase 3B durable peer-comparison snapshots linked to an analyst review.

The comparison engine remains the existing Trecapital peer page. This service only validates and
persists an analyst-approved result; it never fetches peers, recalculates financial statements, or
writes Q01-Q59 assessments automatically.
"""

from datetime import datetime, timezone
import hashlib
import json
import math
import re
from typing import Any

import pandas as pd

from ..repositories.sqlite_repository import ValidationError


PEER_SNAPSHOT_SCHEMA_SQL = [
    """
    CREATE TABLE IF NOT EXISTS peer_comparison_snapshots(
        company_ref_id BIGINT NOT NULL REFERENCES checklist_company_refs(id),
        review_id BIGINT NOT NULL REFERENCES research_reviews(id),
        version_no INTEGER NOT NULL,
        as_of_date TEXT NOT NULL,
        base_ticker TEXT NOT NULL,
        target_mos_pct DOUBLE PRECISION,
        peer_count INTEGER NOT NULL CHECK(peer_count BETWEEN 2 AND 10),
        source_module TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        payload_hash TEXT NOT NULL,
        save_reason TEXT NOT NULL,
        created_by TEXT,
        created_at TEXT NOT NULL,
        PRIMARY KEY(company_ref_id, review_id, version_no)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_peer_snapshots_review ON peer_comparison_snapshots(review_id,version_no)",
    "CREATE INDEX IF NOT EXISTS ix_peer_snapshots_company_date ON peer_comparison_snapshots(company_ref_id,as_of_date,version_no)",
]

PEER_QUESTION_IDS = ("Q19", "Q22", "Q24", "Q26", "Q32")
MAX_PEERS = 10
_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9]{1,5}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_peer_snapshot_schema(repo) -> None:
    with repo._conn() as c:
        for statement in PEER_SNAPSHOT_SCHEMA_SQL:
            c.execute(statement)


def _json_value(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return None if not math.isfinite(value) else float(value)
    if hasattr(value, "item"):
        try:
            return _json_value(value.item())
        except Exception:
            pass
    return str(value)


def normalize_peer_result(result: Any, *, base_ticker: str) -> pd.DataFrame:
    """Validate and rank the existing Trecapital peer result without inventing missing scores."""
    if isinstance(result, pd.DataFrame):
        frame = result.copy()
    elif isinstance(result, list):
        frame = pd.DataFrame(result)
    else:
        raise ValidationError("Kết quả peer phải là bảng từ trang So sánh doanh nghiệp.")
    if frame.empty or "Mã" not in frame.columns:
        raise ValidationError("Kết quả peer chưa có cột Mã hoặc đang trống.")

    base = str(base_ticker or "").strip().upper()
    if not _TICKER_RE.fullmatch(base):
        raise ValidationError("Mã doanh nghiệp gốc không hợp lệ.")
    frame["Mã"] = frame["Mã"].astype(str).str.strip().str.upper()
    frame = frame[frame["Mã"].map(lambda x: bool(_TICKER_RE.fullmatch(x)))].copy()
    frame = frame.drop_duplicates(subset=["Mã"], keep="last")
    if base not in set(frame["Mã"]):
        raise ValidationError(f"Kết quả peer không chứa mã đang phân tích {base}.")
    if "Mã đang phân tích" not in frame.columns:
        raise ValidationError(
            "Kết quả peer thiếu dấu vết mã gốc; hãy chạy lại từ trang So sánh doanh nghiệp."
        )
    base_flags = frame["Mã đang phân tích"].fillna(False).astype(bool)
    marked_bases = frame.loc[base_flags, "Mã"].tolist()
    if marked_bases != [base]:
        marked = ", ".join(marked_bases) if marked_bases else "không có"
        raise ValidationError(
            f"Kết quả peer được tạo cho mã gốc {marked}, không thể gắn vào review {base}."
        )
    if len(frame) < 2:
        raise ValidationError("Cần tối thiểu mã đang phân tích và 1 doanh nghiệp peer.")
    if len(frame) > MAX_PEERS:
        raise ValidationError(f"Mỗi snapshot chỉ được lưu tối đa {MAX_PEERS} doanh nghiệp.")

    if "Điểm tổng hợp" not in frame.columns:
        raise ValidationError("Kết quả peer thiếu Điểm tổng hợp của engine Trecapital.")
    frame["Điểm tổng hợp"] = pd.to_numeric(frame["Điểm tổng hợp"], errors="coerce")
    if frame["Điểm tổng hợp"].notna().sum() < 2:
        raise ValidationError("Chưa đủ điểm tổng hợp để xếp hạng peer.")

    mos = pd.to_numeric(frame.get("MOS hiện tại %"), errors="coerce") if "MOS hiện tại %" in frame else pd.Series(index=frame.index, dtype=float)
    moat = pd.to_numeric(frame.get("Moat score"), errors="coerce") if "Moat score" in frame else pd.Series(index=frame.index, dtype=float)
    frame = frame.assign(
        _score_sort=frame["Điểm tổng hợp"].fillna(-999.0),
        _mos_sort=mos.reindex(frame.index).fillna(-999.0),
        _moat_sort=moat.reindex(frame.index).fillna(-999.0),
    )
    frame = frame.sort_values(
        ["_score_sort", "_mos_sort", "_moat_sort", "Mã"],
        ascending=[False, False, False, True],
    ).drop(columns=["_score_sort", "_mos_sort", "_moat_sort"]).reset_index(drop=True)
    frame["Xếp hạng"] = range(1, len(frame) + 1)
    frame["Mã đang phân tích"] = frame["Mã"].eq(base)
    return frame


def build_peer_payload(
    result: Any,
    *,
    base_ticker: str,
    as_of_date: str,
    target_mos_pct: float | None,
) -> dict[str, Any]:
    frame = normalize_peer_result(result, base_ticker=base_ticker)
    rows = [
        {str(key): _json_value(value) for key, value in record.items()}
        for record in frame.to_dict("records")
    ]
    return {
        "snapshot_schema": "phase3b-peer-ranking-v1",
        "base_ticker": str(base_ticker).strip().upper(),
        "as_of_date": str(as_of_date),
        "target_mos_pct": _json_value(target_mos_pct),
        "peer_count": len(rows),
        "question_links": list(PEER_QUESTION_IDS),
        "source_module": "Trecapital So sánh doanh nghiệp",
        "rows": rows,
    }


def save_peer_snapshot(
    repo,
    *,
    company_ref_id: int,
    review_id: int,
    result: Any,
    base_ticker: str,
    target_mos_pct: float | None,
    save_reason: str,
    actor: str,
) -> int:
    reason = str(save_reason or "").strip()
    if not reason:
        raise ValidationError("Lý do lưu Peer Snapshot là bắt buộc.")
    ensure_peer_snapshot_schema(repo)
    with repo._conn() as c:
        review = repo.get_review(review_id, conn=c)
        if not review:
            raise ValidationError("Review không tồn tại.")
        if int(review["company_ref_id"]) != int(company_ref_id):
            raise ValidationError("Peer Snapshot không thuộc đúng doanh nghiệp của review.")
        if review["status"] == "completed":
            raise ValidationError("Review đã finalize; Peer Snapshot bị khóa và không thể ghi thêm.")

        payload = build_peer_payload(
            result,
            base_ticker=base_ticker,
            as_of_date=review["as_of_date"],
            target_mos_pct=target_mos_pct,
        )
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        payload_hash = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        row = c.execute(
            "SELECT COALESCE(MAX(version_no),0) v FROM peer_comparison_snapshots WHERE company_ref_id=? AND review_id=?",
            (company_ref_id, review_id),
        ).fetchone()
        version = int(row["v"] or 0) + 1
        created_at = _now()
        c.execute(
            """INSERT INTO peer_comparison_snapshots(
                company_ref_id,review_id,version_no,as_of_date,base_ticker,target_mos_pct,
                peer_count,source_module,payload_json,payload_hash,save_reason,created_by,created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                company_ref_id, review_id, version, review["as_of_date"], payload["base_ticker"],
                target_mos_pct, payload["peer_count"], payload["source_module"], encoded,
                payload_hash, reason, actor, created_at,
            ),
        )
        after = {
            "company_ref_id": company_ref_id,
            "review_id": review_id,
            "version_no": version,
            "as_of_date": review["as_of_date"],
            "base_ticker": payload["base_ticker"],
            "target_mos_pct": target_mos_pct,
            "peer_count": payload["peer_count"],
            "payload_hash": payload_hash,
            "save_reason": reason,
            "created_by": actor,
            "created_at": created_at,
        }
        repo._audit(
            c,
            company_ref_id=company_ref_id,
            review_id=review_id,
            actor=actor,
            action="append_version",
            entity_type="peer_comparison_snapshot",
            entity_id=f"review-{review_id}-v{version}",
            before=None,
            after=after,
        )
        return version


def list_peer_snapshots(repo, review_id: int, *, conn=None) -> list[dict[str, Any]]:
    def query(c):
        return [dict(row) for row in c.execute(
            """SELECT company_ref_id,review_id,version_no,as_of_date,base_ticker,target_mos_pct,
                      peer_count,source_module,payload_hash,save_reason,created_by,created_at
               FROM peer_comparison_snapshots WHERE review_id=? ORDER BY version_no DESC""",
            (review_id,),
        )]

    if conn is not None:
        return query(conn)
    ensure_peer_snapshot_schema(repo)
    with repo._conn() as c:
        return query(c)


def get_peer_snapshot(repo, review_id: int, version_no: int | None = None, *, conn=None) -> dict[str, Any] | None:
    def query(c):
        if version_no is None:
            row = c.execute(
                "SELECT * FROM peer_comparison_snapshots WHERE review_id=? ORDER BY version_no DESC LIMIT 1",
                (review_id,),
            ).fetchone()
        else:
            row = c.execute(
                "SELECT * FROM peer_comparison_snapshots WHERE review_id=? AND version_no=?",
                (review_id, int(version_no)),
            ).fetchone()
        if not row:
            return None
        out = dict(row)
        out["payload"] = json.loads(out.pop("payload_json"))
        return out

    if conn is not None:
        return query(conn)
    ensure_peer_snapshot_schema(repo)
    with repo._conn() as c:
        return query(c)


def snapshot_peer_payload_for_review(repo, review_id: int, *, conn=None) -> dict[str, Any] | None:
    """Return the exact latest approved peer payload embedded when a review is finalized."""
    row = get_peer_snapshot(repo, review_id, conn=conn)
    if not row:
        return None
    return {
        "version_no": row["version_no"],
        "payload_hash": row["payload_hash"],
        "save_reason": row["save_reason"],
        "created_by": row.get("created_by"),
        "created_at": row["created_at"],
        "payload": row["payload"],
    }


__all__ = [
    "MAX_PEERS",
    "PEER_QUESTION_IDS",
    "PEER_SNAPSHOT_SCHEMA_SQL",
    "build_peer_payload",
    "ensure_peer_snapshot_schema",
    "get_peer_snapshot",
    "list_peer_snapshots",
    "normalize_peer_result",
    "save_peer_snapshot",
    "snapshot_peer_payload_for_review",
]
