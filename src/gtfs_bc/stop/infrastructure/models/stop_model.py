import re
from sqlalchemy import Column, String, Float, Integer, ForeignKey, Text
from sqlalchemy.orm import relationship
from core.base import Base


class StopModel(Base):
    """SQLAlchemy model for GTFS Stop."""

    __tablename__ = "gtfs_stops"

    id = Column(String(100), primary_key=True)
    name = Column(String(255), nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    code = Column(String(50), nullable=True)
    description = Column(String(500), nullable=True)
    zone_id = Column(String(100), nullable=True)
    url = Column(String(500), nullable=True)
    location_type = Column(Integer, nullable=False, default=0)
    parent_station_id = Column(String(100), ForeignKey("gtfs_stops.id"), nullable=True)
    timezone = Column(String(100), nullable=True)
    wheelchair_boarding = Column(Integer, nullable=True)
    platform_code = Column(String(50), nullable=True)
    province = Column(String(50), nullable=True)

    # Renfe station metadata
    renfe_codigo_estacion = Column(Integer, nullable=True)
    color = Column(String(50), nullable=True)
    lineas = Column(String(500), nullable=True)  # Lines serving this stop (from LINEAS field)
    parking_bicis = Column(Text, nullable=True)
    accesibilidad = Column(String(100), nullable=True)
    cor_bus = Column(Text, nullable=True)
    cor_metro = Column(Text, nullable=True)
    cor_ml = Column(Text, nullable=True)
    cor_cercanias = Column(Text, nullable=True)
    cor_tranvia = Column(Text, nullable=True)

    # Self-referential relationship for parent station
    parent_station = relationship("StopModel", remote_side=[id], backref="child_stops")

    @property
    def is_hub(self) -> bool:
        """Calculate if this stop is a transport hub.

        A hub is a station with 2 or more DIFFERENT transport types:
        - Metro (cor_metro)
        - Cercanías/Rodalies (cor_cercanias with C*/R* lines only)
        - Metro Ligero (cor_ml)
        - Tranvía (cor_tranvia)

        Note: Multiple lines of the same type don't make a hub.
        Euskotren lines (E1, E2, TR) in cor_cercanias are NOT counted.
        """
        transport_count = 0

        if self.cor_metro:
            transport_count += 1

        # Only count real Cercanías (C*/R* patterns), not Euskotren (E1, E2, TR)
        if self.cor_cercanias:
            lines = [line.strip() for line in self.cor_cercanias.split(',')]
            has_real_cercanias = any(re.match(r'^[CR]\d', line) for line in lines)
            if has_real_cercanias:
                transport_count += 1

        if self.cor_ml:
            transport_count += 1

        if self.cor_tranvia:
            transport_count += 1

        return transport_count >= 2
