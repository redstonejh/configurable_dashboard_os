from datetime import datetime, timedelta, timezone

import pytest

from app.config import get_app_settings
from app.database import init_db
from app.models import AppConfig, Record
from app.rule_engine import evaluate_record, score_record
from app.storage import save_record


@pytest.fixture(autouse=True)
def isolated_database(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("APP_LOG_PATH", str(tmp_path / "test.log"))
    get_app_settings.cache_clear()
    init_db()
    yield
    get_app_settings.cache_clear()


def _record(**overrides):
    values = {
        "external_id": "record-1",
        "received_time": datetime.now(timezone.utc),
        "title": "Priority metric crossed threshold",
        "source": "Analytics",
        "category": "Metric",
        "status": "Priority",
        "owner": "Team",
        "resource": "Metric Set",
        "summary": "",
        "details": "",
    }
    values.update(overrides)
    return Record(**values)


def test_score_record_uses_configurable_label_rules():
    config = AppConfig(default_score=40, score_rules="priority=25\ncomplete=-20")

    score, label, reasons = score_record(_record(), config)

    assert score == 65
    assert label == "High"
    assert "priority rule +25" in reasons


def test_score_record_applies_repeat_context():
    config = AppConfig(default_score=40, score_rules="", repeat_1_adjustment=12)
    prior = _record(
        external_id="record-prior",
        received_time=datetime.now(timezone.utc) - timedelta(hours=1),
        title="Metric record",
        status="Open",
    )
    save_record(prior)

    score, _label, reasons = score_record(
        _record(external_id="record-current", title="Metric record", status="Open"),
        config,
    )

    assert score == 52
    assert any("same category and resource" in reason for reason in reasons)


def test_evaluate_record_uses_notification_threshold():
    config = AppConfig(notification_min_score=80)
    record = _record()
    record.score = 85
    record.score_label = "Critical"

    decision = evaluate_record(record, config)

    assert decision.should_notify is True
    assert decision.reason == "score_threshold"
