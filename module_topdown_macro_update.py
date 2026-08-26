"""Standalone latest-on-click macro update for Fisher Top-Down.

The source adapters are shared with the existing governed data layer, but this workflow is not tied
to a company, a Checklist review, Q01--Q59, or an analyst-acceptance table. A fetch returns
observations and rule-based score suggestions. The Fisher page may use valid suggestions as its
automatic baseline; a score explicitly changed by the analyst always has priority.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import os
from typing import Any, Iterable

import httpx

from modules.investment_checklist.services.topdown_data_update import (
    SourceFetchError,
    _suggestion,
    automatic_driver_ids,
    fetch_latest_observation,
    load_source_registry,
    source_registry_hash,
)


METHOD_VERSION = "fisher-topdown-latest-on-click-v2"
VALID_DRIVER_SCORES = {-2.0, -1.0, 0.0, 1.0, 2.0}

# IMF DataMapper intermittently returns HTTP 403 from Streamlit Cloud.  These official WDI series
# preserve a usable Vietnam macro proxy without pretending that the source/method is identical.
WORLD_BANK_FALLBACKS = {
    "gdp_growth": ("NY.GDP.MKTP.KD.ZG", "% tăng trưởng GDP thực"),
    "inflation": ("FP.CPI.TOTL.ZG", "% CPI"),
    "employment": ("SL.UEM.TOTL.ZS", "% lực lượng lao động thất nghiệp"),
    "gov_spending": ("NE.CON.GOVT.ZS", "% GDP"),
}


def _api_keys(values: dict[str, str] | None) -> dict[str, str]:
    if values is not None:
        return {str(key): str(value) for key, value in values.items()}
    return {key: os.getenv(key, "") for key in ("FRED_API_KEY", "EIA_API_KEY")}


def available_macro_drivers(registry: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    registry = registry or load_source_registry()
    return [
        {
            "driver_id": str(entry["driver_id"]),
            "driver_name": str(entry["driver_name"]),
            "source": str(registry["sources"][entry["source_code"]]["publisher"]),
            "mode": str(entry["mode"]),
            "note": str(entry.get("note", "")),
        }
        for entry in registry["driver_sources"]
        if entry.get("adapter")
    ]


def resolve_effective_driver_scores(
    current_scores: dict[str, float],
    score_sources: dict[str, str],
    suggestions: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Apply valid automatic suggestions while preserving every analyst override."""
    effective_scores = {str(key): float(value) for key, value in current_scores.items()}
    effective_sources = {str(key): str(value) for key, value in score_sources.items()}
    automatic_scores: dict[str, float] = {}
    applied_driver_ids: list[str] = []
    analyst_override_ids: list[str] = []
    research_gap_ids: list[str] = []

    for row in suggestions:
        driver_id = str(row.get("driver_id", "")).strip()
        if not driver_id:
            continue
        raw_score = row.get("suggested_score")
        if raw_score is None:
            research_gap_ids.append(driver_id)
            continue
        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            research_gap_ids.append(driver_id)
            continue
        if score not in VALID_DRIVER_SCORES:
            research_gap_ids.append(driver_id)
            continue

        automatic_scores[driver_id] = score
        if effective_sources.get(driver_id) == "analyst_override":
            analyst_override_ids.append(driver_id)
            continue
        effective_scores[driver_id] = score
        effective_sources[driver_id] = "automatic_suggestion"
        applied_driver_ids.append(driver_id)

    return {
        "effective_scores": effective_scores,
        "score_sources": effective_sources,
        "automatic_scores": automatic_scores,
        "applied_driver_ids": applied_driver_ids,
        "analyst_override_ids": analyst_override_ids,
        "research_gap_ids": research_gap_ids,
    }


def _world_bank_fallback_entry(entry: dict[str, Any]) -> dict[str, Any] | None:
    fallback = WORLD_BANK_FALLBACKS.get(str(entry.get("driver_id", "")))
    if not fallback:
        return None
    series_code, unit = fallback
    copied = dict(entry)
    copied.update(
        {
            "source_code": "world_bank_wdi",
            "adapter": "world_bank",
            "series_code": series_code,
            "unit": unit,
            "frequency": "annual",
            "note": (
                f"Official World Bank fallback for {entry.get('driver_name')}; "
                "analyst must interpret it as a proxy, not an IMF-equivalent series."
            ),
        }
    )
    return copied


