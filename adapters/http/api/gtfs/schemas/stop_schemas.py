"""Stop-related response schemas."""

from typing import Optional, List
from pydantic import BaseModel


class StopResponse(BaseModel):
    id: str
    name: str
    lat: float
    lon: float
    code: Optional[str]
    location_type: int
    parent_station_id: Optional[str]
    zone_id: Optional[str]
    province: Optional[str]
    lineas: Optional[str]
    parking_bicis: Optional[str]
    accesibilidad: Optional[str]
    cor_bus: Optional[str]
    cor_metro: Optional[str]
    cor_ml: Optional[str]
    cor_cercanias: Optional[str]
    cor_tranvia: Optional[str]
    is_hub: bool = False  # True if station has 2+ different transport types

    class Config:
        from_attributes = True


class RouteStopResponse(BaseModel):
    """Stop response with route sequence information."""
    id: str
    name: str
    lat: float
    lon: float
    code: Optional[str]
    location_type: int
    parent_station_id: Optional[str]
    zone_id: Optional[str]
    province: Optional[str]
    lineas: Optional[str]
    parking_bicis: Optional[str]
    accesibilidad: Optional[str]
    cor_bus: Optional[str]
    cor_metro: Optional[str]
    cor_ml: Optional[str]
    cor_cercanias: Optional[str]
    cor_tranvia: Optional[str]
    is_hub: bool = False
    stop_sequence: int  # Position in the route (1-based)

    class Config:
        from_attributes = True


class PlatformResponse(BaseModel):
    """Platform coordinates for one or more lines at a stop."""
    id: int
    stop_id: str
    lines: str  # Single line "L6" or multiple "C2, C3, C4a, C4b"
    lat: float
    lon: float
    source: Optional[str]
    color: Optional[str] = None
    description: Optional[str] = None

    class Config:
        from_attributes = True


class StopPlatformsResponse(BaseModel):
    """All platforms at a stop with their coordinates."""
    stop_id: str
    stop_name: str
    platforms: List[PlatformResponse]


class WalkingShapePoint(BaseModel):
    """A point in a walking route shape."""
    lat: float
    lon: float


class CorrespondenceResponse(BaseModel):
    """Walking connection to another station."""
    id: int
    to_stop_id: str
    to_stop_name: str
    to_lines: Optional[str]
    to_transport_types: List[str]  # metro, cercanias, metro_ligero, tranvia
    distance_m: Optional[int]
    walk_time_s: Optional[int]
    source: Optional[str]
    walking_shape: Optional[List[WalkingShapePoint]] = None  # Pedestrian route coordinates

    class Config:
        from_attributes = True


class StopCorrespondencesResponse(BaseModel):
    """Walking correspondences from a stop to nearby stations."""
    stop_id: str
    stop_name: str
    correspondences: List[CorrespondenceResponse]


class AccessResponse(BaseModel):
    """Station access point (entrance/exit) with street-level location."""
    id: int
    stop_id: str
    name: str
    lat: float
    lon: float
    street: Optional[str] = None
    street_number: Optional[str] = None
    opening_time: Optional[str] = None
    closing_time: Optional[str] = None
    wheelchair: Optional[bool] = None
    level: Optional[int] = None
    source: Optional[str] = None

    class Config:
        from_attributes = True


class StopAccessesResponse(BaseModel):
    """All access points (entrances) at a stop."""
    stop_id: str
    stop_name: str
    accesses: List[AccessResponse]


class NearbyAccessResponse(BaseModel):
    """Access point with distance and RAPTOR routing ID."""
    id: int
    raptor_id: str  # ACCESS_{id} for use in route-planner
    stop_id: str  # Platform stop ID
    stop_name: str  # Platform name
    name: str  # Access name
    lat: float
    lon: float
    distance_m: int  # Distance from search point
    wheelchair: Optional[bool] = None
    is_elevator: bool = False

    class Config:
        from_attributes = True


class VestibuleResponse(BaseModel):
    """Station vestibule (internal lobby) with underground location."""
    id: int
    stop_id: str
    name: str
    lat: float
    lon: float
    level: Optional[int] = None
    vestibule_type: Optional[str] = None
    turnstile_type: Optional[str] = None
    opening_time: Optional[str] = None
    closing_time: Optional[str] = None
    wheelchair: Optional[bool] = None
    source: Optional[str] = None

    class Config:
        from_attributes = True


class StopVestibulesResponse(BaseModel):
    """All vestibules (internal lobbies) at a stop."""
    stop_id: str
    stop_name: str
    vestibules: List[VestibuleResponse]
