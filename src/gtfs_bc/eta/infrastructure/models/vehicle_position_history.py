from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Integer, Index
from core.base import Base


class VehiclePositionHistoryModel(Base):
    """Model for storing historical vehicle positions.

    This table stores vehicle position samples for calculating travel times
    and building segment statistics.
    """
    __tablename__ = "gtfs_vehicle_position_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_id = Column(String(50), nullable=False, index=True)
    trip_id = Column(String(50), nullable=False, index=True)
    route_id = Column(String(50), nullable=True, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    stop_id = Column(String(50), nullable=True, index=True)  # Current or next stop
    current_status = Column(String(20), nullable=True)  # INCOMING_AT, STOPPED_AT, IN_TRANSIT_TO
    timestamp = Column(DateTime, nullable=False, index=True)
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_position_history_trip_time", "trip_id", "timestamp"),
        Index("ix_position_history_vehicle_time", "vehicle_id", "timestamp"),
        # Partition-friendly index for date-based queries
        Index("ix_position_history_recorded", "recorded_at"),
    )

    def __repr__(self):
        return f"<VehiclePositionHistory {self.vehicle_id} @ {self.timestamp}>"
