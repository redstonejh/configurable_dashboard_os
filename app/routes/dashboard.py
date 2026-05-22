from collections import Counter
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import json
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from app.scanner import DEFAULT_LOOKBACK_DAYS, run_sync, run_sync_range
from app.storage import (
    dashboard_stats,
    get_config,
    get_state,
    list_current_notification_cases,
    list_events,
    list_records,
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

RANGE_PRESETS = [
    {"days": 1, "label": "Today", "short": "Today"},
    {"days": 7, "label": "Last 7 days", "short": "7d"},
    {"days": 30, "label": "Last 30 days", "short": "30d"},
    {"days": 60, "label": "Last 60 days", "short": "60d"},
    {"days": 90, "label": "Last 90 days", "short": "90d"},
    {"days": 180, "label": "Last 6 months", "short": "6mo"},
    {"days": 365, "label": "Last year", "short": "1yr"},
]

METRIC_LABELS = {
    "": "Records",
    "total": "Records",
    "critical": "Critical records",
    "repeated": "Repeated categories",
    "review": "Needs review",
    "notified": "Notifications",
}


def _decode_reasons(value: object) -> list[str]:
    if not value:
        return []
    try:
        loaded = json.loads(str(value))
    except json.JSONDecodeError:
        return [str(value)]
    if isinstance(loaded, list):
        return [str(item) for item in loaded]
    return [str(loaded)]


def _search_matches(query: str, values: list[object]) -> bool:
    terms = [term for term in re.split(r"\s+", query.strip().lower()) if term]
    if not terms:
        return True
    haystack = " ".join(str(value or "") for value in values).lower()
    return all(term in haystack for term in terms)


def _format_date_short(value: str) -> str:
    try:
        dt = datetime.strptime(value, "%Y-%m-%d")
        return f"{dt:%b} {dt.day}, {dt.year}"
    except (ValueError, TypeError):
        return value or ""


def _format_date_compact(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%m/%d/%y")
    except (ValueError, TypeError):
        return value or ""


def _range_display(start: str, end: str) -> str:
    return f"{_format_date_compact(start)} - {_format_date_compact(end)}"


def _local_fallback(utc: datetime) -> datetime:
    year = utc.year

    def nth_sunday(y: int, month: int, n: int) -> datetime:
        first = datetime(y, month, 1, tzinfo=timezone.utc)
        days_to_sunday = (6 - first.weekday()) % 7
        return first + timedelta(days=days_to_sunday + 7 * (n - 1))

    dst_start = nth_sunday(year, 3, 2) + timedelta(hours=10)
    dst_end = nth_sunday(year, 11, 1) + timedelta(hours=9)
    offset = timedelta(hours=-7 if dst_start <= utc < dst_end else -8)
    return utc + offset


def _format_datetime(value: object) -> str:
    if not value:
        return ""
    text = str(value)
    try:
        utc = datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return text
    try:
        local = utc.astimezone(ZoneInfo("America/Los_Angeles"))
    except ZoneInfoNotFoundError:
        local = _local_fallback(utc)
    hour = local.hour % 12 or 12
    return f"{local:%m/%d/%y} {hour}:{local:%M %p}"


def _today_utc() -> datetime:
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def _range_start(days: int) -> str:
    today = _today_utc()
    if days <= 1:
        return today.date().isoformat()
    return (today - timedelta(days=days - 1)).date().isoformat()


def _safe_range_days(value: str) -> int:
    try:
        days = int(value)
    except (TypeError, ValueError):
        return DEFAULT_LOOKBACK_DAYS
    allowed = {preset["days"] for preset in RANGE_PRESETS}
    return days if days in allowed else DEFAULT_LOOKBACK_DAYS


def _custom_range(start_value: str, end_value: str) -> tuple[str, str] | None:
    if not start_value or not end_value:
        return None
    try:
        start = datetime.strptime(start_value, "%Y-%m-%d").date()
        end = datetime.strptime(end_value, "%Y-%m-%d").date()
    except ValueError:
        return None
    if start > end:
        start, end = end, start
    return start.isoformat(), end.isoformat()


def _safe_metric(value: str) -> str:
    return value if value in METRIC_LABELS else ""


def _ensure_sync_coverage(days: int) -> tuple[bool, int]:
    desired_start = _range_start(days)
    today = _today_utc().date().isoformat()
    coverage_start = get_state("sync_coverage_start")
    coverage_end = get_state("sync_coverage_end")
    processed = 0
    synced = False

    if not coverage_start:
        result = run_sync_range(desired_start, today)
        return True, result.get("processed", 0)

    if desired_start < coverage_start:
        previous_day = (
            datetime.strptime(coverage_start, "%Y-%m-%d") - timedelta(days=1)
        ).date().isoformat()
        result = run_sync_range(desired_start, previous_day)
        processed += result.get("processed", 0)
        synced = True

    if not coverage_end or coverage_end < today:
        result = run_sync()
        processed += result.get("processed", 0)
        synced = True

    return synced, processed


def _chart_percent(value: int, total: int) -> int:
    if total <= 0 or value <= 0:
        return 0
    return max(1, min(100, round((value / total) * 100)))


def _received_local_date(row: dict):
    value = row.get("received_time")
    if not value:
        return None
    try:
        received = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if received.tzinfo is None:
        received = received.replace(tzinfo=timezone.utc)
    utc = received.astimezone(timezone.utc)
    try:
        return utc.astimezone(ZoneInfo("America/Los_Angeles")).date()
    except ZoneInfoNotFoundError:
        return _local_fallback(utc).date()


def _top_visual_rows(counter: Counter, total: int, limit: int = 4) -> list[dict]:
    max_count = max(counter.values(), default=0)
    rows: list[dict] = []
    for label, count in counter.most_common(limit):
        rows.append(
            {
                "label": label,
                "count": count,
                "pct": _chart_percent(count, max_count),
                "share": _chart_percent(count, total),
            }
        )
    return rows


def _trend_visual_rows(records: list[dict], start: str, end: str) -> list[dict]:
    try:
        start_date = datetime.strptime(start, "%Y-%m-%d").date()
        end_date = datetime.strptime(end, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return []
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    span_days = max(1, (end_date - start_date).days + 1)
    bucket_count = min(12, span_days)
    buckets: list[dict] = []
    for idx in range(bucket_count):
        bucket_start = start_date + timedelta(days=(idx * span_days) // bucket_count)
        bucket_end = start_date + timedelta(days=(((idx + 1) * span_days) // bucket_count) - 1)
        label = (
            f"{bucket_start:%m/%d}"
            if bucket_start == bucket_end
            else f"{bucket_start:%m/%d}-{bucket_end:%m/%d}"
        )
        buckets.append({"label": label, "count": 0})
    for row in records:
        local_date = _received_local_date(row)
        if local_date is None or local_date < start_date or local_date > end_date:
            continue
        offset = (local_date - start_date).days
        bucket_index = min(bucket_count - 1, (offset * bucket_count) // span_days)
        buckets[bucket_index]["count"] += 1
    max_count = max((bucket["count"] for bucket in buckets), default=0)
    for bucket in buckets:
        count = int(bucket["count"])
        bucket["height"] = 0 if count == 0 else max(8, _chart_percent(count, max_count))
    return buckets


def _dashboard_visuals(records: list[dict], start: str, end: str) -> dict:
    total = len(records)
    label_counts: Counter = Counter()
    category_counts: Counter = Counter()
    source_counts: Counter = Counter()
    for row in records:
        label_counts[str(row.get("score_label") or "Unknown").strip().lower()] += 1
        category_counts[str(row.get("category") or "Unknown").strip() or "Unknown"] += 1
        source_counts[str(row.get("source") or "Unknown").strip() or "Unknown"] += 1

    label_rows = []
    for key, label in (
        ("critical", "Critical"),
        ("high", "High"),
        ("medium", "Medium"),
        ("low", "Low"),
        ("unknown", "Unknown"),
    ):
        count = label_counts.get(key, 0)
        label_rows.append(
            {
                "key": key,
                "label": label,
                "count": count,
                "pct": _chart_percent(count, total),
            }
        )
    return {
        "total": total,
        "labels": label_rows,
        "trend": _trend_visual_rows(records, start, end),
        "categories": _top_visual_rows(category_counts, total),
        "sources": _top_visual_rows(source_counts, total),
    }


def _notification_title(row: dict) -> str:
    label = str(row.get("score_label") or "Record").strip().title()
    title = str(row.get("title") or "Untitled record").strip()
    source = str(row.get("source") or "").strip()
    return f"{label}: {source} - {title}" if source else f"{label}: {title}"


def _decorate_record(record: dict) -> dict:
    record["received_display"] = _format_datetime(record.get("received_time"))
    record["source_display"] = str(record.get("source") or "").strip()
    record["owner_display"] = str(record.get("owner") or "Unassigned").strip()
    record["resource_display"] = str(record.get("resource") or "").strip()
    record["category_display"] = str(record.get("category") or "").strip()
    record["status_display"] = str(record.get("status") or "").strip()
    record["score_reasons_list"] = _decode_reasons(record.get("score_reasons"))
    return record


@router.get("/")
@router.get("/dashboard")
def dashboard(request: Request):
    config = asdict(get_config(include_secrets=False))
    active_days = _safe_range_days(request.query_params.get("range", str(DEFAULT_LOOKBACK_DAYS)))
    active_metric = _safe_metric(request.query_params.get("metric", ""))
    search_query = request.query_params.get("q", "").strip()
    custom_range = _custom_range(request.query_params.get("start", ""), request.query_params.get("end", ""))
    if custom_range:
        view_start, view_end = custom_range
        active_label = f"{view_start} to {view_end}"
        range_query = f"start={view_start}&end={view_end}"
        coverage_days = max(1, (_today_utc().date() - datetime.strptime(view_start, "%Y-%m-%d").date()).days + 1)
    else:
        view_start = _range_start(active_days)
        view_end = _today_utc().date().isoformat()
        active_label = next(
            preset["label"] for preset in RANGE_PRESETS if preset["days"] == active_days
        )
        range_query = f"range={active_days}"
        coverage_days = active_days

    auto_synced = False
    auto_processed = 0
    auto_sync_failed = False
    if config.get("source_poll_enabled"):
        try:
            auto_synced, auto_processed = _ensure_sync_coverage(coverage_days)
        except Exception:
            auto_sync_failed = True

    stats = dashboard_stats(start=view_start, end=view_end)
    stats["last_sync_display"] = _format_datetime(stats.get("last_sync_time"))
    stats["sync_range_display"] = active_label
    stats["coverage_start_display"] = _format_date_short(get_state("sync_coverage_start"))
    stats["coverage_end_display"] = _format_date_short(get_state("sync_coverage_end"))
    stats["poll_interval_seconds"] = config.get("source_poll_interval_seconds") or 60

    if active_metric == "notified":
        recent_records = list_current_notification_cases(500, start=view_start, end=view_end)
    else:
        recent_records = list_records(500, start=view_start, end=view_end, metric=active_metric)
    filtered_records = []
    for record in recent_records:
        _decorate_record(record)
        if search_query and not _search_matches(
            search_query,
            [
                record.get("received_display"),
                record.get("source_display"),
                record.get("owner_display"),
                record.get("resource_display"),
                record.get("category_display"),
                record.get("status_display"),
                record.get("score_label"),
                record.get("title"),
                record.get("summary"),
                record.get("details"),
                record.get("raw_payload"),
            ],
        ):
            continue
        filtered_records.append(record)
    recent_records = filtered_records
    visualizations = _dashboard_visuals(recent_records, view_start, view_end)
    notifications = list_current_notification_cases(50, start=view_start, end=view_end)
    for message in notifications:
        message["created_display"] = _format_datetime(message.get("created_at"))
        message["reason_label"] = _notification_title(message)
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "config": config,
            "stats": stats,
            "recent_records": recent_records,
            "visualizations": visualizations,
            "notification_events": list_events("notification", 15),
            "ordinary_events": list_events("ordinary", 15),
            "suppressed_events": list_events("suppressed", 15),
            "notifications": notifications,
            "view_start": view_start,
            "view_end": view_end,
            "active_days": active_days,
            "active_metric": active_metric,
            "search_query": search_query,
            "custom_range": bool(custom_range),
            "range_query": range_query,
            "range_display": _range_display(view_start, view_end),
            "metric_label": METRIC_LABELS[active_metric],
            "range_presets": RANGE_PRESETS,
            "auto_synced": auto_synced,
            "auto_processed": auto_processed,
            "auto_sync_failed": auto_sync_failed,
        },
    )
