from sqlalchemy import Column, String, Integer
from core.base import Base


class StopCorrespondenceModel(Base):
    """Walking connections between different stations.

    Examples:
    - Acacias (L5) ↔ Embajadores (L3, C5) - underground passage
    - Noviciado (L2) ↔ Plaza de España (L3, L10) - underground passage
    """
    __tablename__ = "stop_correspondence"

    id = Column(Integer, primary_key=True, autoincrement=True)
    from_stop_id = Column(String(100), nullable=False, index=True)
    to_stop_id = Column(String(100), nullable=False, index=True)
    distance_m = Column(Integer, nullable=True)  # Walking distance in meters
    walk_time_s = Column(Integer, nullable=True)  # Estimated walk time in seconds
    source = Column(String(50), nullable=True)  # 'manual', 'gtfs', 'proximity'

    def __repr__(self):
        return f"<StopCorrespondence {self.from_stop_id} → {self.to_stop_id}>"
