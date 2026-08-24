from __future__ import annotations

"""Phase 8 governed Fisher Top-down/Sector context.

The service stores analyst-confirmed context snapshots only. It never writes Q01-Q59,
never calls an AI provider, and never turns the sector model into a security-level trade.
"""

from datetime import date, datetime, timezone
import hashlib
import json
import math
import re
from typing import Any

from ..repositories.sqlite_repository import ValidationError


SNAPSHOT_SCHEMA = "trecapital-topdown-sector-context-v1"
BENCHMARK_STATUSES = ("unverified", "historical_source", "analyst_verified")
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


def _text(value: Any, *, label: str, required: bool = False, limit: int = 12000) -> str:
    result = str(value or "").strip()
    if required and not result:
        raise ValidationError(f"{label} là bắt buộc.")
    if len(result) > limit:
        raise ValidationError(f"{label} không được vượt quá {limit:,} ký tự.")
    return result


def _number(value: Any, *, label: str, low: float, high: float) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{label} phải là số trong khoảng {low:g}–{high:g}.") from exc
    if not math.isfinite(result) or result < low or result > high:
        raise ValidationError(f"{label} phải là số trong khoảng {low:g}–{high:g}.")
    return result


def _integer(value: Any, *, label: str, low: int, high: int) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{label} phải nằm trong khoảng {low}–{high}.") from exc
    if result < low or result > high:
        raise ValidationError(f"{label} phải nằm trong khoảng {low}–{high}.")
    return result


def _canonical_json(payload: dict[str, Any]) -> str:
    try:
        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValidationError("Payload Top-down phải là JSON hợp lệ và không chứa NaN/Infinity.") from exc


def _payload_hash(payload_json: str) -> str:
    return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()


