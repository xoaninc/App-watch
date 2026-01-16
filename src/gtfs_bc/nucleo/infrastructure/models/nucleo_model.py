from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.orm import relationship
from core.base import Base


class NucleoModel(Base):
    """SQLAlchemy model for Renfe Regional Networks (Núcleos)."""

    __tablename__ = "gtfs_nucleos"

    id = Column(Integer, primary_key=True, autoincrement=False)
    name = Column(String(100), nullable=False, unique=True, index=True)
    color = Column(String(50), nullable=True)  # RGB format "R,G,B"

    # Geographic boundaries
    bounding_box_min_lat = Column(Float, nullable=True)
    bounding_box_max_lat = Column(Float, nullable=True)
    bounding_box_min_lon = Column(Float, nullable=True)
    bounding_box_max_lon = Column(Float, nullable=True)

    # Center point coordinates
    center_lat = Column(Float, nullable=True)
    center_lon = Column(Float, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships (no need to specify foreign_keys explicitly)
    stops = relationship("StopModel", back_populates="nucleo")
    routes = relationship("RouteModel", back_populates="nucleo")

    def __repr__(self):
        return f"<NucleoModel(id={self.id}, name={self.name})>"
