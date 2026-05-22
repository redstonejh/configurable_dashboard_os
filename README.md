# Configurable Dashboard OS

Work in progress. This project is being refactored out of a previous project-specific dashboard into a reusable, generic dashboard foundation.

The goal is to create a barebones but polished dashboard application that can be adapted to different domains by swapping in custom data sources, parsers, metrics, widgets, and notification hooks. It is not intended to ship with business-specific logic or vendor-specific assumptions.

## Current Goal

Configurable Dashboard OS is meant to become a reusable dashboard skeleton with:

- A FastAPI backend
- SQLite persistence
- Jinja templates
- Static CSS and JavaScript
- Settings/configuration screens
- Generic records/items/events
- Reusable dashboard panels
- Widget placeholder cards
- Date range controls
- Basic table/list/detail patterns
- A generic rule/score engine
- Source connector, parser, and notifier stubs

The current app is intentionally neutral. Domain-specific behavior should be added by implementing the extension points instead of hardcoding assumptions into the dashboard shell.

## Project Status

This is an active refactor. Expect rough edges.

Recent work has focused on:

- Removing old project-specific integrations and terminology
- Replacing alert/security-specific logic with generic records and rules
- Preserving a configurable dashboard layout
- Adding customizable panel shells
- Cleaning up UI styling and interaction behavior
- Separating reusable structure from project-specific implementation

The dashboard is usable locally, but the API, UI, storage shape, and customization model may continue to change.

## What Is Included

- FastAPI application setup
- Route organization for dashboard, records, settings, actions, and API previews
- SQLite schema and persistence helpers
- Generic `Record` and `AppConfig` models
- Generic parser for simple key-value payloads
- Generic rule engine for configurable scores and labels
- Source connector stub
- Notification hook stub
- Background sync pattern, disabled by default
- Dashboard layout with metric cards, time filters, and configurable panels
- Settings page for source, parser, notification, and scoring options
- Tests for parser, rule engine, and storage behavior

## What This Is Not

This is not a finished SaaS dashboard yet.

It does not include a real production connector, real authentication, multi-user permissions, a widget marketplace, or a finalized design system. Those are future customization points.

## Run Locally

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python -m uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/dashboard
```

The app creates local runtime files under `data/` and `logs/`. Those are intentionally ignored by git.

## Configuration

Copy `.env.example` to `.env` if you want to override local paths:

```text
APP_DATABASE_PATH=./data/dashboard_skeleton.db
APP_LOG_PATH=./logs/app.log
APP_POLL_INTERVAL_SECONDS=60
```

Most app behavior is also configurable from the settings screen.

## Extension Points

Start here when adapting the skeleton:

- `app/source_connector.py` - fetch or receive raw source payloads
- `app/parser.py` - map payloads into generic records
- `app/rule_engine.py` - adjust scoring labels and rule behavior
- `app/notifier.py` - implement outbound notification delivery
- `app/routes/dashboard.py` - add domain-specific metrics and widget data
- `app/templates/dashboard.html` - replace placeholder widgets with real widgets
- `app/storage.py` - add persistence helpers for new data shapes

## Tests

```powershell
.\.venv\Scripts\python -m pytest
```

## Notes

This repository is intentionally being kept generic. Private assumptions, vendor names, domain-specific scoring rules, and one-off integration logic should stay out of the base skeleton.
