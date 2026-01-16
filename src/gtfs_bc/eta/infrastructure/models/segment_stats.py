from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, Index
from core.base import Base


# Day type constants
WEEKDAY = "weekday"
SATURDAY = "saturday"
SUNDAY = "sunday"

# Hour range constants
EARLY_MORNING = "early_morning"  # 05:00 - 07:00
MORNING_PEAK = "morning_peak"    # 07:00 - 09:30
MORNING = "morning"              # 09:30 - 13:00
AFTERNOON = "afternoon"          # 13:00 - 17:00
EVENING_PEAK = "evening_peak"    # 17:00 - 20:00
EVENING = "evening"              # 20:00 - 23:00
NIGHT = "night"                  # 23:00 - 05:00


def get_hour_range(hour: int) -> str:
    """Get the hour range for a given hour."""
    if 5 <= hour < 7:
        return EARLY_MORNING
    elif 7 <= hour < 10:
        return MORNING_PEAK
    elif 10 <= hour < 13:
        return MORNING
    elif 13 <= hour < 17:
        return AFTERNOON
    elif 17 <= hour < 20:
        return EVENING_PEAK
    elif 20 <= hour < 23:
        return EVENING
    else:
        return NIGHT


def get_day_type(weekday: int) -> str:
    """Get the day type for a given weekday (0=Monday, 6=Sunday)."""
    if weekday < 5:
        return WEEKDAY
    elif weekday == 5:
        return SATURDAY
    else:
        return SUNDAY


class SegmentStatsModel(Base):
    """Model for statistical data about track segments.

    Stores aggregated travel time statistics by day type and hour range.
    """
    __tablename__ = "gtfs_segment_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    segment_id = Column(
        String(100),
        ForeignKey("gtfs_track_segments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    day_type = Column(String(20), nullable=False)  # weekday, saturday, sunday
    hour_range = Column(String(20), nullable=False)  # early_morning, morning_peak, etc.
    avg_travel_time_seconds = Column(Float, nullable=False)
    min_travel_time_seconds = Column(Float, nullable=True)
    max_travel_time_seconds = Column(Float, nullable=True)
    std_deviation_seconds = Column(Float, nullable=True)
    sample_count = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_segment_stats_lookup", "segment_id", "day_type", "hour_range"),
    )

    def __repr__(self):
        return f"<SegmentStats {self.segment_id} {self.day_type.value} {self.hour_range.value}>"
