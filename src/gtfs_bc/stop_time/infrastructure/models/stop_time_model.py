from sqlalchemy import Column, String, Integer, Float, ForeignKey, Index
from sqlalchemy.orm import relationship
from core.base import Base


class StopTimeModel(Base):
    """SQLAlchemy model for GTFS StopTime."""

    __tablename__ = "gtfs_stop_times"

    # Composite primary key
    trip_id = Column(String(100), ForeignKey("gtfs_trips.id"), primary_key=True)
    stop_sequence = Column(Integer, primary_key=True)

    stop_id = Column(String(100), ForeignKey("gtfs_stops.id"), nullable=False)
    arrival_time = Column(String(10), nullable=False)  # HH:MM:SS
    departure_time = Column(String(10), nullable=False)
    arrival_seconds = Column(Integer, nullable=False)  # For efficient queries
    departure_seconds = Column(Integer, nullable=False)
    stop_headsign = Column(String(255), nullable=True)
    pickup_type = Column(Integer, nullable=False, default=0)
    drop_off_type = Column(Integer, nullable=False, default=0)
    shape_dist_traveled = Column(Float, nullable=True)
    timepoint = Column(Integer, nullable=False, default=1)

    # Relationships
    trip = relationship("TripModel", backref="stop_times")
    stop = relationship("StopModel", backref="stop_times")

    # Indexes for common queries
    __table_args__ = (
        Index("ix_stop_times_stop_id", "stop_id"),
        Index("ix_stop_times_arrival", "arrival_seconds"),
    )
