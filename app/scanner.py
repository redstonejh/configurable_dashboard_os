import argparse
import json
import logging
from datetime import datetime, timedelta, timezone

from app.database import get_connection, init_db
from app.logger import setup_logging
from app.models import Record
from app.notifier import Notifier
from app.parser import parse_record_payload
from app.rule_engine import (
    encode_reasons,
    evaluate_record,
    score_record,
    should_send_notification,
)
from app.source_connector import SourceConnector
from app.storage import (
    add_event,
    add_notification,
    get_config,
    get_state,
    record_exists,
    save_record,
    update_record_rule_reason,
    update_state,
)

logger = logging.getLogger(__name__)
DEFAULT_LOOKBACK_DAYS = 60
DEFAULT_POLL_INTERVAL_SECONDS = 60


def _date_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).date().isoformat()


def _merge_coverage(start_date: str, end_date: str | None = None) -> None:
    start = start_date[:10]
    end = (end_date or _date_text(datetime.now(timezone.utc)))[:10]
    current_start = get_state("sync_coverage_start")
    current_end = get_state("sync_coverage_end")
    if not current_start or start < current_start:
        update_state("sync_coverage_start", start)
    if not current_end or end > current_end:
        update_state("sync_coverage_end", end)


def _required_fields() -> list[str]:
    config = get_config()
    return [
        field.strip()
        for field in (config.parser_required_fields or "").split(",")
        if field.strip()
    ]


def _process_payloads(payloads: list[dict], source: str) -> dict[str, int]:
    init_db()
    config = get_config()
    notifier = Notifier(config.notification_hook_url)
    processed = skipped = notified = ordinary = parse_failed = 0
    parse_failure_examples: list[str] = []
    required_fields = _required_fields()

    for payload in payloads:
        try:
            record = parse_record_payload(payload)
        except Exception as exc:
            parse_failed += 1
            title = str(payload.get("title") or payload.get("id") or "Untitled payload")
            parse_failure_examples.append(f"{title}: {exc}")
            add_event(None, "parse_failed", f"{source}: {title}: {exc}")
            logger.exception("Parser failed for payload")
            continue

        if record.external_id and record_exists(record.external_id):
            skipped += 1
            continue

        missing_fields = [field for field in required_fields if not getattr(record, field, "")]
        if missing_fields:
            parse_failed += 1
            detail = f"missing {', '.join(missing_fields)}"
            parse_failure_examples.append(f"{record.title}: {detail}")
            add_event(None, "parse_failed", f"{source}: {record.title}: {detail}")
            skipped += 1
            continue

        score, label, reasons = score_record(record, config)
        record.score = score
        record.score_label = label
        record.score_reasons = encode_reasons(reasons)
        record_id = save_record(record)
        if record_id is None:
            skipped += 1
            continue

        processed += 1
        decision = evaluate_record(record, config)
        update_record_rule_reason(record_id, decision.reason)
        if decision.should_notify:
            if should_send_notification(decision, config):
                payload_text = notifier.format_record(record, decision.reason, decision.count)
                if config.notification_preview_mode or not config.notification_hook_url:
                    add_notification(record_id, "preview", decision.reason, payload_text, fingerprint=decision.fingerprint)
                    add_event(record_id, "notification", f"{decision.reason} (local preview)")
                    notified += 1
                else:
                    try:
                        result = notifier.send_text(payload_text)
                        add_notification(
                            record_id,
                            result.status,
                            decision.reason,
                            payload_text,
                            result.response_text,
                            decision.fingerprint,
                        )
                        add_event(record_id, "notification", decision.reason)
                        update_state("last_notification_time", datetime.now(timezone.utc).isoformat())
                        notified += 1
                    except Exception as exc:
                        add_notification(
                            record_id,
                            "failed",
                            decision.reason,
                            payload_text,
                            str(exc),
                            decision.fingerprint,
                        )
                        add_event(record_id, "notification_failed", decision.reason)
                        logger.exception("Notification hook failed")
            else:
                add_event(record_id, "suppressed", f"{decision.reason} cooldown")
        else:
            add_event(record_id, "ordinary", decision.reason)
            ordinary += 1

    update_state("last_sync_time", datetime.now(timezone.utc).isoformat())
    update_state("last_parse_failed_count", str(parse_failed))
    update_state("last_parse_failed_examples", json.dumps(parse_failure_examples[:5]))
    logger.info(
        "%s sync complete: processed=%s skipped=%s notified=%s ordinary=%s parse_failed=%s",
        source,
        processed,
        skipped,
        notified,
        ordinary,
        parse_failed,
    )
    return {
        "processed": processed,
        "skipped": skipped,
        "notified": notified,
        "ordinary": ordinary,
        "parse_failed": parse_failed,
    }


def run_sync() -> dict[str, int]:
    init_db()
    config = get_config()
    start = datetime.now(timezone.utc) - timedelta(days=config.lookback_days or DEFAULT_LOOKBACK_DAYS)
    connector = SourceConnector(config.source_name)
    payloads = list(connector.fetch_records(start=start))
    result = _process_payloads(payloads, config.source_name)
    _merge_coverage(_date_text(start))
    return result


def run_sync_range(start_date: str, end_date: str | None = None) -> dict[str, int]:
    init_db()
    config = get_config()
    start = datetime.fromisoformat((start_date[:10] + "T00:00:00+00:00"))
    end = None
    if end_date:
        end = datetime.fromisoformat((end_date[:10] + "T23:59:59+00:00"))
    connector = SourceConnector(config.source_name)
    payloads = list(connector.fetch_records(start=start, end=end))
    result = _process_payloads(payloads, f"{config.source_name} range")
    _merge_coverage(start_date, end_date)
    return result


def _record_from_row(row) -> Record:
    received = datetime.fromisoformat(str(row["received_time"]).replace("Z", "+00:00"))
    return Record(
        external_id=row["external_id"],
        received_time=received,
        title=row["title"],
        source=row["source"],
        category=row["category"],
        status=row["status"],
        owner=row["owner"] or "",
        resource=row["resource"] or "",
        summary=row["summary"] or "",
        details=row["details"] or "",
        raw_payload=row["raw_payload"] or "",
        score=row["score"],
        score_label=row["score_label"],
        score_reasons=row["score_reasons"],
        rule_reason=row["rule_reason"],
        policy_version=row["policy_version"],
    )


def backfill_scores(force: bool = False) -> int:
    init_db()
    config = get_config()
    where = "" if force else "WHERE score_label = '' OR score = 0"
    with get_connection() as conn:
        rows = conn.execute(f"SELECT * FROM records {where} ORDER BY received_time ASC").fetchall()
    updated = 0
    for row in rows:
        record = _record_from_row(row)
        score, label, reasons = score_record(record, config)
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE records
                SET score = ?, score_label = ?, score_reasons = ?, policy_version = ?
                WHERE id = ?
                """,
                (score, label, json.dumps(reasons), "generic-rules-v1", row["id"]),
            )
        updated += 1
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the generic dashboard source sync once.")
    args = parser.parse_args()
    setup_logging()
    result = run_sync()
    print(result)


if __name__ == "__main__":
    main()
