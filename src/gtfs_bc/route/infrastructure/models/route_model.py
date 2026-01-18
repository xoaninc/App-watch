from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from core.base import Base
from src.gtfs_bc.agency.infrastructure.models.agency_model import AgencyModel


class RouteModel(Base):
    """SQLAlchemy model for GTFS Route."""

    __tablename__ = "gtfs_routes"

    id = Column(String(100), primary_key=True)
    agency_id = Column(String(100), ForeignKey("gtfs_agencies.id"), nullable=False)
    short_name = Column(String(50), nullable=False)
    long_name = Column(String(255), nullable=False)
    route_type = Column(Integer, nullable=False, default=2)  # 2 = Rail
    color = Column(String(6), nullable=True)  # Hex color without #
    text_color = Column(String(6), nullable=True)
    description = Column(String(500), nullable=True)
    url = Column(String(500), nullable=True)
    sort_order = Column(Integer, nullable=True)

    # Network relationship
    network_id = Column(String(20), ForeignKey("gtfs_networks.code", ondelete="SET NULL"), nullable=True, index=True)

    # Renfe line metadata
    renfe_idlinea = Column(Integer, nullable=True)

    # Route geometry (LineString)
    geometry = Column(Geometry(geometry_type='LINESTRING', srid=4326), nullable=True)

    # Relationships
    agency = relationship(AgencyModel, backref="routes")
    network = relationship("NetworkModel", back_populates="routes")
