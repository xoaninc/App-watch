from sqlalchemy import Column, String, Integer, Float
from core.base import Base


class StopPlatformModel(Base):
    """SQLAlchemy model for platform coordinates at a stop.

    Each physical station can have multiple platforms. Lines that share
    the same platform (same coordinates) are grouped in the `lines` field.

    Examples:
    - Metro: Each line has different coords → one entry per line
      METRO_120: lines="L6", lat=40.446, lon=-3.692
      METRO_120: lines="L8", lat=40.447, lon=-3.691

    - Cercanías: Lines sharing a platform → grouped
      RENFE_18002: lines="C3, C4a, C4b", lat=40.445, lon=-3.692
      RENFE_18002: lines="C7, C8a, C8b, C10", lat=40.445, lon=-3.693
    """
    __tablename__ = "stop_platform"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Reference to gtfs_stops (not a FK to allow flexibility)
    stop_id = Column(String(100), nullable=False, index=True)

    # Line identifier(s) - can be single "L6" or multiple "C2, C3, C4a, C4b"
    lines = Column(String(255), nullable=False, index=True)

    # Platform coordinates
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)

    # Data source
    source = Column(String(50), nullable=True)  # 'gtfs', 'osm', 'manual'

    def __repr__(self):
        return f"<StopPlatform {self.stop_id} - {self.lines}: ({self.lat}, {self.lon})>"
