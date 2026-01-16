from sqlalchemy import Column, String, Integer, DateTime, Text
from datetime import datetime
from core.base import Base


class FeedImportModel(Base):
    """SQLAlchemy model for GTFS Feed Import tracking."""

    __tablename__ = "gtfs_feed_imports"

    id = Column(String(100), primary_key=True)
    source_url = Column(String(500), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    agencies_count = Column(Integer, nullable=False, default=0)
    routes_count = Column(Integer, nullable=False, default=0)
    stops_count = Column(Integer, nullable=False, default=0)
    trips_count = Column(Integer, nullable=False, default=0)
    stop_times_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
