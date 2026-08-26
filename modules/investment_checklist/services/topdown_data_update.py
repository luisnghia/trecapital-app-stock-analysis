from __future__ import annotations

"""Phase 9 — governed latest-on-click data intake for Fisher Portfolio Drivers.

Network access is deliberately isolated in ``run_latest_data_update`` and only happens when the
analyst explicitly invokes it from the UI. Importing this module, opening the Checklist, changing a
section, or finalizing a review never polls a source. Observations and suggestions are append-only;
an analyst decision is required before a suggested driver outlook is applied to the Top-down page.
"""

from calendar import monthrange
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
from typing import Any, Iterable

import httpx

from ..repositories.sqlite_repository import ValidationError


APP_ROOT = Path(__file__).resolve().parents[3]
REGISTRY_PATH = APP_ROOT / "configs" / "topdown_phase9_sources.json"
DRIVER_PATH = APP_ROOT / "configs" / "sector_drivers_fisher.json"
METHOD_VERSION = "phase9-latest-on-click-v1"
_SAFE_CODE = re.compile(r"^[A-Za-z0-9_.:-]{1,160}$")


class SourceFetchError(RuntimeError):
    """A safe, user-displayable source error without credentials or response bodies."""


@dataclass(frozen=True)
class LatestObservation:
    driver_id: str
    source_code: str
    source_tier: str
    series_code: str
    source_url: str
    period_label: str
    observation_date: str
    published_at: str | None
    retrieved_at: str
    frequency: str
    value_numeric: float
    previous_value_numeric: float | None
    unit: str
    observation_status: str
    freshness_status: str
    payload_hash: str
    raw_locator: str

    @property
    def delta_numeric(self) -> float | None:
        if self.previous_value_numeric is None:
            return None
        return self.value_numeric - self.previous_value_numeric


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
            default=str,
        )
    except (TypeError, ValueError) as exc:
        raise ValidationError("Payload Phase 9 phải là JSON hợp lệ, không chứa NaN/Infinity.") from exc


def _sha256(value: str | bytes) -> str:
    raw = value if isinstance(value, bytes) else value.encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def load_source_registry() -> dict[str, Any]:
    try:
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        driver_catalog = json.loads(DRIVER_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"Không đọc được Source Registry Phase 9: {exc}") from exc
    entries = registry.get("driver_sources")
    if not isinstance(entries, list):
        raise ValidationError("Source Registry Phase 9 thiếu driver_sources.")
    expected = {str(row["id"]) for row in driver_catalog.get("drivers", [])}
    actual = [str(row.get("driver_id", "")) for row in entries]
    if len(actual) != len(set(actual)):
        raise ValidationError("Source Registry Phase 9 có driver bị trùng.")
    if set(actual) != expected:
        missing = sorted(expected - set(actual))
        extra = sorted(set(actual) - expected)
        raise ValidationError(f"Source Registry không khớp 26 drivers; thiếu={missing}, thừa={extra}.")
    sources = registry.get("sources")
    if not isinstance(sources, dict):
        raise ValidationError("Source Registry Phase 9 thiếu sources.")
    for entry in entries:
        source_code = str(entry.get("source_code", ""))
        if source_code not in sources:
            raise ValidationError(f"Nguồn {source_code} của {entry.get('driver_id')} chưa được khai báo.")
    return registry


def source_registry_hash(registry: dict[str, Any] | None = None) -> str:
    return _sha256(_canonical_json(registry or load_source_registry()))


