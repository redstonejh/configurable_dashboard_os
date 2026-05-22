from dataclasses import dataclass, fields
from datetime import datetime
from typing import Any


DEFAULT_SCORE_RULES = """priority=20
blocked=18
late=14
manual=10
review=8
complete=-12
closed=-16"""


@dataclass(slots=True)
class AppConfig:
    app_name: str = "Configurable Dashboard Skeleton"
    source_name: str = "Source"
    source_description: str = "Generic source connector placeholder"
    source_poll_enabled: bool = False
    source_poll_interval_seconds: int = 60
    lookback_days: int = 60
    start_date: str = ""
    parser_required_fields: str = "title,source,category,status"
    notification_hook_url: str = ""
    notification_preview_mode: bool = True
    notification_cooldown_hours: int = 24
    notification_min_score: int = 85
    default_score: int = 35
    score_rules: str = DEFAULT_SCORE_RULES
    score_critical_threshold: int = 85
    score_high_threshold: int = 65
    score_medium_threshold: int = 40
    repeat_window_hours: int = 24
    repeat_1_adjustment: int = 8
    repeat_2_adjustment: int = 14
    repeat_3_adjustment: int = 20
    source_volume_window_hours: int = 24
    source_volume_threshold: int = 8
    source_volume_adjustment: int = 10
    rule_preset: str = "generic"


@dataclass(slots=True)
class Record:
    external_id: str
    received_time: datetime
    title: str
    source: str
    category: str
    status: str
    owner: str = ""
    resource: str = ""
    summary: str = ""
    details: str = ""
    raw_payload: str = ""
    score: int = 0
    score_label: str = ""
    score_reasons: str = ""
    rule_reason: str = ""
    policy_version: str = "generic-rules-v1"

    def as_dict(self) -> dict[str, Any]:
        data = {field.name: getattr(self, field.name) for field in fields(self)}
        data["received_time"] = self.received_time.isoformat()
        return data


@dataclass(slots=True)
class NotificationDecision:
    should_notify: bool
    reason: str
    fingerprint: str
    label_rank: int
    count: int
