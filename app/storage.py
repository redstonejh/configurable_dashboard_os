from dataclasses import fields
from datetime import datetime, timezone
import json
from typing import Any

from app.config import get_app_settings
from app.database import get_connection
from app.models import AppConfig, Record

SENSITIVE_KEYS = {"notification_hook_url"}


def _env_overrides(config: AppConfig) -> AppConfig:
    env = get_app_settings()
    config.source_poll_interval_seconds = env.poll_interval_seconds or config.source_poll_interval_seconds
    return config


def _coerce_value(current: object, value: object) -> object:
    if isinstance(current, bool):
        return str(value).lower() in {"1", "true", "yes", "on"}
    if isinstance(current, int):
        return int(value)
    return str(value)


def get_config(include_secrets: bool = True) -> AppConfig:
    config = AppConfig()
    with get_connection() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    for row in rows:
        if not hasattr(config, row["key"]):
            continue
        current = getattr(config, row["key"])
        try:
            setattr(config, row["key"], _coerce_value(current, row["value"]))
        except (TypeError, ValueError):
            continue
    config = _env_overrides(config)
    if not include_secrets:
        config.notification_hook_url = ""
    return config


def save_config(form_data: dict[str, Any]) -> None:
    valid_fields = {field.name for field in fields(AppConfig)}
    with get_connection() as conn:
        for key, value in form_data.items():
            if key not in valid_fields:
                continue
            if key in SENSITIVE_KEYS and not value:
                continue
            conn.execute(
                """
                INSERT INTO settings(key, value, sensitive)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    sensitive = excluded.sensitive
                """,
                (key, str(value), 1 if key in SENSITIVE_KEYS else 0),
            )


def get_setting(key: str) -> str:
    with get_connection() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else ""


