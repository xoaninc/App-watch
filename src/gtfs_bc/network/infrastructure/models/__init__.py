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

    @property
    def transport_type(self) -> str:
        """Infer transport type from network code.

        Returns: 'cercanias', 'metro', 'metro_ligero', 'tranvia', 'fgc', 'euskotren', 'other'
        """
        code_upper = self.code.upper()

        # Metro (check before cercanías since 11T ends with T)
        if code_upper.startswith('METRO_') or code_upper == '11T' or code_upper == 'TMB_METRO':
            return 'metro'

        # Metro Ligero (check before cercanías since 12T ends with T)
        if code_upper == '12T' or code_upper.startswith('ML_'):
            return 'metro_ligero'

        # Cercanías: codes ending with T (10T, 40T, 51T) but not 11T or 12T
        if code_upper.endswith('T') and code_upper[:-1].isdigit():
            return 'cercanias'

        # Tranvía
        if code_upper.startswith('TRANVIA_') or code_upper.startswith('TRAM_'):
            return 'tranvia'

        # FGC
        if code_upper == 'FGC':
            return 'fgc'

        # Euskotren
        if code_upper == 'EUSKOTREN':
            return 'euskotren'

        return 'other'

    def __repr__(self):
        return f"<Network {self.code}: {self.name}>"


from .network_province_model import NetworkProvinceModel

__all__ = ["NetworkModel", "NetworkProvinceModel"]
