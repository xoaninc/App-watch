from sqlalchemy import Column, String, Integer, Float
from core.base import Base


class StopPlatformModel(Base):
    """SQLAlchemy model for platform coordinates per line at a stop.

    Each physical station can have multiple platforms, one per line.
    This table stores the specific coordinates of each platform/line.

    Example: Nuevos Ministerios has platforms for L6, L8, L10, C4a, C8a,
    each at slightly different coordinates.
    """
    __tablename__ = "stop_platform"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Reference to gtfs_stops (not a FK to allow flexibility)
    stop_id = Column(String(100), nullable=False, index=True)

    # Line identifier (L6, C4a, T1, E1, S1, ML1, etc.)
    line = Column(String(50), nullable=False, index=True)

    # Platform coordinates
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)

    # Data source
    source = Column(String(50), nullable=True)  # 'gtfs', 'osm', 'manual'

    def __repr__(self):
        return f"<StopPlatform {self.stop_id} - {self.line}: ({self.lat}, {self.lon})>"
