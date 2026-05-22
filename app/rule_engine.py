import json
import re
from datetime import datetime, timedelta, timezone

from app.database import get_connection
from app.models import AppConfig, DEFAULT_SCORE_RULES, NotificationDecision, Record

LABEL_RANKS = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}


def _config(config: AppConfig | None) -> AppConfig:
    if config is not None:
        return config
    from app.storage import get_config

    return get_config()


def parse_score_rules(value: str | None) -> list[tuple[str, int]]:
    rows: list[tuple[str, int]] = []
    source = value or DEFAULT_SCORE_RULES
    for line in source.splitlines():
        if not line.strip() or line.strip().startswith("#") or "=" not in line:
            continue
        label, score_text = line.split("=", 1)
        try:
            score = int(score_text.strip())
        except ValueError:
            continue
        label = label.strip().lower()
        if label:
            rows.append((label, score))
    return rows


def score_label(score: int, config: AppConfig | None = None) -> str:
    cfg = _config(config)
    if score >= cfg.score_critical_threshold:
        return "Critical"
    if score >= cfg.score_high_threshold:
        return "High"
    if score >= cfg.score_medium_threshold:
        return "Medium"
    return "Low"


def _text_blob(record: Record) -> str:
    return " ".join(
        [
            record.title,
            record.source,
            record.category,
            record.status,
            record.owner,
            record.resource,
            record.summary,
            record.details,
        ]
    ).lower()


def rule_adjustments(record: Record, config: AppConfig | None = None) -> tuple[int, list[str]]:
    cfg = _config(config)
    adjustment = 0
    reasons: list[str] = []
    blob = _text_blob(record)

    for label, points in parse_score_rules(cfg.score_rules):
        if re.search(r"\b" + re.escape(label) + r"\b", blob):
            adjustment += points
            reasons.append(f"{label} rule {points:+d}")

    now = record.received_time.astimezone(timezone.utc)
    current_iso = now.isoformat()
    repeat_window = (now - timedelta(hours=cfg.repeat_window_hours)).isoformat()
    volume_window = (now - timedelta(hours=cfg.source_volume_window_hours)).isoformat()

    with get_connection() as conn:
        repeat_count = 0
        if record.category and record.resource:
            repeat_count = conn.execute(
                """
                SELECT COUNT(*) AS c FROM records
                WHERE category = ? AND resource = ?
                  AND received_time >= ? AND received_time < ?
                """,
                (record.category, record.resource, repeat_window, current_iso),
            ).fetchone()["c"]
        if repeat_count >= 3:
            adjustment += cfg.repeat_3_adjustment
            reasons.append(f"same category and resource seen {repeat_count + 1} times")
        elif repeat_count >= 2:
            adjustment += cfg.repeat_2_adjustment
            reasons.append(f"same category and resource seen {repeat_count + 1} times")
        elif repeat_count >= 1:
            adjustment += cfg.repeat_1_adjustment
            reasons.append(f"same category and resource seen {repeat_count + 1} times")

        source_count = 0
        if record.source:
            source_count = conn.execute(
                """
                SELECT COUNT(*) AS c FROM records
                WHERE source = ? AND received_time >= ? AND received_time < ?
                """,
                (record.source, volume_window, current_iso),
            ).fetchone()["c"]
        if source_count >= cfg.source_volume_threshold:
            adjustment += cfg.source_volume_adjustment
            reasons.append(f"source volume reached {source_count + 1} records")

    return adjustment, reasons


def score_record(record: Record, config: AppConfig | None = None) -> tuple[int, str, list[str]]:
    cfg = _config(config)
    adjustment, reasons = rule_adjustments(record, cfg)
    score = max(0, min(100, cfg.default_score + adjustment))
    return score, score_label(score, cfg), reasons


def scoring_breakdown(record: Record, config: AppConfig | None = None) -> dict[str, object]:
    cfg = _config(config)
    adjustment, reasons = rule_adjustments(record, cfg)
    score = max(0, min(100, cfg.default_score + adjustment))
    return {
        "base_score": cfg.default_score,
        "context_adjustment": adjustment,
        "score": score,
        "label": score_label(score, cfg),
        "reasons": reasons,
    }


def evaluate_record(record: Record, config: AppConfig | None = None) -> NotificationDecision:
    cfg = _config(config)
    if record.score < cfg.notification_min_score:
        return NotificationDecision(False, "below_notification_threshold", "", LABEL_RANKS.get(record.score_label, 0), 1)
    identity = "|".join(
        part.strip().lower()
        for part in (record.source, record.category, record.resource or record.owner or "record")
        if part
    )
    fingerprint = f"notification|{cfg.notification_cooldown_hours}h|{identity}"
    return NotificationDecision(True, "score_threshold", fingerprint, LABEL_RANKS.get(record.score_label, 0), 1)


def should_send_notification(decision: NotificationDecision, config: AppConfig | None = None) -> bool:
    if not decision.should_notify:
        return False
    cfg = _config(config)
    window_start = (datetime.now(timezone.utc) - timedelta(hours=cfg.notification_cooldown_hours)).isoformat()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT created_at FROM notifications
            WHERE fingerprint = ?
            ORDER BY created_at DESC LIMIT 1
            """,
            (decision.fingerprint,),
        ).fetchone()
    if row is None:
        return True
    last_sent = row["created_at"]
    if not last_sent:
        return True
    try:
        return datetime.fromisoformat(last_sent) <= datetime.fromisoformat(window_start)
    except ValueError:
        return True


def encode_reasons(reasons: list[str]) -> str:
    return json.dumps(reasons)
