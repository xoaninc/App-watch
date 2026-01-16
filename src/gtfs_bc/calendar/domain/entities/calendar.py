from dataclasses import dataclass
from datetime import date
from typing import Optional
from enum import IntEnum


class ExceptionType(IntEnum):
    """GTFS Calendar Date exception types."""
    ADDED = 1  # Service added for this date
    REMOVED = 2  # Service removed for this date


@dataclass
class Calendar:
    """GTFS Calendar entity - represents service availability by day."""

    service_id: str
    monday: bool
    tuesday: bool
    wednesday: bool
    thursday: bool
    friday: bool
    saturday: bool
    sunday: bool
    start_date: date
    end_date: date

    @classmethod
    def from_gtfs(cls, row: dict) -> "Calendar":
        """Create Calendar from GTFS CSV row."""
        return cls(
            service_id=row.get("service_id", ""),
            monday=row.get("monday", "0") == "1",
            tuesday=row.get("tuesday", "0") == "1",
            wednesday=row.get("wednesday", "0") == "1",
            thursday=row.get("thursday", "0") == "1",
            friday=row.get("friday", "0") == "1",
            saturday=row.get("saturday", "0") == "1",
            sunday=row.get("sunday", "0") == "1",
            start_date=cls._parse_date(row.get("start_date", "")),
            end_date=cls._parse_date(row.get("end_date", "")),
        )

    @staticmethod
    def _parse_date(date_str: str) -> date:
        """Parse YYYYMMDD date string."""
        if not date_str:
            return date.today()
        return date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))

    def operates_on(self, day: date) -> bool:
        """Check if service operates on a given day."""
        if day < self.start_date or day > self.end_date:
            return False
        weekday = day.weekday()
        days = [self.monday, self.tuesday, self.wednesday, self.thursday,
                self.friday, self.saturday, self.sunday]
        return days[weekday]


@dataclass
class CalendarDate:
    """GTFS CalendarDate entity - represents service exceptions."""

    service_id: str
    date: date
    exception_type: ExceptionType

    @classmethod
    def from_gtfs(cls, row: dict) -> "CalendarDate":
        """Create CalendarDate from GTFS CSV row."""
        date_str = row.get("date", "")
        return cls(
            service_id=row.get("service_id", ""),
            date=date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8])) if date_str else date.today(),
            exception_type=ExceptionType(int(row.get("exception_type", 1))),
        )