def _validate_payload(payload: Any) -> tuple[dict[str, Any], str, str]:
    if not isinstance(payload, dict):
        raise ValidationError("Payload Top-down phải là object JSON.")
    if payload.get("schema") != SNAPSHOT_SCHEMA:
        raise ValidationError(f"Payload Top-down phải dùng schema {SNAPSHOT_SCHEMA}.")
    methodology_version = _text(
        payload.get("methodology_version"), label="Phiên bản phương pháp", required=True, limit=120
    )
    generated_at = _text(payload.get("generated_at"), label="Thời điểm tạo mô hình", required=True, limit=80)
    try:
        datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError("Thời điểm tạo mô hình phải là ISO-8601 hợp lệ.") from exc
    _text(payload.get("cycle_phase"), label="Pha chu kỳ", required=True, limit=80)

    benchmark = payload.get("benchmark")
    if not isinstance(benchmark, dict):
        raise ValidationError("Payload Top-down thiếu benchmark.")
    _text(benchmark.get("id"), label="Benchmark ID", required=True, limit=120)
    _text(benchmark.get("name"), label="Tên benchmark", required=True, limit=500)
    benchmark_weights = benchmark.get("weights")
    if not isinstance(benchmark_weights, dict):
        raise ValidationError("Benchmark weights phải là object JSON.")
    normalized_benchmark_weights = {
        _text(code, label="Mã ngành benchmark", required=True, limit=16): _number(
            value, label=f"Tỷ trọng benchmark {code}", low=0, high=100
        )
        for code, value in benchmark_weights.items()
    }

    ranking = payload.get("ranking")
    weights = payload.get("weights")
    if not isinstance(ranking, list) or len(ranking) != 11:
        raise ValidationError("Bảng xếp hạng Top-down phải có đúng 11 ngành.")
    if not isinstance(weights, list) or len(weights) != 11:
        raise ValidationError("Bảng tỷ trọng Top-down phải có đúng 11 ngành.")

    ranking_codes: set[str] = set()
    for row in ranking:
        if not isinstance(row, dict):
            raise ValidationError("Mỗi dòng xếp hạng Top-down phải là object JSON.")
        code = _text(row.get("sector_code"), label="Mã ngành", required=True, limit=16)
        if code in ranking_codes:
            raise ValidationError(f"Mã ngành {code} bị trùng trong bảng xếp hạng.")
        ranking_codes.add(code)
        _text(row.get("sector_name"), label=f"Tên ngành {code}", required=True, limit=300)
        _number(row.get("score"), label=f"Điểm ngành {code}", low=0, high=100)

    weight_codes: set[str] = set()
    benchmark_total = 0.0
    proposed_total = 0.0
    for row in weights:
        if not isinstance(row, dict):
            raise ValidationError("Mỗi dòng tỷ trọng Top-down phải là object JSON.")
        code = _text(row.get("sector_code"), label="Mã ngành tỷ trọng", required=True, limit=16)
        if code in weight_codes:
            raise ValidationError(f"Mã ngành {code} bị trùng trong bảng tỷ trọng.")
        weight_codes.add(code)
        benchmark_weight = _number(
            row.get("benchmark_weight_pct"), label=f"Tỷ trọng benchmark {code}", low=0, high=100
        )
        proposed_weight = _number(
            row.get("proposed_weight_pct"), label=f"Tỷ trọng đề xuất {code}", low=0, high=100
        )
        tilt = _number(row.get("tilt_pct"), label=f"Độ lệch {code}", low=-100, high=100)
        if abs(benchmark_weight - normalized_benchmark_weights.get(code, float("nan"))) > 0.11:
            raise ValidationError(f"Tỷ trọng benchmark {code} không đồng nhất giữa payload.")
        if abs((proposed_weight - benchmark_weight) - tilt) > 0.21:
            raise ValidationError(f"Độ lệch tỷ trọng {code} không khớp công thức proposed − benchmark.")
        benchmark_total += benchmark_weight
        proposed_total += proposed_weight
    if ranking_codes != weight_codes or ranking_codes != set(normalized_benchmark_weights):
        raise ValidationError("Danh sách ngành phải đồng nhất giữa ranking, weights và benchmark.")
    if abs(benchmark_total - 100.0) > 0.5:
        raise ValidationError(f"Tổng tỷ trọng benchmark phải xấp xỉ 100%; hiện là {benchmark_total:.1f}%.")
    if abs(proposed_total - 100.0) > 0.5:
        raise ValidationError(f"Tổng tỷ trọng đề xuất phải xấp xỉ 100%; hiện là {proposed_total:.1f}%.")

    parameters = payload.get("parameters")
    if not isinstance(parameters, dict):
        raise ValidationError("Payload Top-down thiếu parameters.")
    _number(parameters.get("max_deviation_pct"), label="Giới hạn lệch benchmark", low=1, high=20)
    outlook = parameters.get("driver_outlook")
    if not isinstance(outlook, dict) or len(outlook) < 20:
        raise ValidationError("Payload phải chứa ít nhất 20 Portfolio Drivers.")
    for key, value in outlook.items():
        _text(key, label="Driver ID", required=True, limit=120)
        _number(value, label=f"Triển vọng driver {key}", low=-2, high=2)
    scoring_weights = parameters.get("scoring_weights")
    if not isinstance(scoring_weights, dict) or not scoring_weights:
        raise ValidationError("Payload Top-down thiếu trọng số chấm điểm.")
    scoring_total = sum(
        _number(value, label=f"Trọng số {key}", low=0, high=100)
        for key, value in scoring_weights.items()
    )
    if scoring_total <= 0:
        raise ValidationError("Tổng trọng số chấm điểm phải lớn hơn 0.")

    source_mapping_hash = _text(
        payload.get("source_mapping_sha256"), label="Source mapping SHA-256", required=True, limit=64
    ).lower()
    if not _HASH_RE.fullmatch(source_mapping_hash):
        raise ValidationError("Source mapping SHA-256 không hợp lệ.")
    payload_json = _canonical_json(payload)
    return payload, payload_json, methodology_version


def _selected_rows(payload: dict[str, Any], selected_sector_code: str) -> tuple[dict[str, Any], dict[str, Any]]:
    ranking = next((row for row in payload["ranking"] if row["sector_code"] == selected_sector_code), None)
    weight = next((row for row in payload["weights"] if row["sector_code"] == selected_sector_code), None)
    if ranking is None or weight is None:
        raise ValidationError("Ngành được chọn không tồn tại trong snapshot Top-down.")
    return ranking, weight


