from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class ConfidenceLevel(Enum):
    """Confidence level of the ETA estimation."""
    HIGH = "high"      # RT data with reported delay
    MEDIUM = "medium"  # Position-based calculation
    LOW = "low"        # Only scheduled time, no RT data


class CalculationMethod(Enum):
    """Method used to calculate the ETA."""
    SCHEDULED = "scheduled"          # Using only scheduled times
    DELAY_REPORTED = "delay_reported"  # Using TripUpdate delay
    POSITION_BASED = "position_based"  # Calculated from vehicle position
    HISTORICAL = "historical"         # Based on historical patterns


@dataclass
class ETAResult:
    """Result of an ETA calculation for a train arrival at a stop."""
    trip_id: str
    stop_id: str
    scheduled_arrival: datetime
    estimated_arrival: datetime
    delay_seconds: int
    confidence_level: ConfidenceLevel
    calculation_method: CalculationMethod
    calculated_at: datetime
    vehicle_id: Optional[str] = None
    distance_to_stop_meters: Optional[float] = None
    current_stop_id: Optional[str] = None

    @property
    def delay_minutes(self) -> int:
        """Get delay in minutes."""
        return self.delay_seconds // 60

    @property
    def is_delayed(self) -> bool:
        """Check if train is delayed (more than 1 minute)."""
        return self.delay_seconds > 60

    @property
    def is_early(self) -> bool:
        """Check if train is early."""
        return self.delay_seconds < -60

    @property
    def is_on_time(self) -> bool:
        """Check if train is on time (within 1 minute)."""
        return -60 <= self.delay_seconds <= 60
