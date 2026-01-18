from sqlalchemy import Column, String, Text, Integer
from sqlalchemy.orm import relationship
from core.base import Base


class NetworkModel(Base):
    """SQLAlchemy model for transit network metadata.

    Un network puede operar en múltiples provincias (relación N:M via network_provinces).
    Ejemplo: Rodalies Catalunya opera en Barcelona, Lleida, Girona, Tarragona.
    """

    __tablename__ = "gtfs_networks"

    code = Column(String(20), primary_key=True)  # Network code (e.g., "10T", "METRO_BILBAO", "TRANVIA_VITORIA")
    name = Column(String(100), nullable=False)  # Network name
    region = Column(String(100), nullable=False)  # Region/community
    color = Column(String(10), nullable=False)  # Primary brand color (hex with #)
    text_color = Column(String(10), nullable=False, default="#FFFFFF")
    logo_url = Column(String(500), nullable=True)
    wikipedia_url = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)

    # Mapeo a nucleo_id de Renfe (para importación GTFS estático)
    # Solo aplica a redes de Cercanías (10T->10, 51T->50, etc.)
    nucleo_id_renfe = Column(Integer, nullable=True)

    # Relación 1:N con rutas
    routes = relationship("RouteModel", back_populates="network")

    def __repr__(self):
        return f"<Network {self.code}: {self.name}>"


from .network_province_model import NetworkProvinceModel

__all__ = ["NetworkModel", "NetworkProvinceModel"]