def save_setting(key: str, value: str, sensitive: bool = False) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO settings(key, value, sensitive)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                sensitive = excluded.sensitive
            """,
            (key, value, 1 if sensitive else 0),
        )


def delete_setting(key: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM settings WHERE key = ?", (key,))


def record_exists(external_id: str) -> bool:
    with get_connection() as conn:
        row = conn.execute("SELECT 1 FROM records WHERE external_id = ?", (external_id,)).fetchone()
    return row is not None


def save_record(record: Record) -> int | None:
    data = record.as_dict()
    columns = ", ".join(data.keys())
    placeholders = ", ".join(["?"] * len(data))
    updates = ", ".join(
        f"{column} = excluded.{column}"
        for column in data
        if column != "external_id"
    )
    with get_connection() as conn:
        try:
            conn.execute(
                f"""
                INSERT INTO records({columns}) VALUES ({placeholders})
                ON CONFLICT(external_id) DO UPDATE SET {updates}
                """,
                tuple(data.values()),
            )
        except Exception:
            return None
        row = conn.execute("SELECT id FROM records WHERE external_id = ?", (record.external_id,)).fetchone()
    return int(row["id"]) if row else None


def update_record_rule_reason(record_id: int, reason: str) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE records SET rule_reason = ? WHERE id = ?", (reason, record_id))


def get_record(record_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM records WHERE id = ?", (record_id,)).fetchone()
    return dict(row) if row else None


def list_records(
    limit: int = 25,
    start: str = "",
    end: str = "",
    metric: str = "",
) -> list[dict[str, Any]]:
    conds: list[str] = []
    params: list[Any] = []
    if start:
        conds.append("received_time >= ?")
        params.append(f"{start}T00:00:00" if len(start) == 10 else start)
    if end:
        conds.append("received_time <= ?")
        params.append(f"{end}T23:59:59" if len(end) == 10 else end)
    if metric == "critical":
        conds.append("LOWER(score_label) = 'critical'")
    elif metric == "review":
        conds.append(
            "(LOWER(status) LIKE '%review%' OR LOWER(status) LIKE '%blocked%' "
            "OR LOWER(status) LIKE '%priority%')"
        )
    elif metric == "repeated":
        repeated_range = ""
        if start:
            repeated_range += " AND repeated_records.received_time >= ?"
            params.append(f"{start}T00:00:00" if len(start) == 10 else start)
        if end:
            repeated_range += " AND repeated_records.received_time <= ?"
            params.append(f"{end}T23:59:59" if len(end) == 10 else end)
        conds.append(
            f"""
            EXISTS (
                SELECT 1 FROM records repeated_records
                WHERE repeated_records.category = records.category
                  AND repeated_records.resource = records.resource
                  AND repeated_records.category != ''
                  AND repeated_records.resource != ''
                  {repeated_range}
                GROUP BY repeated_records.category, repeated_records.resource
                HAVING COUNT(*) >= 2
            )
            """
        )
    elif metric == "notified":
        conds.append(
            "EXISTS (SELECT 1 FROM notifications WHERE notifications.record_id = records.id)"
        )
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    params.append(limit)
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM records {where} ORDER BY received_time DESC LIMIT ?",
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def list_current_notification_cases(limit: int = 25, start: str = "", end: str = "") -> list[dict[str, Any]]:
    conds: list[str] = []
    params: list[Any] = []
    if start:
        conds.append("records.received_time >= ?")
        params.append(f"{start}T00:00:00" if len(start) == 10 else start)
    if end:
        conds.append("records.received_time <= ?")
        params.append(f"{end}T23:59:59" if len(end) == 10 else end)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    params.append(limit)
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT notifications.*, records.received_time, records.title,
                   records.source, records.category, records.status,
                   records.owner, records.resource, records.score_label,
                   records.score, records.id AS linked_record_id
            FROM notifications
            LEFT JOIN records ON records.id = notifications.record_id
            {where}
            ORDER BY notifications.created_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def list_events(event_type: str | None = None, limit: int = 25) -> list[dict[str, Any]]:
    sql = """
        SELECT rule_events.*, records.source, records.category, records.status
        FROM rule_events
        LEFT JOIN records ON records.id = rule_events.record_id
    """
    params: tuple[Any, ...] = ()
    if event_type:
        sql += " WHERE event_type = ?"
        params = (event_type,)
    sql += " ORDER BY rule_events.created_at DESC LIMIT ?"
    params += (limit,)
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def add_event(record_id: int | None, event_type: str, message: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO rule_events(record_id, event_type, message) VALUES (?, ?, ?)",
            (record_id, event_type, message),
        )


def add_notification(
    record_id: int | None,
    status: str,
    reason: str,
    payload: str,
    error: str = "",
    fingerprint: str = "",
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO notifications(record_id, status, reason, payload, error, fingerprint)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (record_id, status, reason, payload, error, fingerprint),
        )


def update_state(key: str, value: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO app_state(key, value)
            VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )


def get_state(key: str) -> str:
    with get_connection() as conn:
        row = conn.execute("SELECT value FROM app_state WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else ""


def dashboard_stats(start: str = "", end: str = "") -> dict[str, Any]:
    date_conds: list[str] = []
    date_params: list[Any] = []
    if start:
        date_conds.append("received_time >= ?")
        date_params.append(f"{start}T00:00:00" if len(start) == 10 else start)
    if end:
        date_conds.append("received_time <= ?")
        date_params.append(f"{end}T23:59:59" if len(end) == 10 else end)
    date_filter = (" AND " + " AND ".join(date_conds)) if date_conds else ""

    with get_connection() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) AS c FROM records WHERE 1=1{date_filter}",
            date_params,
        ).fetchone()["c"]
        critical = conn.execute(
            f"SELECT COUNT(*) AS c FROM records WHERE LOWER(score_label) = 'critical'{date_filter}",
            date_params,
        ).fetchone()["c"]
        repeated = conn.execute(
            f"""
            SELECT COUNT(*) AS c FROM (
                SELECT category, resource FROM records
                WHERE category != '' AND resource != ''{date_filter}
                GROUP BY category, resource HAVING COUNT(*) >= 2
            )
            """,
            date_params,
        ).fetchone()["c"]
        review = conn.execute(
            f"""
            SELECT COUNT(*) AS c FROM records
            WHERE (
                LOWER(status) LIKE '%review%'
                OR LOWER(status) LIKE '%blocked%'
                OR LOWER(status) LIKE '%priority%'
            ){date_filter}
            """,
            date_params,
        ).fetchone()["c"]
        preview_count = conn.execute(
            "SELECT COUNT(*) AS c FROM notifications WHERE status IN ('preview', 'logged')"
        ).fetchone()["c"]
    return {
        "total": total,
        "critical": critical,
        "repeated": repeated,
        "review": review,
        "notifications_logged": len(list_current_notification_cases(10000, start=start, end=end)),
        "preview_count": preview_count,
        "last_sync_time": get_state("last_sync_time"),
        "last_parse_failed_count": int(get_state("last_parse_failed_count") or 0),
        "last_parse_failed_examples": json.loads(get_state("last_parse_failed_examples") or "[]"),
        "last_notification_time": get_state("last_notification_time"),
        "sync_range_label": get_state("last_sync_range_label"),
        "sync_range_start": get_state("last_sync_range_start"),
        "sync_range_end": get_state("last_sync_range_end"),
    }


def historical_matches(category: str, resource: str, exclude_id: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM records
            WHERE id != ? AND category = ? AND resource = ?
            ORDER BY received_time DESC LIMIT 50
            """,
            (exclude_id, category, resource),
        ).fetchall()
    return [dict(row) for row in rows]


def notification_for_record(record_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT * FROM notifications
            WHERE record_id = ?
            ORDER BY created_at DESC LIMIT 1
            """,
            (record_id,),
        ).fetchone()
    return dict(row) if row else None


def record_count() -> int:
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM records").fetchone()
    return int(row["c"])


def clear_data() -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM notifications")
        conn.execute("DELETE FROM rule_events")
        conn.execute("DELETE FROM records")
        conn.execute("DELETE FROM app_state")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
