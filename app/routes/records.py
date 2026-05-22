from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.storage import get_record, historical_matches, notification_for_record

router = APIRouter(prefix="/records")
templates = Jinja2Templates(directory="app/templates")


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


@router.get("")
def records(request: Request):
    return RedirectResponse("/dashboard", status_code=303)


@router.get("/{record_id}")
def record_detail(request: Request, record_id: int):
    record = get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    record["received_display"] = _format_datetime(record.get("received_time"))
    record["source_display"] = record.get("source") or "Unknown source"
    record["resource_display"] = record.get("resource") or "Unspecified resource"
    record["owner_display"] = record.get("owner") or "Unassigned"
    matches = historical_matches(record.get("category", ""), record.get("resource", ""), record_id)
    for match in matches:
        match["received_display"] = _format_datetime(match.get("received_time"))
    return templates.TemplateResponse(
        "record_detail.html",
        {
            "request": request,
            "record": record,
            "notification": notification_for_record(record_id),
            "matches": matches,
        },
    )
