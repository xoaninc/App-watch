from sqlalchemy import Column, String
from core.base import Base


class AgencyModel(Base):
    """SQLAlchemy model for GTFS Agency."""

    __tablename__ = "gtfs_agencies"

    id = Column(String(100), primary_key=True)
    name = Column(String(255), nullable=False)
    url = Column(String(500), nullable=True)
    timezone = Column(String(100), nullable=False, default="Europe/Madrid")
    lang = Column(String(10), nullable=True)
    phone = Column(String(50), nullable=True)
