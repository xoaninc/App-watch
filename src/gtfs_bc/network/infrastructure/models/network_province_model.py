from sqlalchemy import Column, String, ForeignKey
from core.base import Base


class NetworkProvinceModel(Base):
    """SQLAlchemy model for network-province relationship (N:M).

    Links networks to the provinces where they operate.
    Example: Rodalies (51T) operates in BAR, LLE, GIR, TAR provinces.
    """

    __tablename__ = "network_provinces"

    network_id = Column(
        String(20),
        ForeignKey('gtfs_networks.code', ondelete='CASCADE'),
        primary_key=True
    )
    province_code = Column(
        String(5),
        ForeignKey('spanish_provinces.code', ondelete='CASCADE'),
        primary_key=True
    )

    def __repr__(self):
        return f"<NetworkProvince {self.network_id} -> {self.province_code}>"
