from sqlalchemy import Column, String, Integer, Float, Boolean, Time
from core.base import Base


class StopVestibuleModel(Base):
    """SQLAlchemy model for station vestibules (internal lobbies).

    Each metro station can have multiple internal vestibules at different
    underground levels. These are the areas between the entrance and the
    platforms, typically containing ticket machines and turnstiles.

    Examples:
    - Sol station has multiple vestibules at different levels
    - Some vestibules may be closed during certain hours
    - Vestibules may have different turnstile types
    """
    __tablename__ = "stop_vestibule"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Reference to gtfs_stops (not a FK to allow flexibility)
    stop_id = Column(String(100), nullable=False, index=True)

    # Vestibule name/identifier
    name = Column(String(255), nullable=False)

    # Location coordinates (WGS84)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)

    # Underground level (-1, -2, etc.)
    level = Column(Integer, nullable=True)

    # Vestibule and turnstile types
    vestibule_type = Column(String(50), nullable=True)
    turnstile_type = Column(String(50), nullable=True)

    # Operating hours
    opening_time = Column(Time, nullable=True)
    closing_time = Column(Time, nullable=True)

    # Accessibility
    wheelchair = Column(Boolean, nullable=True)

    # Data source
    source = Column(String(50), nullable=True)  # 'crtm', 'osm', 'manual'

    def __repr__(self):
        return f"<StopVestibule {self.stop_id} - {self.name}: ({self.lat}, {self.lon})>"
