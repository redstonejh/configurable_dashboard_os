import asyncio
import logging

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.database import init_db
from app.logger import setup_logging
from app.scanner import DEFAULT_POLL_INTERVAL_SECONDS, backfill_scores, run_sync
from app.storage import get_config
from app.routes import actions, api, dashboard, records, settings

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="app/templates")


def create_app() -> FastAPI:
    setup_logging()
    init_db()

    app = FastAPI(title="Configurable Dashboard Skeleton")
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    app.include_router(dashboard.router)
    app.include_router(settings.router)
    app.include_router(api.router)
    app.include_router(records.router)
    app.include_router(actions.router)

    @app.on_event("startup")
    async def start_background_sync() -> None:
        await asyncio.to_thread(backfill_scores, True)
        config = get_config()
        interval = config.source_poll_interval_seconds or DEFAULT_POLL_INTERVAL_SECONDS
        if config.source_poll_enabled and interval > 0:
            asyncio.create_task(_sync_forever(interval))

    @app.exception_handler(Exception)
    async def handle_exception(request: Request, exc: Exception) -> HTMLResponse:
        logger.exception("Unhandled request error")
        return templates.TemplateResponse(
            "base.html",
            {"request": request, "error": str(exc), "content_template": None},
            status_code=500,
        )

    return app


async def _sync_forever(interval: int) -> None:
    while True:
        await asyncio.sleep(interval)
        try:
            await asyncio.to_thread(run_sync)
        except Exception:
            logger.exception("Scheduled source sync failed")


app = create_app()
