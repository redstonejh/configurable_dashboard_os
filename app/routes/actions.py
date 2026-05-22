from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import RedirectResponse

from app.models import Record
from app.notifier import Notifier
from app.scanner import backfill_scores, run_sync, run_sync_range
from app.source_connector import SourceConnector
from app.storage import add_notification, clear_data, get_config, update_state

router = APIRouter(prefix="/actions")


def _ok(message: str, detail: object | None = None) -> dict:
    return {"ok": True, "message": message, "detail": detail}


@router.post("/test-source")
def test_source():
    try:
        connector = SourceConnector(get_config().source_name)
        connector.test_connection()
        return _ok("Source connector test succeeded.")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/test-notification")
def test_notification():
    try:
        config = get_config()
        message = "Generic dashboard notification preview."
        if config.notification_preview_mode or not config.notification_hook_url:
            add_notification(None, "preview", "test_notification", message)
            return _ok("Notification preview logged locally.")
        result = Notifier(config.notification_hook_url).send_text(message)
        add_notification(None, result.status, "test_notification", message, result.response_text)
        return _ok("Notification hook completed.", {"status": result.status})
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/test-record")
def test_record():
    try:
        config = get_config()
        record = Record(
            external_id="local-test-record",
            received_time=datetime.now(timezone.utc),
            title="Local test record",
            source="Local",
            category="Test",
            status="Priority",
            owner="Example owner",
            resource="Example resource",
            summary="Generated local notification preview.",
            details="Use this as a placeholder when wiring a project-specific source.",
            score=100,
            score_label="Critical",
        )
        message = Notifier(config.notification_hook_url).format_record(record, "score_threshold", 1)
        if config.notification_preview_mode or not config.notification_hook_url:
            add_notification(None, "preview", "record_test", message)
            return _ok("Record notification preview logged locally.")
        result = Notifier(config.notification_hook_url).send_text(message)
        add_notification(None, result.status, "record_test", message, result.response_text)
        return _ok("Record notification hook completed.", {"status": result.status})
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/run-parser")
def run_parser_now():
    try:
        return _ok("Parser run completed.", run_sync())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sync-source")
def sync_source():
    try:
        result = run_sync()
        return RedirectResponse(
            f"/dashboard?synced={result.get('processed', 0)}&view_all=1",
            status_code=303,
        )
    except Exception as exc:
        return RedirectResponse(f"/dashboard?sync_failed=1&err={quote(str(exc))}&view_all=1", status_code=303)


@router.post("/sync-range")
def sync_range(start_date: str = Form(...), end_date: str = Form(""), range_label: str = Form("")):
    try:
        result = run_sync_range(start_date, end_date or None)
        view_end = (end_date or start_date)[:10]
        update_state("last_sync_range_start", start_date[:10])
        update_state("last_sync_range_end", view_end)
        update_state("last_sync_range_label", range_label)
        return RedirectResponse(
            f"/dashboard?synced={result.get('processed', 0)}"
            f"&view_start={start_date[:10]}&view_end={view_end}&view_label={quote(range_label)}",
            status_code=303,
        )
    except Exception as exc:
        return RedirectResponse(f"/dashboard?sync_failed=1&err={quote(str(exc))}", status_code=303)


@router.post("/rescore")
def rescore_all():
    updated = backfill_scores(force=True)
    return RedirectResponse(f"/dashboard?rescored={updated}", status_code=303)


@router.post("/clear-data")
def clear_data_action():
    try:
        clear_data()
        return RedirectResponse("/dashboard?cleared=1", status_code=303)
    except Exception as exc:
        return RedirectResponse(f"/dashboard?sync_failed=1&err={quote(str(exc))}", status_code=303)
