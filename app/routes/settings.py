from dataclasses import asdict

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.models import DEFAULT_SCORE_RULES
from app.routes.dashboard import _format_datetime
from app.scanner import backfill_scores
from app.security import mask_secret
from app.storage import delete_setting, get_config, get_state, save_config

router = APIRouter(prefix="/settings")
templates = Jinja2Templates(directory="app/templates")


@router.get("")
def settings_page(request: Request):
    config = get_config()
    display = asdict(config)
    display["notification_hook_url_masked"] = mask_secret(config.notification_hook_url)
    display["notification_hook_url"] = ""
    display["last_sync_display"] = _format_datetime(get_state("last_sync_time"))
    return templates.TemplateResponse("settings.html", {"request": request, "config": display})


@router.post("")
def save_settings(
    app_name: str = Form("Configurable Dashboard Skeleton"),
    source_name: str = Form("Source"),
    source_description: str = Form(""),
    source_poll_enabled: bool = Form(False),
    source_poll_interval_seconds: int = Form(60),
    lookback_days: int = Form(60),
    parser_required_fields: str = Form("title,source,category,status"),
    notification_hook_url: str = Form(""),
    notification_preview_mode: bool = Form(False),
    notification_cooldown_hours: int = Form(24),
    notification_min_score: int = Form(85),
    default_score: int = Form(35),
    score_rules: str = Form(""),
    rule_preset: str = Form("generic"),
    score_critical_threshold: int = Form(85),
    score_high_threshold: int = Form(65),
    score_medium_threshold: int = Form(40),
    repeat_window_hours: int = Form(24),
    repeat_1_adjustment: int = Form(8),
    repeat_2_adjustment: int = Form(14),
    repeat_3_adjustment: int = Form(20),
    source_volume_window_hours: int = Form(24),
    source_volume_threshold: int = Form(8),
    source_volume_adjustment: int = Form(10),
):
    save_config(
        {
            "app_name": app_name,
            "source_name": source_name,
            "source_description": source_description,
            "source_poll_enabled": source_poll_enabled,
            "source_poll_interval_seconds": source_poll_interval_seconds,
            "lookback_days": lookback_days,
            "start_date": "",
            "parser_required_fields": parser_required_fields,
            "notification_hook_url": notification_hook_url,
            "notification_preview_mode": notification_preview_mode,
            "notification_cooldown_hours": notification_cooldown_hours,
            "notification_min_score": notification_min_score,
            "default_score": default_score,
            "score_rules": score_rules.strip() or DEFAULT_SCORE_RULES,
            "rule_preset": rule_preset,
            "score_critical_threshold": score_critical_threshold,
            "score_high_threshold": score_high_threshold,
            "score_medium_threshold": score_medium_threshold,
            "repeat_window_hours": repeat_window_hours,
            "repeat_1_adjustment": repeat_1_adjustment,
            "repeat_2_adjustment": repeat_2_adjustment,
            "repeat_3_adjustment": repeat_3_adjustment,
            "source_volume_window_hours": source_volume_window_hours,
            "source_volume_threshold": source_volume_threshold,
            "source_volume_adjustment": source_volume_adjustment,
        }
    )
    rescored = backfill_scores(force=True)
    return RedirectResponse(f"/settings?saved=1&rescored={rescored}", status_code=303)


@router.post("/disconnect")
def disconnect_settings():
    for key in (
        "source_name",
        "source_description",
        "source_poll_enabled",
        "notification_hook_url",
    ):
        delete_setting(key)
    return RedirectResponse("/settings?disconnected=1", status_code=303)


@router.post("/quick")
def save_quick_settings(
    app_name: str = Form("Configurable Dashboard Skeleton"),
    source_name: str = Form("Source"),
    source_description: str = Form(""),
    source_poll_enabled: bool = Form(False),
    lookback_days: int = Form(60),
    notification_preview_mode: bool = Form(True),
):
    save_config(locals())
    return RedirectResponse("/dashboard?saved=1", status_code=303)