def run_macro_update(
    driver_ids: Iterable[str] | None = None,
    *,
    http_client: httpx.Client | None = None,
    api_keys: dict[str, str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Fetch current macro observations exactly when called by the explicit Fisher-page button."""
    registry = load_source_registry()
    requested = set(driver_ids or automatic_driver_ids(registry))
    valid_ids = {str(entry["driver_id"]) for entry in registry["driver_sources"]}
    unknown = requested - valid_ids
    if unknown:
        raise ValueError(f"Driver không tồn tại: {', '.join(sorted(unknown))}.")
    entries = [
        entry
        for entry in registry["driver_sources"]
        if entry.get("adapter") and str(entry["driver_id"]) in requested
    ]
    if not entries:
        raise ValueError("Chưa chọn driver nào có nguồn tự động.")

    retrieved_at = now or datetime.now(timezone.utc)
    if retrieved_at.tzinfo is None:
        retrieved_at = retrieved_at.replace(tzinfo=timezone.utc)
    owned_client = http_client is None
    client = http_client or httpx.Client(
        timeout=httpx.Timeout(12.0, connect=6.0),
        follow_redirects=True,
        headers={"User-Agent": "Trecapital-Fisher-TopDown/1.0 (+manual latest-on-click)"},
    )
    keys = _api_keys(api_keys)
    observations: list[dict[str, Any]] = []
    suggestions: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    try:
        for entry in entries:
            used_entry = entry
            fallback_from = None
            try:
                observation = fetch_latest_observation(
                    client, used_entry, registry, api_keys=keys, retrieved_at=retrieved_at
                )
            except SourceFetchError as primary_error:
                fallback_entry = (
                    _world_bank_fallback_entry(entry)
                    if str(entry.get("adapter")) == "imf_datamapper"
                    else None
                )
                if fallback_entry is None:
                    errors.append(
                        {
                            "driver_id": str(entry["driver_id"]),
                            "driver_name": str(entry["driver_name"]),
                            "source_code": str(entry["source_code"]),
                            "series_code": str(entry["series_code"]),
                            "error": str(primary_error)[:500],
                        }
                    )
                    continue
                try:
                    used_entry = fallback_entry
                    fallback_from = f"{entry['source_code']}:{entry['series_code']}"
                    observation = fetch_latest_observation(
                        client, used_entry, registry, api_keys=keys, retrieved_at=retrieved_at
                    )
                except SourceFetchError as fallback_error:
                    errors.append(
                        {
                            "driver_id": str(entry["driver_id"]),
                            "driver_name": str(entry["driver_name"]),
                            "source_code": str(entry["source_code"]),
                            "series_code": str(entry["series_code"]),
                            "error": (
                                f"Nguồn chính: {primary_error}; World Bank fallback: {fallback_error}"
                            )[:500],
                        }
                    )
                    continue

            observation_row = asdict(observation)
            observation_row["delta_numeric"] = observation.delta_numeric
            observation_row["driver_name"] = str(entry["driver_name"])
            observation_row["fallback_from"] = fallback_from
            suggestion = _suggestion(used_entry, observation)
            suggestion.update(
                {
                    "driver_id": str(entry["driver_id"]),
                    "driver_name": str(entry["driver_name"]),
                }
            )
            observations.append(observation_row)
            suggestions.append(suggestion)
    finally:
        if owned_client:
            client.close()

    status = "completed" if observations and not errors else "partial" if observations else "failed"
    return {
        "schema": "fisher-topdown-macro-update-v1",
        "method_version": METHOD_VERSION,
        "trigger_type": "manual_click",
        "status": status,
        "retrieved_at": retrieved_at.isoformat(timespec="seconds"),
        "source_registry_hash": source_registry_hash(registry),
        "requested_driver_ids": [str(entry["driver_id"]) for entry in entries],
        "success_count": len(observations),
        "failure_count": len(errors),
        "observations": observations,
        "suggestions": suggestions,
        "errors": errors,
        "guardrail": (
            "manual_click_only; no polling; valid suggestions may become automatic driver baselines; "
            "analyst override wins; no company/checklist write"
        ),
    }


__all__ = [
    "METHOD_VERSION",
    "WORLD_BANK_FALLBACKS",
    "available_macro_drivers",
    "resolve_effective_driver_scores",
    "run_macro_update",
]
