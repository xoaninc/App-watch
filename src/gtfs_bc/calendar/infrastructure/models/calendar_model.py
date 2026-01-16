from sqlalchemy import Column, String, Boolean, Date, Integer, ForeignKey, Index
from core.base import Base


class CalendarModel(Base):
    """SQLAlchemy model for GTFS Calendar."""

    __tablename__ = "gtfs_calendar"

    service_id = Column(String(100), primary_key=True)
    monday = Column(Boolean, nullable=False, default=False)
    tuesday = Column(Boolean, nullable=False, default=False)
    wednesday = Column(Boolean, nullable=False, default=False)
    thursday = Column(Boolean, nullable=False, default=False)
    friday = Column(Boolean, nullable=False, default=False)
    saturday = Column(Boolean, nullable=False, default=False)
    sunday = Column(Boolean, nullable=False, default=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)


class CalendarDateModel(Base):
    """SQLAlchemy model for GTFS CalendarDate (exceptions)."""

    __tablename__ = "gtfs_calendar_dates"

    # Composite primary key
    service_id = Column(String(100), ForeignKey("gtfs_calendar.service_id"), primary_key=True)
    date = Column(Date, primary_key=True)

    exception_type = Column(Integer, nullable=False)  # 1 = added, 2 = removed

    __table_args__ = (
        Index("ix_calendar_dates_date", "date"),
    )
