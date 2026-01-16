from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from enum import Enum


class FeedImportStatus(str, Enum):
    """Status of a feed import."""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    PARSING = "parsing"
    IMPORTING = "importing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class FeedImport:
    """Entity representing a GTFS feed import operation."""

    id: str
    source_url: str
    status: FeedImportStatus = FeedImportStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    agencies_count: int = 0
    routes_count: int = 0
    stops_count: int = 0
    trips_count: int = 0
    stop_times_count: int = 0

    def start(self):
        """Mark import as started."""
        self.status = FeedImportStatus.DOWNLOADING
        self.started_at = datetime.utcnow()

    def set_parsing(self):
        """Mark import as parsing."""
        self.status = FeedImportStatus.PARSING

    def set_importing(self):
        """Mark import as importing."""
        self.status = FeedImportStatus.IMPORTING

    def complete(self, counts: dict):
        """Mark import as completed."""
        self.status = FeedImportStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.agencies_count = counts.get("agencies", 0)
        self.routes_count = counts.get("routes", 0)
        self.stops_count = counts.get("stops", 0)
        self.trips_count = counts.get("trips", 0)
        self.stop_times_count = counts.get("stop_times", 0)

    def fail(self, error: str):
        """Mark import as failed."""
        self.status = FeedImportStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.error_message = error
