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

    # Nucleo fields
    nucleo_id = Column(Integer, ForeignKey("gtfs_nucleos.id"), nullable=True)
    nucleo_name = Column(String(100), nullable=True)

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

    # Self-referential relationship for parent station
    parent_station = relationship("StopModel", remote_side=[id], backref="child_stops")

    # Nucleo relationship
    nucleo = relationship("NucleoModel", back_populates="stops", foreign_keys=[nucleo_id])
