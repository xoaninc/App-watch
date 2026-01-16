from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint, Index
from core.base import Base


class StopRouteSequenceModel(Base):
    """SQLAlchemy model for stop sequence in a route.

    Stores the position (sequence number based on closest point in route geometry)
    of each stop in each route.
    """

    __tablename__ = "gtfs_stop_route_sequence"

    id = Column(Integer, primary_key=True)
    stop_id = Column(String(100), ForeignKey("gtfs_stops.id"), nullable=False)
    route_id = Column(String(100), ForeignKey("gtfs_routes.id"), nullable=False)
    sequence = Column(Integer, nullable=False)  # Index of closest point in route geometry

    # Unique constraint: each stop appears only once per route
    __table_args__ = (
        UniqueConstraint('stop_id', 'route_id', name='uq_stop_route_sequence'),
        Index('idx_route_sequence', 'route_id', 'sequence'),
    )
