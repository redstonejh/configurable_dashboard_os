from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.models import Record
from app.parser import parse_record_payload
from app.routes.dashboard import (
    METRIC_LABELS,
    RANGE_PRESETS,
    _format_datetime,
    _range_start,
    _safe_metric,
    _safe_range_days,
    _today_utc,
)
from app.rule_engine import scoring_breakdown
from app.storage import (
    dashboard_stats,
    get_config,
    get_record,
    historical_matches,
    list_current_notification_cases,
    list_records,
    notification_for_record,
)

router = APIRouter(prefix="/api")

PREVIEW_CONFIG_FIELDS = {
    "default_score",
    "score_critical_threshold",
    "score_high_threshold",
    "score_medium_threshold",
    "repeat_window_hours",
    "repeat_1_adjustment",
    "repeat_2_adjustment",
    "repeat_3_adjustment",
    "source_volume_window_hours",
    "source_volume_threshold",
    "source_volume_adjustment",
    "notification_min_score",
    "score_rules",
}


def _public_record(row: dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    item["received_display"] = _format_datetime(item.get("received_time"))
    return item


@router.get("/dashboard")
def dashboard_data(request: Request) -> dict[str, Any]:
    active_days = _safe_range_days(request.query_params.get("range", "60"))
    active_metric = _safe_metric(request.query_params.get("metric", ""))
    view_start = _range_start(active_days)
    view_end = _today_utc().date().isoformat()
    stats = dashboard_stats(start=view_start, end=view_end)

    if active_metric == "notified":
        recent = list_current_notification_cases(500, start=view_start, end=view_end)
    else:
        recent = list_records(500, start=view_start, end=view_end, metric=active_metric)

    return {
        "config": asdict(get_config(include_secrets=False)),
        "stats": stats,
        "records": [_public_record(record) for record in recent],
        "notifications": [
            _public_record(message)
            for message in list_current_notification_cases(50, start=view_start, end=view_end)
        ],
        "range": {
            "active_days": active_days,
            "active_metric": active_metric,
            "metric_label": METRIC_LABELS[active_metric],
            "view_start": view_start,
            "view_end": view_end,
            "presets": RANGE_PRESETS,
        },
    }


@router.get("/records/{record_id}")
def record_data(record_id: int) -> dict[str, Any]:
    record = get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return {
        "record": _public_record(record),
        "notification": notification_for_record(record_id),
        "matches": [
            _public_record(row)
            for row in historical_matches(
                record.get("category", ""),
                record.get("resource", ""),
                record_id,
            )
        ],
    }


@router.get("/settings")
def settings_data() -> dict[str, Any]:
    config = asdict(get_config(include_secrets=False))
    return {"config": config}


@router.post("/rule-preview")
async def rule_preview(request: Request) -> dict[str, Any]:
    payload = await request.json()
    config = get_config()
    preview_config = payload.get("config") or {}
    for key, value in preview_config.items():
        if key not in PREVIEW_CONFIG_FIELDS or not hasattr(config, key):
            continue
        current = getattr(config, key)
        if isinstance(current, bool):
            setattr(config, key, str(value).lower() in {"1", "true", "yes", "on"})
        elif isinstance(current, int):
            try:
                setattr(config, key, int(value))
            except (TypeError, ValueError):
                pass
        else:
            setattr(config, key, str(value))

    record = parse_record_payload(
        {
            "id": "preview",
            "received_time": payload.get("received_time") or datetime.now(timezone.utc).isoformat(),
            "title": payload.get("title") or "",
            "source": payload.get("source") or "",
            "category": payload.get("category") or "",
            "status": payload.get("status") or "",
            "owner": payload.get("owner") or "",
            "resource": payload.get("resource") or "",
            "summary": payload.get("summary") or "",
            "details": payload.get("details") or "",
        }
    )
    return scoring_breakdown(record, config)
