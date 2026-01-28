from sqlalchemy import Column, String, Integer, Float, Boolean, Time
from core.base import Base


class StopAccessModel(Base):
    """SQLAlchemy model for station access points (entrances/exits).

    Each metro station can have multiple physical entrances (bocas) at street
    level. This table stores their locations, addresses, and operating hours.

    Examples:
    - Sol station has ~10 different entrances on different streets
    - Each entrance may have different operating hours
    - Some entrances are wheelchair accessible, others are not
    """
    __tablename__ = "stop_access"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Reference to gtfs_stops (not a FK to allow flexibility)
    stop_id = Column(String(100), nullable=False, index=True)

    # Access point name/identifier
    name = Column(String(255), nullable=False)

    # Location coordinates (WGS84)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)

    # Street address
    street = Column(String(255), nullable=True)
    street_number = Column(String(20), nullable=True)

    # Operating hours
    opening_time = Column(Time, nullable=True)
    closing_time = Column(Time, nullable=True)

    # Accessibility
    wheelchair = Column(Boolean, nullable=True)

    # Entry level (0 = street, -1 = first underground, etc.)
    level = Column(Integer, nullable=True)

    # Data source
    source = Column(String(50), nullable=True)  # 'crtm', 'osm', 'manual'

    def __repr__(self):
        return f"<StopAccess {self.stop_id} - {self.name}: ({self.lat}, {self.lon})>"
