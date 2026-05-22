from datetime import datetime, timezone

import pytest

from app.config import get_app_settings
from app.database import init_db
from app.models import Record
from app.storage import dashboard_stats, list_records, record_count, save_record


@pytest.fixture(autouse=True)
def isolated_database(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("APP_LOG_PATH", str(tmp_path / "test.log"))
    get_app_settings.cache_clear()
    init_db()
    yield
    get_app_settings.cache_clear()


def _save_record(external_id: str, status: str) -> None:
    record = Record(
        external_id=external_id,
        received_time=datetime.now(timezone.utc),
        title=f"{status} record",
        source="Source",
        category="Workflow",
        status=status,
        owner="Team",
        resource="Queue",
        score=50,
        score_label="Medium",
    )
    save_record(record)


def test_records_persist_and_contribute_to_stats():
    _save_record("record-1", "Open")
    _save_record("record-2", "Review")

    assert record_count() == 2
    assert dashboard_stats()["total"] == 2


def test_list_records_filters_review_metric():
    _save_record("record-1", "Open")
    _save_record("record-2", "Review")
    _save_record("record-3", "Blocked")

    rows = list_records(metric="review")

    assert {row["status"] for row in rows} == {"Review", "Blocked"}
