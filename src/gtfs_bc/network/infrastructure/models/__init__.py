from sqlalchemy import Column, String, Text
from core.base import Base


class NetworkModel(Base):
    """SQLAlchemy model for Cercanías network metadata."""

    __tablename__ = "gtfs_networks"

    code = Column(String(10), primary_key=True)  # Network code (e.g., "10T")
    name = Column(String(100), nullable=False)  # Network name
    city = Column(String(100), nullable=False)  # Main city
    region = Column(String(100), nullable=False)  # Region/community
    color = Column(String(6), nullable=False)  # Primary brand color (hex)
    text_color = Column(String(6), nullable=False, default="FFFFFF")
    logo_url = Column(String(500), nullable=True)
    wikipedia_url = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)

    def __repr__(self):
        return f"<Network {self.code}: {self.name}>"


__all__ = ["NetworkModel"]
