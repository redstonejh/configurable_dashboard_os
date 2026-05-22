import json
import re
from collections.abc import Mapping
from datetime import datetime, timezone
from html import unescape
from typing import Any
from uuid import uuid4

from app.models import Record

FIELD_PATTERNS = {
    "title": [r"Title:\s*(.+)", r"Name:\s*(.+)"],
    "source": [r"Source:\s*(.+)", r"Origin:\s*(.+)"],
    "category": [r"Category:\s*(.+)", r"Type:\s*(.+)"],
    "status": [r"Status:\s*(.+)", r"State:\s*(.+)"],
    "owner": [r"Owner:\s*(.+)", r"Assigned to:\s*(.+)"],
    "resource": [r"Resource:\s*(.+)", r"Object:\s*(.+)"],
    "summary": [r"Summary:\s*(.+)", r"Description:\s*(.+)"],
    "details": [r"Details:\s*(.+)", r"Notes:\s*(.+)"],
}


def _clean_text(value: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    return re.sub(r"[ \t]+", " ", text).strip()


def _extract(patterns: list[str], text: str) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip().strip(".,;")
    return ""


def _parse_time(value: object) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return datetime.now(timezone.utc)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _payload_text(payload: Mapping[str, Any]) -> str:
    body = payload.get("body") or payload.get("content") or payload.get("raw_payload") or ""
    if isinstance(body, Mapping):
        body = body.get("content", "")
    return _clean_text(str(body or ""))


def parse_record_payload(payload: Mapping[str, Any]) -> Record:
    """Convert a generic source payload into the app's neutral record shape.

    TODO: Replace or extend this parser with domain-specific extraction rules
    when adapting the skeleton for a real source.
    """
    text = _payload_text(payload)
    raw_payload = text or json.dumps(dict(payload), default=str, sort_keys=True)
    values = {
        field: str(payload.get(field) or "").strip()
        for field in FIELD_PATTERNS
    }
    for field, patterns in FIELD_PATTERNS.items():
        if not values[field]:
            values[field] = _extract(patterns, text)

    return Record(
        external_id=str(payload.get("external_id") or payload.get("id") or f"record-{uuid4().hex}"),
        received_time=_parse_time(payload.get("received_time") or payload.get("created_at")),
        title=values["title"] or "Untitled record",
        source=values["source"] or "Source",
        category=values["category"] or "General",
        status=values["status"] or "New",
        owner=values["owner"],
        resource=values["resource"],
        summary=values["summary"],
        details=values["details"],
        raw_payload=raw_payload,
    )
