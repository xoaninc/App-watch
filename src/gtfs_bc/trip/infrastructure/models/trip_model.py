from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.orm import relationship
from core.base import Base


class TripModel(Base):
    """SQLAlchemy model for GTFS Trip."""

    __tablename__ = "gtfs_trips"

    id = Column(String(100), primary_key=True)
    route_id = Column(String(100), ForeignKey("gtfs_routes.id"), nullable=False)
    service_id = Column(String(100), ForeignKey("gtfs_calendar.service_id"), nullable=False)
    headsign = Column(String(255), nullable=True)
    short_name = Column(String(100), nullable=True)
    direction_id = Column(Integer, nullable=True)  # 0 = outbound, 1 = inbound
    block_id = Column(String(100), nullable=True)
    shape_id = Column(String(100), nullable=True)
    wheelchair_accessible = Column(Integer, nullable=True)
    bikes_allowed = Column(Integer, nullable=True)

    # Relationships
    route = relationship("RouteModel", backref="trips")
    calendar = relationship("CalendarModel", backref="trips")