def save_topdown_sector_snapshot(
    repo,
    *,
    company_ref_id: int,
    review_id: int,
    payload: dict[str, Any],
    selected_sector_code: str,
    as_of_date,
    horizon_months: int = 12,
    benchmark_status: str = "unverified",
    benchmark_source_evidence_id: int | None = None,
    research_gaps: list[str] | tuple[str, ...] = (),
    analyst_confirmed: bool = False,
    change_reason: str,
    actor: str = "analyst",
) -> int:
    payload, payload_json, methodology_version = _validate_payload(payload)
    selected_sector_code = _text(
        selected_sector_code, label="Ngành gán cho doanh nghiệp", required=True, limit=16
    )
    ranking_row, weight_row = _selected_rows(payload, selected_sector_code)
    horizon_months = _integer(horizon_months, label="Time horizon", low=1, high=36)
    if benchmark_status not in BENCHMARK_STATUSES:
        raise ValidationError("Trạng thái benchmark không hợp lệ.")
    if benchmark_status == "historical_source" and payload["benchmark"].get("requires_update"):
        raise ValidationError("Benchmark cần cập nhật không thể được gắn historical_source.")
    if not analyst_confirmed:
        raise ValidationError("Analyst phải xác nhận snapshot chỉ là sector context, không phải kết luận đầu tư.")
    change_reason = _text(change_reason, label="Lý do lưu snapshot", required=True, limit=3000)
    as_of = repo._date(as_of_date)
    gaps = [_text(item, label="Research gap", required=True, limit=2000) for item in research_gaps]
    if payload["benchmark"].get("requires_update") and benchmark_status != "analyst_verified":
        default_gap = "Benchmark đang là dữ liệu khởi tạo/chưa được kiểm chứng từ nguồn chính thống."
        if default_gap not in gaps:
            gaps.append(default_gap)
    gaps_json = json.dumps(gaps, ensure_ascii=False, separators=(",", ":"))
    digest = _payload_hash(payload_json)

    with repo._conn() as c:
        review = repo.get_review(review_id, conn=c)
        if not review:
            raise ValidationError("Review không tồn tại.")
        if int(review["company_ref_id"]) != int(company_ref_id):
            raise ValidationError("Review không thuộc doanh nghiệp đang phân tích.")
        if review["status"] == "completed":
            raise ValidationError("Review đã finalize; Fisher Top-down & Sector Context là read-only.")
        if as_of > str(review["as_of_date"]):
            raise ValidationError("Ngày snapshot Top-down không được sau ngày as-of của review.")
        company = repo.get_company_ref(company_ref_id, conn=c)
        if not company:
            raise ValidationError("Doanh nghiệp không tồn tại.")

        evidence = None
        if benchmark_source_evidence_id is not None:
            evidence = repo._d(c.execute(
                """SELECT e.*,s.status source_status,s.document_date source_document_date,
                EXISTS(SELECT 1 FROM research_evidence newer
                  WHERE newer.source_id=e.source_id AND newer.evidence_key=e.evidence_key
                    AND newer.version_no>e.version_no) has_newer
                FROM research_evidence e JOIN research_sources s ON s.id=e.source_id WHERE e.id=?""",
                (benchmark_source_evidence_id,),
            ).fetchone())
            if not evidence or int(evidence["company_ref_id"]) != int(company_ref_id):
                raise ValidationError("Benchmark evidence không thuộc doanh nghiệp đang phân tích.")
            if evidence["source_status"] != "active":
                raise ValidationError("Nguồn benchmark đã archived.")
            if evidence.get("has_newer"):
                raise ValidationError("Benchmark evidence đã có version mới hơn; phải dùng exact evidence mới nhất.")
            evidence_as_of = evidence.get("evidence_date") or evidence.get("source_document_date")
            if evidence_as_of and str(evidence_as_of) > as_of:
                raise ValidationError("Benchmark evidence không được có ngày sau snapshot as-of.")
        if benchmark_status == "analyst_verified":
            if not evidence or evidence["verification_status"] != "verified":
                raise ValidationError("Benchmark analyst_verified phải gắn exact evidence đã verified.")

        duplicate = c.execute(
            """SELECT id FROM topdown_sector_snapshots
            WHERE review_id=? AND payload_hash=? AND selected_sector_code=?
              AND as_of_date=? AND benchmark_status=?""",
            (review_id, digest, selected_sector_code, as_of, benchmark_status),
        ).fetchone()
        if duplicate:
            raise ValidationError(f"Snapshot Top-down này đã được lưu (Snapshot #{duplicate['id']}).")
        previous = repo._d(c.execute(
            "SELECT * FROM topdown_sector_snapshots WHERE review_id=? ORDER BY version_no DESC,id DESC LIMIT 1",
            (review_id,),
        ).fetchone())
        version_no = int(previous["version_no"]) + 1 if previous else 1
        benchmark = payload["benchmark"]
        fields = {
            "company_ref_id": company_ref_id,
            "review_id": review_id,
            "version_no": version_no,
            "as_of_date": as_of,
            "horizon_months": horizon_months,
            "methodology_version": methodology_version,
            "selected_sector_code": selected_sector_code,
            "selected_sector_name": ranking_row["sector_name"],
            "cycle_phase": payload["cycle_phase"],
            "benchmark_id": benchmark["id"],
            "benchmark_name": benchmark["name"],
            "benchmark_status": benchmark_status,
            "benchmark_source_evidence_id": benchmark_source_evidence_id,
            "sector_score": float(ranking_row["score"]),
            "benchmark_weight_pct": float(weight_row["benchmark_weight_pct"]),
            "proposed_weight_pct": float(weight_row["proposed_weight_pct"]),
            "tilt_pct": float(weight_row["tilt_pct"]),
            "research_gaps_json": gaps_json,
            "payload_json": payload_json,
            "payload_hash": digest,
            "source_mapping_hash": payload["source_mapping_sha256"],
            "analyst_confirmed": 1,
            "change_reason": change_reason,
            "supersedes_snapshot_id": previous["id"] if previous else None,
            "created_by": _text(actor, label="Analyst", required=True, limit=300),
        }
        cur = c.execute(
            f"INSERT INTO topdown_sector_snapshots({','.join(fields)}) VALUES({','.join('?' for _ in fields)})",
            tuple(fields.values()),
        )
        snapshot_id = int(cur.lastrowid)
        created = repo._d(c.execute("SELECT * FROM topdown_sector_snapshots WHERE id=?", (snapshot_id,)).fetchone())
        repo._audit(
            c,
            company_ref_id=company_ref_id,
            review_id=review_id,
            actor=actor,
            action="append_version",
            entity_type="topdown_sector_snapshot",
            entity_id=snapshot_id,
            before=previous,
            after=created,
        )
        return snapshot_id


