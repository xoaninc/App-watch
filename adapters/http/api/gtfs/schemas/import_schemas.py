from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ImportRequest(BaseModel):
    """Request to import GTFS feed."""
    url: Optional[str] = None  # If None, uses default Renfe Cercanías URL


class ImportResponse(BaseModel):
    """Response after starting import."""
    id: str
    status: str
    message: str


class ImportStatusResponse(BaseModel):
    """Full status of an import."""
    id: str
    source_url: str
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    agencies_count: int = 0
    routes_count: int = 0
    stops_count: int = 0
    trips_count: int = 0
    stop_times_count: int = 0
