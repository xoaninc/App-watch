from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.sql import func
from core.base import Base


class LocalHolidayModel(Base):
    """SQLAlchemy model for local (city-specific) holidays.

    These are holidays that apply to specific cities within a province,
    such as San Isidro (Madrid), La Merce (Barcelona), etc.

    Note: FK to spanish_provinces.code is defined at DB level (migration 041),
    not in SQLAlchemy model since spanish_provinces has no ORM model.
    """

    __tablename__ = "local_holidays"

    id = Column(Integer, primary_key=True, autoincrement=True)
    province_code = Column(String(5), nullable=False, index=True)
    city = Column(String(100), nullable=False)
    name = Column(String(100), nullable=False)
    month = Column(Integer, nullable=False)
    day = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<LocalHoliday {self.city}: {self.name} ({self.day}/{self.month})>"
