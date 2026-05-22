from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class SourceConnector:
    """Example connector interface for adapting the skeleton to any data source.

    TODO: Implement authentication, pagination, rate limiting, and mapping for
    the source used by your project. The app expects dictionaries that the
    generic parser can convert into records.
    """

    source_name: str = "Source"

    def test_connection(self) -> bool:
        return True

    def fetch_records(self, start: datetime | None = None, end: datetime | None = None) -> Iterable[dict]:
        return []
