"""Realtime-related response schemas."""

import json
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, field_validator


class PositionSchema(BaseModel):
    latitude: float
    longitude: float


class VehiclePositionResponse(BaseModel):
    vehicle_id: str
    trip_id: str
    position: PositionSchema
    current_status: str
    stop_id: Optional[str]
    label: Optional[str]
    timestamp: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class TripUpdateResponse(BaseModel):
    trip_id: str
    delay: int
    delay_minutes: int
    is_delayed: bool
    vehicle_id: Optional[str]
    wheelchair_accessible: Optional[bool]
    timestamp: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class StopDelayResponse(BaseModel):
    trip_id: str
    stop_id: str
    arrival_delay: Optional[int]
    arrival_time: Optional[datetime]
    departure_delay: Optional[int]
    departure_time: Optional[datetime]


class AlertEntityResponse(BaseModel):
    route_id: Optional[str]
    route_short_name: Optional[str]
    stop_id: Optional[str]
    trip_id: Optional[str]
    agency_id: Optional[str]
    route_type: Optional[int]


class AlertResponse(BaseModel):
    alert_id: str
    cause: str
    effect: str
    header_text: str
    description_text: Optional[str]
    url: Optional[str]
    active_period_start: Optional[datetime]
    active_period_end: Optional[datetime]
    is_active: bool
    informed_entities: List[AlertEntityResponse]
    timestamp: datetime
    updated_at: Optional[datetime]
    # AI enrichment fields
    ai_severity: Optional[str] = None  # INFO, WARNING, CRITICAL
    ai_status: Optional[str] = None  # NORMAL, DELAYS, PARTIAL_SUSPENSION, FULL_SUSPENSION, FACILITY_ISSUE
    ai_summary: Optional[str] = None  # AI-generated summary
    ai_affected_segments: Optional[List[str]] = None  # Extracted stop names
    ai_processed_at: Optional[datetime] = None

    @field_validator('ai_affected_segments', mode='before')
    @classmethod
    def parse_segments(cls, v):
        """Parse JSON string to list if needed."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except:
                return None
        return v

    class Config:
        from_attributes = True


class FetchResponse(BaseModel):
    vehicle_positions: int
    trip_updates: int
    alerts: int
    message: str


class EstimatedPositionResponse(BaseModel):
    """Estimated vehicle position based on schedule."""
    trip_id: str
    route_id: str
    route_short_name: str
    route_color: str
    headsign: Optional[str]
    position: PositionSchema
    current_status: str
    current_stop_id: str
    current_stop_name: str
    next_stop_id: Optional[str]
    next_stop_name: Optional[str]
    progress_percent: float
    estimated: bool = True


class SchedulerStatusResponse(BaseModel):
    running: bool
    last_fetch: Optional[str]
    fetch_count: int
    error_count: int
    interval_seconds: int


class FrequencyPeriodResponse(BaseModel):
    start_time: str  # HH:MM format
    end_time: str    # HH:MM format
    headway_minutes: int
    headway_secs: int


class RealtimeRouteFrequencyResponse(BaseModel):
    """Route frequency response for realtime endpoints."""
    route_id: str
    route_short_name: str
    route_long_name: str
    route_color: Optional[str]
    day_type: str
    periods: List[FrequencyPeriodResponse]


class CurrentFrequencyResponse(BaseModel):
    route_id: str
    route_short_name: str
    route_color: Optional[str]
    day_type: str
    current_headway_minutes: int
    current_period: str  # e.g., "07:00-10:00"
    message: str  # e.g., "Un tren cada 5 minutos"


class CreateAlertRequest(BaseModel):
    header_text: str
    description_text: Optional[str] = None
    cause: str = "OTHER_CAUSE"
    effect: str = "OTHER_EFFECT"
    route_ids: Optional[List[str]] = None
    stop_ids: Optional[List[str]] = None
    active_period_start: Optional[datetime] = None
    active_period_end: Optional[datetime] = None
    url: Optional[str] = None


class CreateAlertResponse(BaseModel):
    alert_id: str
    message: str