def _decode(row: dict[str, Any]) -> dict[str, Any]:
    result = dict(row)
    result["payload"] = json.loads(result.pop("payload_json"))
    result["research_gaps"] = json.loads(result.pop("research_gaps_json"))
    result["payload_hash_valid"] = _payload_hash(_canonical_json(result["payload"])) == result["payload_hash"]
    return result


def list_topdown_sector_snapshots(repo, review_id: int, *, conn=None) -> list[dict[str, Any]]:
    sql = "SELECT * FROM topdown_sector_snapshots WHERE review_id=? ORDER BY version_no DESC,id DESC"

    def run(c):
        return [_decode(dict(row)) for row in c.execute(sql, (review_id,))]

    if conn is not None:
        return run(conn)
    with repo._conn() as c:
        return run(c)


def snapshot_topdown_for_review(repo, review_id: int, *, conn=None) -> dict[str, Any]:
    rows = list_topdown_sector_snapshots(repo, review_id, conn=conn)
    latest = rows[0] if rows else None
    history = [
        {
            "id": row["id"],
            "version_no": row["version_no"],
            "as_of_date": row["as_of_date"],
            "selected_sector_code": row["selected_sector_code"],
            "benchmark_status": row["benchmark_status"],
            "payload_hash": row["payload_hash"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]
    return {
        "schema": "governed-fisher-topdown-sector-v1",
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "latest": latest,
        "version_history": history,
    }


def snapshot_is_stale(snapshot: dict[str, Any], *, today: date | None = None) -> bool:
    today = today or date.today()
    try:
        as_of = date.fromisoformat(str(snapshot["as_of_date"])[:10])
        horizon_months = int(snapshot["horizon_months"])
    except (KeyError, TypeError, ValueError):
        return True
    return (today - as_of).days > horizon_months * 31


__all__ = [
    "BENCHMARK_STATUSES",
    "SNAPSHOT_SCHEMA",
    "list_topdown_sector_snapshots",
    "save_topdown_sector_snapshot",
    "snapshot_is_stale",
    "snapshot_topdown_for_review",
]
