from sqlalchemy import Column, String, Float, Integer, ForeignKey, Index
from sqlalchemy.orm import relationship
from core.base import Base


class ShapeModel(Base):
    """SQLAlchemy model for GTFS Shape (metadata)."""

    __tablename__ = "gtfs_shapes"

    id = Column(String(100), primary_key=True)

    # Relationships
    points = relationship("ShapePointModel", back_populates="shape", order_by="ShapePointModel.sequence")


class ShapePointModel(Base):
    """SQLAlchemy model for GTFS Shape points."""

    __tablename__ = "gtfs_shape_points"

    # Composite primary key
    shape_id = Column(String(100), ForeignKey("gtfs_shapes.id"), primary_key=True)
    sequence = Column(Integer, primary_key=True)

    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    dist_traveled = Column(Float, nullable=True)

    # Relationships
    shape = relationship("ShapeModel", back_populates="points")

    __table_args__ = (
        Index("ix_shape_points_shape_id", "shape_id"),
    )
