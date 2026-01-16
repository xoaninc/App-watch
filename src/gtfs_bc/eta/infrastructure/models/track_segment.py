from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, DateTime, Index
from core.base import Base


class TrackSegmentModel(Base):
    """Model for track segments between stops.

    A segment represents the track between two consecutive stops on a route.
    """
    __tablename__ = "gtfs_track_segments"

    id = Column(String(100), primary_key=True)  # route_id:from_stop:to_stop
    route_id = Column(String(50), nullable=False, index=True)
    from_stop_id = Column(String(50), nullable=False, index=True)
    to_stop_id = Column(String(50), nullable=False, index=True)
    sequence = Column(Integer, nullable=False)  # Order in the route
    distance_meters = Column(Float, nullable=True)  # Calculated from coordinates
    scheduled_travel_time_seconds = Column(Integer, nullable=True)  # From GTFS
    avg_travel_time_seconds = Column(Float, nullable=True)  # Calculated from history
    avg_speed_kmh = Column(Float, nullable=True)  # Calculated
    sample_count = Column(Integer, default=0)  # Number of observations
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_track_segments_route_stops", "route_id", "from_stop_id", "to_stop_id"),
    )

    def __repr__(self):
        return f"<TrackSegment {self.from_stop_id} -> {self.to_stop_id}>"
