from dataclasses import dataclass

from app.models import Record


@dataclass(frozen=True)
class NotificationResult:
    status: str
    response_text: str = ""


class Notifier:
    """Generic notification hook interface.

    TODO: Connect this class to your preferred delivery mechanism. The skeleton
    only formats payloads and records preview entries locally.
    """

    def __init__(self, hook_url: str = "") -> None:
        self.hook_url = hook_url

    def format_record(self, record: Record, reason: str, count: int = 1) -> str:
        lines = [
            f"**{record.score_label or 'Record'}: {record.title}**",
            f"Reason: {reason.replace('_', ' ').title()}",
            f"Source: {record.source or 'Unknown'}",
            f"Category: {record.category or 'Unknown'}",
            f"Status: {record.status or 'Unknown'}",
            f"Owner: {record.owner or 'Unassigned'}",
            f"Resource: {record.resource or 'Unspecified'}",
            f"Score: {record.score}",
            f"Matching count: {count}",
            f"Received: {record.received_time.isoformat()}",
        ]
        return "\n\n".join(lines)

    def send_text(self, text: str) -> NotificationResult:
        raise NotImplementedError("Add a project-specific notification sender here.")