def source_coverage_rows(registry: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    registry = registry or load_source_registry()
    sources = registry["sources"]
    rows = []
    for entry in registry["driver_sources"]:
        source = sources[entry["source_code"]]
        mode = str(entry["mode"])
        rows.append(
            {
                "Driver": entry["driver_name"],
                "Driver ID": entry["driver_id"],
                "Nguồn": source["publisher"],
                "Series": entry["series_code"],
                "Cơ chế": (
                    "Tự động khi bấm Cập nhật"
                    if mode in {"automatic", "automatic_proxy"}
                    else "Tự động khi có API key"
                    if mode == "automatic_optional_key"
                    else "Research gap — cần nguồn/analyst"
                ),
                "Tần suất nguồn": entry["frequency"],
                "Ghi chú": entry.get("note", ""),
                "URL": source.get("homepage", ""),
            }
        )
    return rows


def automatic_driver_ids(registry: dict[str, Any] | None = None) -> list[str]:
    registry = registry or load_source_registry()
    return [
        str(entry["driver_id"])
        for entry in registry["driver_sources"]
        if entry.get("adapter")
    ]


def _finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _period_date(period: str, frequency: str) -> date:
    raw = str(period or "").strip()
    if re.fullmatch(r"\d{4}", raw):
        return date(int(raw), 12, 31)
    if re.fullmatch(r"\d{4}-\d{2}", raw):
        year, month = (int(part) for part in raw.split("-"))
        return date(year, month, monthrange(year, month)[1])
    quarter = re.fullmatch(r"(\d{4})Q([1-4])", raw, flags=re.I)
    if quarter:
        year, q = int(quarter.group(1)), int(quarter.group(2))
        month = q * 3
        return date(year, month, monthrange(year, month)[1])
    try:
        return date.fromisoformat(raw[:10])
    except ValueError as exc:
        raise SourceFetchError(f"Kỳ dữ liệu không hợp lệ: {raw[:40]}") from exc


def _freshness(observation_date: date, *, stale_after_days: int, today: date) -> str:
    if stale_after_days <= 0:
        return "event_driven"
    age = (today - observation_date).days
    if age <= stale_after_days:
        return "current"
    if age <= stale_after_days * 2:
        return "aging"
    return "stale"


def _points(values: Iterable[tuple[str, Any]]) -> list[tuple[str, date, float]]:
    result: list[tuple[str, date, float]] = []
    for period, raw_value in values:
        value = _finite(raw_value)
        if value is None:
            continue
        try:
            parsed = _period_date(str(period), "")
        except SourceFetchError:
            continue
        result.append((str(period), parsed, value))
    result.sort(key=lambda item: item[1], reverse=True)
    return result


def _request_json(client: httpx.Client, url: str, *, params: dict[str, Any]) -> tuple[Any, str, str]:
    try:
        response = client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
    except httpx.TimeoutException as exc:
        raise SourceFetchError("Nguồn hết thời gian phản hồi.") from exc
    except httpx.HTTPStatusError as exc:
        raise SourceFetchError(f"Nguồn trả HTTP {exc.response.status_code}.") from exc
    except (httpx.NetworkError, ValueError) as exc:
        raise SourceFetchError(f"Không đọc được JSON từ nguồn: {type(exc).__name__}.") from exc
    # Never persist query parameters: FRED/EIA keys and future signed parameters must not enter
    # observations, audit rows, immutable snapshots or exported tables. Series/period provenance is
    # preserved separately in ``series_code`` and ``raw_locator``.
    return payload, str(response.request.url.copy_with(query=None)), _sha256(response.content)


def _build_observation(
    entry: dict[str, Any],
    source: dict[str, Any],
    *,
    points: list[tuple[str, date, float]],
    source_url: str,
    payload_hash: str,
    retrieved_at: datetime,
    observation_status: str,
) -> LatestObservation:
    # IMF/WEO and similar sources may include long-range forecasts. "Latest on click" means the
    # newest observation/estimate available for the current analytical year, not the farthest
    # forecast horizon returned by the payload.
    points = [point for point in points if point[1].year <= retrieved_at.year]
    if not points:
        raise SourceFetchError("Nguồn không trả quan sát số hợp lệ.")
    latest = points[0]
    previous = points[1] if len(points) > 1 else None
    return LatestObservation(
        driver_id=str(entry["driver_id"]),
        source_code=str(entry["source_code"]),
        source_tier=str(source["tier"]),
        series_code=str(entry["series_code"]),
        source_url=source_url,
        period_label=latest[0],
        observation_date=latest[1].isoformat(),
        published_at=None,
        retrieved_at=retrieved_at.isoformat(timespec="seconds"),
        frequency=str(entry["frequency"]),
        value_numeric=latest[2],
        previous_value_numeric=previous[2] if previous else None,
        unit=str(entry["unit"]),
        observation_status=observation_status,
        freshness_status=_freshness(
            latest[1],
            stale_after_days=int(entry.get("stale_after_days") or 0),
            today=retrieved_at.date(),
        ),
        payload_hash=payload_hash,
        raw_locator=f"{entry['series_code']} · period {latest[0]}",
    )


def _fetch_world_bank(
    client: httpx.Client,
    entry: dict[str, Any],
    source: dict[str, Any],
    retrieved_at: datetime,
) -> LatestObservation:
    code = str(entry["series_code"])
    if not _SAFE_CODE.fullmatch(code):
        raise SourceFetchError("World Bank series code không hợp lệ.")
    url = f"{source['base_url']}/country/VNM/indicator/{code}"
    payload, source_url, digest = _request_json(
        client, url, params={"format": "json", "mrnev": 6, "per_page": 12}
    )
    if not isinstance(payload, list) or len(payload) < 2 or not isinstance(payload[1], list):
        raise SourceFetchError("World Bank trả cấu trúc dữ liệu không mong đợi.")
    rows = payload[1]
    points = _points((str(row.get("date", "")), row.get("value")) for row in rows if isinstance(row, dict))
    status = str(next((row.get("obs_status") for row in rows if row.get("value") is not None), "actual") or "actual")
    return _build_observation(
        entry,
        source,
        points=points,
        source_url=source_url,
        payload_hash=digest,
        retrieved_at=retrieved_at,
        observation_status=status,
    )


def _imf_country_values(payload: Any, series_code: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    values = payload.get("values", payload)
    if isinstance(values, dict) and series_code in values:
        values = values[series_code]
    if isinstance(values, dict):
        for country_key in ("VNM", "VN"):
            country = values.get(country_key)
            if isinstance(country, dict):
                return country
        # Some API versions wrap the values in another named object.
        for nested in values.values():
            if isinstance(nested, dict):
                for country_key in ("VNM", "VN"):
                    country = nested.get(country_key)
                    if isinstance(country, dict):
                        return country
    return {}


def _fetch_imf(
    client: httpx.Client,
    entry: dict[str, Any],
    source: dict[str, Any],
    retrieved_at: datetime,
) -> LatestObservation:
    code = str(entry["series_code"])
    if not _SAFE_CODE.fullmatch(code):
        raise SourceFetchError("IMF series code không hợp lệ.")
    url = f"{source['base_url']}/{code}/VNM"
    payload, source_url, digest = _request_json(client, url, params={})
    values = _imf_country_values(payload, code)
    points = _points((str(period), value) for period, value in values.items())
    return _build_observation(
        entry,
        source,
        points=points,
        source_url=source_url,
        payload_hash=digest,
        retrieved_at=retrieved_at,
        observation_status="IMF estimate/forecast",
    )


def _fetch_fred(
    client: httpx.Client,
    entry: dict[str, Any],
    source: dict[str, Any],
    retrieved_at: datetime,
    api_key: str,
) -> LatestObservation:
    code = str(entry["series_code"])
    if not _SAFE_CODE.fullmatch(code):
        raise SourceFetchError("FRED series code không hợp lệ.")
    payload, source_url, digest = _request_json(
        client,
        f"{source['base_url']}/series/observations",
        params={
            "series_id": code,
            "api_key": api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 8,
        },
    )
    rows = payload.get("observations") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise SourceFetchError("FRED trả cấu trúc dữ liệu không mong đợi.")
    points = _points((str(row.get("date", "")), row.get("value")) for row in rows if isinstance(row, dict))
    return _build_observation(
        entry,
        source,
        points=points,
        source_url=source_url,
        payload_hash=digest,
        retrieved_at=retrieved_at,
        observation_status="published",
    )


def _fetch_eia(
    client: httpx.Client,
    entry: dict[str, Any],
    source: dict[str, Any],
    retrieved_at: datetime,
    api_key: str,
) -> LatestObservation:
    code = str(entry["series_code"])
    if not _SAFE_CODE.fullmatch(code):
        raise SourceFetchError("EIA series code không hợp lệ.")
    payload, source_url, digest = _request_json(
        client,
        f"{source['base_url']}/seriesid/{code}",
        params={"api_key": api_key, "length": 8, "sort[0][column]": "period", "sort[0][direction]": "desc"},
    )
    response = payload.get("response") if isinstance(payload, dict) else None
    rows = response.get("data") if isinstance(response, dict) else None
    if not isinstance(rows, list):
        raise SourceFetchError("EIA trả cấu trúc dữ liệu không mong đợi.")
    points = _points(
        (str(row.get("period", row.get("date", ""))), row.get("value"))
        for row in rows
        if isinstance(row, dict)
    )
    return _build_observation(
        entry,
        source,
        points=points,
        source_url=source_url,
        payload_hash=digest,
        retrieved_at=retrieved_at,
        observation_status="published",
    )


def fetch_latest_observation(
    client: httpx.Client,
    entry: dict[str, Any],
    registry: dict[str, Any],
    *,
    api_keys: dict[str, str],
    retrieved_at: datetime,
) -> LatestObservation:
    source = registry["sources"][entry["source_code"]]
    adapter = entry.get("adapter")
    if adapter == "world_bank":
        return _fetch_world_bank(client, entry, source, retrieved_at)
    if adapter == "imf_datamapper":
        return _fetch_imf(client, entry, source, retrieved_at)
    if adapter == "fred":
        key = str(api_keys.get("FRED_API_KEY", "")).strip()
        if not key:
            raise SourceFetchError("Thiếu FRED_API_KEY; nguồn tùy chọn chưa được gọi.")
        return _fetch_fred(client, entry, source, retrieved_at, key)
    if adapter == "eia_seriesid":
        key = str(api_keys.get("EIA_API_KEY", "")).strip()
        if not key:
            raise SourceFetchError("Thiếu EIA_API_KEY; nguồn tùy chọn chưa được gọi.")
        return _fetch_eia(client, entry, source, retrieved_at, key)
    raise SourceFetchError("Driver chưa có adapter tự động an toàn.")


def _suggestion(entry: dict[str, Any], observation: LatestObservation) -> dict[str, Any]:
    rule = entry.get("score_rule") or {}
    previous = observation.previous_value_numeric
    if not rule.get("enabled"):
        return {
            "suggested_score": None,
            "confidence": 2,
            "rationale": (
                f"Đã lấy {observation.value_numeric:g} {observation.unit} tại kỳ {observation.period_label}; "
                "series chỉ là proxy nên app không tự chấm điểm."
            ),
            "data_gap_reason": str(entry.get("note") or "Cần analyst xác nhận proxy."),
        }
    if previous is None:
        return {
            "suggested_score": None,
            "confidence": 2,
            "rationale": f"Đã lấy kỳ {observation.period_label}, nhưng chưa có kỳ trước để tính thay đổi.",
            "data_gap_reason": "Thiếu quan sát kỳ trước.",
        }
    mild = float(rule["mild_delta"])
    strong = float(rule["strong_delta"])
    direction = int(entry.get("direction_multiplier", 1))
    directional_delta = (observation.value_numeric - previous) * direction
    if directional_delta >= strong:
        score = 2
    elif directional_delta >= mild:
        score = 1
    elif directional_delta <= -strong:
        score = -2
    elif directional_delta <= -mild:
        score = -1
    else:
        score = 0
    return {
        "suggested_score": score,
        "confidence": 3 if observation.observation_status != "published" else 4,
        "rationale": (
            f"{entry['driver_name']}: {previous:g} → {observation.value_numeric:g} {observation.unit} "
            f"(kỳ mới nhất {observation.period_label}); quy tắc hướng biến đề xuất {score:+d}. "
            "Đây chỉ là suggestion, không phải kết luận đầu tư."
        ),
        "data_gap_reason": None,
    }


def _api_keys(values: dict[str, str] | None) -> dict[str, str]:
    if values is not None:
        return {str(key): str(value) for key, value in values.items()}
    return {key: os.getenv(key, "") for key in ("FRED_API_KEY", "EIA_API_KEY")}


def run_latest_data_update(
    repo,
    *,
    company_ref_id: int,
    review_id: int,
    driver_ids: Iterable[str] | None = None,
    actor: str = "analyst",
    http_client: httpx.Client | None = None,
    api_keys: dict[str, str] | None = None,
    now: datetime | None = None,
) -> int:
    """Fetch the newest published observation only after an explicit UI click."""

    registry = load_source_registry()
    selected_ids = set(driver_ids or automatic_driver_ids(registry))
    entries = [
        entry for entry in registry["driver_sources"]
        if entry.get("adapter") and str(entry["driver_id"]) in selected_ids
    ]
    if not entries:
        raise ValidationError("Chưa chọn driver nào có adapter tự động.")
    unknown = selected_ids - {str(entry["driver_id"]) for entry in registry["driver_sources"]}
    if unknown:
        raise ValidationError(f"Driver không tồn tại: {', '.join(sorted(unknown))}.")
    actor = str(actor or "").strip()
    if not actor:
        raise ValidationError("Analyst là bắt buộc.")
    started = now or datetime.now(timezone.utc)
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    requested_json = _canonical_json(sorted(str(entry["driver_id"]) for entry in entries))
    registry_version = str(registry.get("_meta", {}).get("version", "unknown"))
    registry_digest = source_registry_hash(registry)

    with repo._conn() as c:
        review = repo.get_review(review_id, conn=c)
        if not review:
            raise ValidationError("Review không tồn tại.")
        if int(review["company_ref_id"]) != int(company_ref_id):
            raise ValidationError("Review không thuộc doanh nghiệp đang phân tích.")
        if review["status"] == "completed":
            raise ValidationError("Review đã finalize; Phase 9 chỉ đọc và không được gọi nguồn mới.")
        fields = {
            "company_ref_id": int(company_ref_id),
            "review_id": int(review_id),
            "trigger_type": "manual_click",
            "status": "running",
            "requested_driver_ids_json": requested_json,
            "source_registry_version": registry_version,
            "source_registry_hash": registry_digest,
            "started_at": started.isoformat(timespec="seconds"),
            "requested_by": actor,
        }
        cur = c.execute(
            f"INSERT INTO topdown_data_update_runs({','.join(fields)}) VALUES({','.join('?' for _ in fields)})",
            tuple(fields.values()),
        )
        run_id = int(cur.lastrowid)
        repo._audit(
            c,
            company_ref_id=company_ref_id,
            review_id=review_id,
            actor=actor,
            action="manual_click_start",
            entity_type="topdown_data_update_run",
            entity_id=run_id,
            after={"requested_drivers": json.loads(requested_json), "registry_hash": registry_digest},
        )

    owned_client = http_client is None
    client = http_client or httpx.Client(
        timeout=httpx.Timeout(12.0, connect=6.0),
        follow_redirects=True,
        headers={"User-Agent": "Trecapital-Phase9/1.0 (+manual latest-on-click)"},
    )
    observations: list[tuple[dict[str, Any], LatestObservation, dict[str, Any]]] = []
    errors: list[dict[str, str]] = []
    keys = _api_keys(api_keys)
    try:
        for entry in entries:
            try:
                observation = fetch_latest_observation(
                    client, entry, registry, api_keys=keys, retrieved_at=started
                )
                observations.append((entry, observation, _suggestion(entry, observation)))
            except SourceFetchError as exc:
                errors.append(
                    {
                        "driver_id": str(entry["driver_id"]),
                        "source_code": str(entry["source_code"]),
                        "series_code": str(entry["series_code"]),
                        "error": str(exc)[:500],
                    }
                )
    finally:
        if owned_client:
            client.close()

    finished = datetime.now(timezone.utc)
    status = "completed" if observations and not errors else "partial" if observations else "failed"
    details = {
        "errors": errors,
        "guardrail": "manual_click_only; no background refresh; no assessment write",
    }
    with repo._conn() as c:
        review = repo.get_review(review_id, conn=c)
        if not review or review["status"] == "completed":
            raise ValidationError("Review đã bị khóa trong khi nguồn đang tải; kết quả Phase 9 không được lưu.")
        for entry, observation, suggestion in observations:
            data = asdict(observation)
            data.update(
                {
                    "run_id": run_id,
                    "company_ref_id": int(company_ref_id),
                    "review_id": int(review_id),
                    "delta_numeric": observation.delta_numeric,
                }
            )
            fields = {
                key: data[key]
                for key in (
                    "run_id", "company_ref_id", "review_id", "driver_id", "source_code",
                    "source_tier", "series_code", "source_url", "period_label",
                    "observation_date", "published_at", "retrieved_at", "frequency",
                    "value_numeric", "previous_value_numeric", "delta_numeric", "unit",
                    "observation_status", "freshness_status", "payload_hash", "raw_locator",
                )
            }
            cur = c.execute(
                f"INSERT INTO topdown_data_observations({','.join(fields)}) VALUES({','.join('?' for _ in fields)})",
                tuple(fields.values()),
            )
            observation_id = int(cur.lastrowid)
            suggestion_fields = {
                "run_id": run_id,
                "observation_id": observation_id,
                "company_ref_id": int(company_ref_id),
                "review_id": int(review_id),
                "driver_id": observation.driver_id,
                "suggested_score": suggestion["suggested_score"],
                "confidence": suggestion["confidence"],
                "rationale": suggestion["rationale"],
                "data_gap_reason": suggestion["data_gap_reason"],
                "method_version": METHOD_VERSION,
                "created_by": actor,
            }
            c.execute(
                f"INSERT INTO topdown_driver_suggestions({','.join(suggestion_fields)}) VALUES({','.join('?' for _ in suggestion_fields)})",
                tuple(suggestion_fields.values()),
            )
        c.execute(
            """UPDATE topdown_data_update_runs
            SET status=?,completed_at=?,success_count=?,failure_count=?,detail_json=? WHERE id=?""",
            (
                status,
                finished.isoformat(timespec="seconds"),
                len(observations),
                len(errors),
                _canonical_json(details),
                run_id,
            ),
        )
        final_row = repo._d(c.execute("SELECT * FROM topdown_data_update_runs WHERE id=?", (run_id,)).fetchone())
        repo._audit(
            c,
            company_ref_id=company_ref_id,
            review_id=review_id,
            actor=actor,
            action="manual_click_complete",
            entity_type="topdown_data_update_run",
            entity_id=run_id,
            after=final_row,
        )
    return run_id


def _decode_run(row: dict[str, Any]) -> dict[str, Any]:
    result = dict(row)
    result["requested_driver_ids"] = json.loads(result.pop("requested_driver_ids_json") or "[]")
    result["detail"] = json.loads(result.pop("detail_json") or "{}")
    return result


def list_update_runs(repo, review_id: int, *, conn=None) -> list[dict[str, Any]]:
    sql = "SELECT * FROM topdown_data_update_runs WHERE review_id=? ORDER BY id DESC"

    def run(c):
        return [_decode_run(dict(row)) for row in c.execute(sql, (review_id,))]

    if conn is not None:
        return run(conn)
    with repo._conn() as c:
        return run(c)


def get_update_run_bundle(repo, run_id: int, *, conn=None) -> dict[str, Any] | None:
    def run(c):
        run_row = c.execute("SELECT * FROM topdown_data_update_runs WHERE id=?", (run_id,)).fetchone()
        if not run_row:
            return None
        observations = [
            dict(row)
            for row in c.execute("SELECT * FROM topdown_data_observations WHERE run_id=? ORDER BY id", (run_id,))
        ]
        suggestions = [
            dict(row)
            for row in c.execute(
                """SELECT s.*,d.id decision_id,d.decision,d.applied_score,d.decision_reason,d.decided_by,d.created_at decision_created_at
                FROM topdown_driver_suggestions s LEFT JOIN topdown_driver_decisions d ON d.suggestion_id=s.id
                WHERE s.run_id=? ORDER BY s.id""",
                (run_id,),
            )
        ]
        return {"run": _decode_run(dict(run_row)), "observations": observations, "suggestions": suggestions}

    if conn is not None:
        return run(conn)
    with repo._conn() as c:
        return run(c)


def list_pending_driver_suggestions(repo, review_id: int) -> list[dict[str, Any]]:
    with repo._conn() as c:
        return [
            dict(row)
            for row in c.execute(
                """SELECT s.*,o.period_label,o.value_numeric,o.previous_value_numeric,o.unit,
                o.source_code,o.series_code,o.freshness_status
                FROM topdown_driver_suggestions s
                JOIN topdown_data_observations o ON o.id=s.observation_id
                LEFT JOIN topdown_driver_decisions d ON d.suggestion_id=s.id
                WHERE s.review_id=? AND d.id IS NULL ORDER BY s.id DESC""",
                (review_id,),
            )
        ]


def decide_driver_suggestion(
    repo,
    *,
    suggestion_id: int,
    decision: str,
    decision_reason: str,
    actor: str = "analyst",
    applied_score: int | None = None,
    analyst_confirmed: bool = False,
) -> int:
    if decision not in {"accept", "reject"}:
        raise ValidationError("Quyết định Phase 9 phải là accept hoặc reject.")
    reason = str(decision_reason or "").strip()
    if not reason:
        raise ValidationError("Lý do accept/reject là bắt buộc.")
    if decision == "accept":
        if not analyst_confirmed:
            raise ValidationError("Analyst phải xác nhận trước khi áp dụng driver suggestion.")
        if applied_score not in {-2, -1, 0, 1, 2}:
            raise ValidationError("Điểm áp dụng phải nằm trong thang -2 đến +2.")
    elif applied_score is not None:
        raise ValidationError("Reject không được gán điểm áp dụng.")
    with repo._conn() as c:
        suggestion = repo._d(
            c.execute("SELECT * FROM topdown_driver_suggestions WHERE id=?", (suggestion_id,)).fetchone()
        )
        if not suggestion:
            raise ValidationError("Driver suggestion không tồn tại.")
        review = repo.get_review(suggestion["review_id"], conn=c)
        if not review or review["status"] == "completed":
            raise ValidationError("Review đã finalize; Phase 9 chỉ đọc.")
        duplicate = c.execute(
            "SELECT id FROM topdown_driver_decisions WHERE suggestion_id=?", (suggestion_id,)
        ).fetchone()
        if duplicate:
            raise ValidationError("Suggestion này đã được quyết định.")
        fields = {
            "suggestion_id": int(suggestion_id),
            "company_ref_id": int(suggestion["company_ref_id"]),
            "review_id": int(suggestion["review_id"]),
            "decision": decision,
            "applied_score": applied_score if decision == "accept" else None,
            "decision_reason": reason,
            "analyst_confirmed": 1 if decision == "accept" else 0,
            "decided_by": str(actor or "analyst").strip(),
        }
        cur = c.execute(
            f"INSERT INTO topdown_driver_decisions({','.join(fields)}) VALUES({','.join('?' for _ in fields)})",
            tuple(fields.values()),
        )
        decision_id = int(cur.lastrowid)
        repo._audit(
            c,
            company_ref_id=suggestion["company_ref_id"],
            review_id=suggestion["review_id"],
            actor=fields["decided_by"],
            action=decision,
            entity_type="topdown_driver_suggestion",
            entity_id=suggestion_id,
            before=suggestion,
            after=fields,
        )
        return decision_id


def latest_accepted_driver_outlook(repo, review_id: int, *, conn=None) -> dict[str, int]:
    sql = """SELECT s.driver_id,d.applied_score,d.id
    FROM topdown_driver_decisions d JOIN topdown_driver_suggestions s ON s.id=d.suggestion_id
    WHERE d.review_id=? AND d.decision='accept' ORDER BY d.id DESC"""

    def run(c):
        result: dict[str, int] = {}
        for row in c.execute(sql, (review_id,)):
            result.setdefault(str(row["driver_id"]), int(row["applied_score"]))
        return result

    if conn is not None:
        return run(conn)
    with repo._conn() as c:
        return run(c)


def snapshot_phase9_for_review(repo, review_id: int, *, conn=None) -> dict[str, Any]:
    def run(c):
        runs = list_update_runs(repo, review_id, conn=c)
        accepted = latest_accepted_driver_outlook(repo, review_id, conn=c)
        decisions = [
            dict(row)
            for row in c.execute(
                """SELECT d.*,s.driver_id,s.suggested_score,s.method_version,o.period_label,
                o.value_numeric,o.unit,o.source_code,o.series_code,o.payload_hash
                FROM topdown_driver_decisions d
                JOIN topdown_driver_suggestions s ON s.id=d.suggestion_id
                JOIN topdown_data_observations o ON o.id=s.observation_id
                WHERE d.review_id=? ORDER BY d.id""",
                (review_id,),
            )
        ]
        return {
            "schema": "governed-topdown-latest-data-v1",
            "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "latest_accepted_driver_outlook": accepted,
            "update_runs": runs,
            "decisions": decisions,
        }

    if conn is not None:
        return run(conn)
    with repo._conn() as c:
        return run(c)


__all__ = [
    "LatestObservation",
    "METHOD_VERSION",
    "SourceFetchError",
    "automatic_driver_ids",
    "decide_driver_suggestion",
    "fetch_latest_observation",
    "get_update_run_bundle",
    "latest_accepted_driver_outlook",
    "list_pending_driver_suggestions",
    "list_update_runs",
    "load_source_registry",
    "run_latest_data_update",
    "snapshot_phase9_for_review",
    "source_coverage_rows",
    "source_registry_hash",
]
