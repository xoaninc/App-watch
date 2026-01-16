from dataclasses import dataclass
from typing import Optional


@dataclass
class Agency:
    """GTFS Agency entity - represents a transit agency."""

    id: str
    name: str
    url: Optional[str] = None
    timezone: str = "Europe/Madrid"
    lang: Optional[str] = None
    phone: Optional[str] = None

    @classmethod
    def from_gtfs(cls, row: dict) -> "Agency":
        """Create Agency from GTFS CSV row."""
        return cls(
            id=row.get("agency_id", ""),
            name=row.get("agency_name", ""),
            url=row.get("agency_url"),
            timezone=row.get("agency_timezone", "Europe/Madrid"),
            lang=row.get("agency_lang"),
            phone=row.get("agency_phone"),
        )
