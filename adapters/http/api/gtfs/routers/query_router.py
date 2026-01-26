from typing import List, Optional
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
import math
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

MADRID_TZ = ZoneInfo("Europe/Madrid")


def get_spanish_holidays(year: int) -> set:
    """Get Spanish national and Madrid regional holidays for a given year.

    Returns a set of date objects for holidays.
    """
    holidays = set()

    # National holidays (fiestas nacionales)
    holidays.add(date(year, 1, 1))    # Año Nuevo
    holidays.add(date(year, 1, 6))    # Epifanía del Señor (Reyes)
    holidays.add(date(year, 5, 1))    # Día del Trabajador
    holidays.add(date(year, 8, 15))   # Asunción de la Virgen
    holidays.add(date(year, 10, 12))  # Fiesta Nacional de España
    holidays.add(date(year, 11, 1))   # Todos los Santos
    holidays.add(date(year, 12, 6))   # Día de la Constitución
    holidays.add(date(year, 12, 8))   # Inmaculada Concepción
    holidays.add(date(year, 12, 25))  # Navidad

    # Madrid regional holidays
    holidays.add(date(year, 5, 2))    # Día de la Comunidad de Madrid
    holidays.add(date(year, 5, 15))   # San Isidro (Madrid capital)
    holidays.add(date(year, 11, 9))   # Almudena (Madrid capital)

    # Easter (variable dates) - approximate calculation
    # Using Anonymous Gregorian algorithm
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    easter_sunday = date(year, month, day)

    # Jueves Santo (Thursday before Easter)
    holidays.add(easter_sunday - timedelta(days=3))
    # Viernes Santo (Friday before Easter)
    holidays.add(easter_sunday - timedelta(days=2))

    return holidays


def is_holiday(check_date: date) -> bool:
    """Check if a date is a holiday."""
    holidays = get_spanish_holidays(check_date.year)
    return check_date in holidays


def is_pre_holiday(check_date: date) -> bool:
    """Check if a date is a pre-holiday (víspera de festivo).

    A pre-holiday is the day before a holiday, when extended
    (friday/saturday) schedules typically apply.
    """
    tomorrow = check_date + timedelta(days=1)
    return is_holiday(tomorrow)


def get_effective_day_type(now: datetime) -> str:
    """Determine the effective day type considering holidays and pre-holidays.

    Returns: 'weekday', 'friday', 'saturday', or 'sunday'

    Logic:
    - Sunday or holiday -> 'sunday'
    - Saturday -> 'saturday'
    - Friday or pre-holiday (víspera) -> 'friday' (extended hours)
    - Monday-Thursday -> 'weekday'
    """
    current_date = now.date()
    weekday = now.weekday()  # 0=Monday, 6=Sunday

    # Check if today is a holiday -> use sunday schedule
    if is_holiday(current_date):
        return "sunday"

    # Sunday
    if weekday == 6:
        return "sunday"

    # Saturday
    if weekday == 5:
        return "saturday"

    # Friday or pre-holiday (víspera) -> extended hours
    if weekday == 4 or is_pre_holiday(current_date):
        return "friday"

    # Monday-Thursday
    return "weekday"


# Prefixes for networks with real GTFS-RT data (don't filter by operating hours)
GTFS_RT_PREFIXES = (
    "RENFE_",        # Cercanías RENFE
    "TMB_METRO_",    # Metro Barcelona
    "FGC_",          # FGC
    "EUSKOTREN_",    # Euskotren
    "METRO_BILBAO_", # Metro Bilbao
)

def is_static_gtfs_route(route_id: str) -> bool:
    """Check if a route uses static GTFS (no real-time data).

    Routes with GTFS-RT don't need operating hours filtering since
    real-time data already reflects actual service.
    """
    return not any(route_id.startswith(prefix) for prefix in GTFS_RT_PREFIXES)


def is_route_operating(db, route_id: str, current_seconds: int, day_type: str) -> bool:
    """Check if a route is currently operating based on its frequency schedule.

    Returns True if current time is within operating hours, False otherwise.
    For routes without frequency data, returns True (assume always operating).
    """
    # Get frequencies for this route and day type
    frequencies = db.query(RouteFrequencyModel).filter(
        RouteFrequencyModel.route_id == route_id,
        RouteFrequencyModel.day_type == day_type
    ).all()

    if not frequencies:
        # No frequency data - assume always operating (or use stop_times)
        return True

    def parse_time_to_seconds(time_val) -> int:
        """Parse time (TIME or VARCHAR like '25:30:00') to seconds."""
        if hasattr(time_val, 'hour'):
            # It's a time object
            return time_val.hour * 3600 + time_val.minute * 60 + time_val.second
        else:
            # It's a string like "25:30:00"
            parts = str(time_val).split(':')
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])

    # First pass: find max_end from ALL entries (including aggregates)
    # This gives us the actual closing time (e.g., 25:30:00 = 01:30 AM)
    max_end = None
    for freq in frequencies:
        end_secs = parse_time_to_seconds(freq.end_time)
        if max_end is None or end_secs > max_end:
            max_end = end_secs

    # Second pass: find min_start from NON-aggregate entries only
    # Aggregates have start=00:00:00 AND end>=25:00:00 - they represent full day summary
    min_start = None
    for freq in frequencies:
        start_secs = parse_time_to_seconds(freq.start_time)
        end_secs = parse_time_to_seconds(freq.end_time)

        # Skip aggregates (00:00:00 to 25:00:00+) for min_start calculation
        is_aggregate = start_secs == 0 and end_secs >= 25 * 3600
        if is_aggregate:
            continue

        if min_start is None or start_secs < min_start:
            min_start = start_secs

    # If no valid min_start found (only aggregates), use default opening time
    # Metro typically opens around 6:00-6:05 AM
    if min_start is None:
        min_start = 6 * 3600  # Default to 6:00 AM (21600 seconds)

    if max_end is None:
        return True  # No valid data

    # Check if current time is within operating hours
    # Handle overnight (max_end > 24h means service extends past midnight)
    if max_end > 24 * 3600:
        # Service runs past midnight (e.g., until 01:30 = 25:30:00)
        # Operating if: current >= min_start OR current <= (max_end - 24h)
        late_night_cutoff = max_end - 24 * 3600  # e.g., 5400 for 01:30 AM
        if current_seconds >= min_start or current_seconds <= late_night_cutoff:
            return True
    else:
        # Normal hours
        if min_start <= current_seconds <= max_end:
            return True

    return False


from core.database import get_db
from src.gtfs_bc.route.infrastructure.models import RouteModel, RouteFrequencyModel
from src.gtfs_bc.stop.infrastructure.models import StopModel
from src.gtfs_bc.trip.infrastructure.models import TripModel
from src.gtfs_bc.stop_time.infrastructure.models import StopTimeModel
from src.gtfs_bc.calendar.infrastructure.models import CalendarModel, CalendarDateModel
from src.gtfs_bc.agency.infrastructure.models import AgencyModel
from src.gtfs_bc.network.infrastructure.models import NetworkModel
from src.gtfs_bc.realtime.infrastructure.models import TripUpdateModel, StopTimeUpdateModel, VehiclePositionModel, PlatformHistoryModel
from src.gtfs_bc.province.province_lookup import (
    get_province_by_coordinates,
    get_province_and_networks_by_coordinates,
)
from src.gtfs_bc.realtime.infrastructure.services.estimated_positions import EstimatedPositionsService
from src.gtfs_bc.realtime.infrastructure.services.gtfs_rt_fetcher import GTFSRealtimeFetcher
from src.gtfs_bc.stop_route_sequence.infrastructure.models import StopRouteSequenceModel
from src.gtfs_bc.transfer.infrastructure.models import LineTransferModel


router = APIRouter(prefix="/gtfs", tags=["GTFS Query"])


# Response schemas
class RouteResponse(BaseModel):
    id: str
    short_name: str
    long_name: str
    route_type: int
    color: Optional[str]
    text_color: Optional[str]
    agency_id: str
    network_id: Optional[str]
    description: Optional[str] = None

    class Config:
        from_attributes = True


class RouteFrequencyResponse(BaseModel):
    """Frequency data for a route (Metro, ML, Tranvía)."""
    trip_id: Optional[str] = None  # Optional - not always available
    route_id: Optional[str] = None  # Optional for compatibility
    day_type: str  # 'weekday', 'saturday', 'sunday'
    start_time: str  # HH:MM:SS format
    end_time: str  # HH:MM:SS format
    headway_secs: int  # Interval between trains in seconds
    headway_minutes: Optional[float] = None  # Interval in minutes (for convenience)

    class Config:
        from_attributes = True


class DayOperatingHours(BaseModel):
    """Operating hours for a single day type."""
    first_departure: Optional[str]  # HH:MM:SS format
    last_departure: Optional[str]  # HH:MM:SS format
    total_trips: int


class RouteOperatingHoursResponse(BaseModel):
    """Operating hours for a route (derived from stop_times for Cercanías)."""
    route_id: str
    route_short_name: str
    weekday: Optional[DayOperatingHours]  # Monday-Thursday
    friday: Optional[DayOperatingHours]   # Friday (extended hours)
    saturday: Optional[DayOperatingHours]
    sunday: Optional[DayOperatingHours]
    is_suspended: bool = False  # True if service is suspended (from alerts)
    suspension_message: Optional[str] = None  # Alert message if suspended


import re as regex_module


def _has_real_cercanias(cor_cercanias: Optional[str]) -> bool:
    """Check if cor_cercanias contains real Cercanías lines (C* or R* patterns).

    Filters out Euskotren lines (E1, E2, TR) which may appear in cor_cercanias
    but are not actually Renfe Cercanías.

    Args:
        cor_cercanias: Comma-separated list of Cercanías lines (e.g., "C1, C3, R2")

    Returns:
        True if any line matches C* or R* pattern (Cercanías/Rodalies Renfe)
    """
    if not cor_cercanias:
        return False
    lines = [line.strip() for line in cor_cercanias.split(',')]
    for line in lines:
        # Match C1, C2, R1, R2, etc. (Renfe Cercanías/Rodalies)
        if regex_module.match(r'^[CR]\d', line):
            return True
    return False


def _calculate_is_hub(stop: StopModel) -> bool:
    """Calculate if a stop is a transport hub.

    A hub is a station with 2 or more DIFFERENT transport types:
    - Metro (cor_metro)
    - Cercanías/Rodalies (cor_cercanias with C*/R* lines only)
    - Metro Ligero (cor_ml)
    - Tranvía (cor_tranvia)

    Note: Multiple lines of the same type don't make a hub.
    """
    transport_count = 0

    if stop.cor_metro:
        transport_count += 1

    if _has_real_cercanias(stop.cor_cercanias):
        transport_count += 1

    if stop.cor_ml:
        transport_count += 1

    if stop.cor_tranvia:
        transport_count += 1

    return transport_count >= 2


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
    is_hub: bool = False  # True if station has 2+ different transport types
    stop_sequence: int  # Position in the route (1-based)

    class Config:
        from_attributes = True


class TrainPositionSchema(BaseModel):
    """Current position of the train."""
    latitude: float
    longitude: float
    current_stop_name: str
    status: str  # STOPPED_AT, IN_TRANSIT_TO, INCOMING_AT
    progress_percent: float
    estimated: bool = True  # True if calculated from schedule, False if from GTFS-RT


class DepartureResponse(BaseModel):
    trip_id: str
    route_id: str
    route_short_name: str
    route_color: Optional[str]
    headsign: Optional[str]
    departure_time: str
    departure_seconds: int
    minutes_until: int
    stop_sequence: int
    # Platform/track info (from GTFS-RT when available, or estimated from history)
    platform: Optional[str] = None
    platform_estimated: bool = False  # True if platform is estimated from history
    # Realtime delay fields
    delay_seconds: Optional[int] = None
    realtime_departure_time: Optional[str] = None
    realtime_minutes_until: Optional[int] = None
    is_delayed: bool = False
    # Train position (from GTFS-RT or estimated)
    train_position: Optional[TrainPositionSchema] = None
    # Frequency-based estimation (for Metro/ML without GTFS-RT)
    frequency_based: bool = False  # True if departure is estimated from frequency data
    headway_secs: Optional[int] = None  # Frequency headway in seconds (e.g., 300 = every 5 min)


class TripStopResponse(BaseModel):
    stop_id: str
    stop_name: str
    arrival_time: str
    departure_time: str
    stop_sequence: int
    stop_lat: float
    stop_lon: float


class TripDetailResponse(BaseModel):
    id: str
    route_id: str
    route_short_name: str
    route_long_name: str
    route_color: Optional[str]
    headsign: Optional[str]
    direction_id: Optional[int]
    stops: List[TripStopResponse]


class AgencyResponse(BaseModel):
    id: str
    name: str
    url: Optional[str]
    timezone: str
    lang: Optional[str]
    phone: Optional[str]

    class Config:
        from_attributes = True


class TransferResponse(BaseModel):
    """Transfer/interchange information between stops or lines."""
    id: int
    from_stop_id: str
    to_stop_id: str
    from_route_id: Optional[str]
    to_route_id: Optional[str]
    transfer_type: int  # 0=recommended, 1=timed, 2=min time required, 3=not possible
    min_transfer_time: Optional[int]  # seconds
    from_stop_name: Optional[str]
    to_stop_name: Optional[str]
    from_line: Optional[str]
    to_line: Optional[str]
    network_id: Optional[str]
    instructions: Optional[str]
    exit_name: Optional[str]
    source: Optional[str]

    class Config:
        from_attributes = True


@router.get("/agencies", response_model=List[AgencyResponse])
def get_agencies(db: Session = Depends(get_db)):
    """Get all agencies."""
    agencies = db.query(AgencyModel).all()
    return agencies


@router.get("/routes", response_model=List[RouteResponse])
def get_routes(
    agency_id: Optional[str] = Query(None, description="Filter by agency ID"),
    network_id: Optional[str] = Query(None, description="Filter by network ID"),
    search: Optional[str] = Query(None, description="Search by name"),
    db: Session = Depends(get_db),
):
    """Get all routes/lines.

    Optionally filter by agency, network, or search by name.

    Filtering logic for routes with variants:
    - CERCANÍAS (C4, C4a, C4b): Base routes (C4) are hidden, only variants shown (C4a, C4b)
      because C4/C8 don't exist as real services - only C4a/C4b and C8a/C8b do.
    - METRO (L7, L7B): Both are returned because they are INDEPENDENT services
      with different terminals and transfer required between them.

    See: scripts/GTFS_IMPORT_CHANGES.md for full documentation.
    """
    query = db.query(RouteModel)

    if agency_id:
        query = query.filter(RouteModel.agency_id == agency_id)

    if network_id:
        query = query.filter(RouteModel.network_id == network_id)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                RouteModel.short_name.ilike(search_term),
                RouteModel.long_name.ilike(search_term),
            )
        )

    routes = query.order_by(RouteModel.short_name).all()

    # Filter out base routes that have variants (ONLY for Cercanías, not Metro)
    # e.g., if C4A and C4B exist, exclude C4
    # But L7 and L7B in Metro are independent lines - don't filter them
    filtered_routes = []
    base_routes_with_variants = set()

    # Normalize route names for comparison (strip whitespace)
    routes_by_name = {}
    routes_by_id = {}
    for route in routes:
        short_name = route.short_name.strip() if route.short_name else ""
        if short_name:
            routes_by_name[short_name] = route
            routes_by_id[route.id] = route

    # First pass: identify base routes that have variants (Cercanías only)
    for short_name, route in routes_by_name.items():
        # Only apply this logic to Cercanías (routes starting with C)
        # Metro lines (L7, L7B) are independent and should NOT be filtered
        if not short_name.upper().startswith('C'):
            continue
        # Check if this is a variant (ends with a single letter A-Z)
        if short_name and short_name[-1].isalpha() and len(short_name) > 1:
            # Extract base name (e.g., "C4" from "C4A")
            base_name = short_name[:-1]
            # Check if base route exists (case-insensitive)
            if any(name.lower() == base_name.lower() for name in routes_by_name.keys()):
                base_routes_with_variants.add(base_name.lower())

    # Second pass: include routes, excluding base routes with variants
    for route in routes:
        short_name = route.short_name.strip() if route.short_name else ""
        if short_name.lower() not in base_routes_with_variants:
            filtered_routes.append(route)

    return filtered_routes


@router.get("/coordinates/routes", response_model=List[RouteResponse])
def get_routes_by_coordinates(
    lat: float = Query(..., ge=-90, le=90, description="Latitude (e.g., 40.42 for Madrid)"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude (e.g., -3.72 for Madrid)"),
    limit: int = Query(600, ge=1, le=1000, description="Maximum results"),
    db: Session = Depends(get_db),
):
    """Get all routes/lines from the núcleo determined by the given coordinates.

    The endpoint automatically calculates which province the coordinates belong to,
    then maps it to the corresponding Renfe regional network (núcleo),
    and returns all routes in that núcleo.

    Flow:
    1. Coordinates → Find Province (PostGIS)
    2. Province → Find Nucleo (province mapping)
    3. Nucleo → Return Routes

    If coordinates are outside Spain or in a province without Renfe service,
    returns empty list (no error).

    For Madrid example: lat=40.42&lon=-3.72
    """
    # Step 1: Determine province and networks from coordinates
    result = get_province_and_networks_by_coordinates(db, lat, lon)

    if not result:
        # Coordinates are outside Spain - return empty list
        return []

    networks = result.get('networks', [])

    # Step 2: If no networks, province has no transit service - return empty list
    if not networks:
        return []

    # Step 3: Get all routes in the determined networks
    network_codes = [n['code'] for n in networks]
    routes = (
        db.query(RouteModel)
        .filter(RouteModel.network_id.in_(network_codes))
        .order_by(RouteModel.short_name)
        .limit(limit)
        .all()
    )

    # Step 4: Filter out generic C4/C8 routes when variants exist
    # Madrid C4 splits into C4a (Alcobendas) and C4b (Colmenar Viejo)
    # Madrid C8 splits into C8a (El Escorial) and C8b (Cercedilla)
    short_names = {r.short_name for r in routes}
    routes_to_exclude = set()

    # If C4a or C4b exist, exclude generic C4
    if 'C4a' in short_names or 'C4b' in short_names:
        routes_to_exclude.add('C4')

    # If C8a or C8b exist, exclude generic C8
    if 'C8a' in short_names or 'C8b' in short_names:
        routes_to_exclude.add('C8')

    if routes_to_exclude:
        routes = [r for r in routes if r.short_name not in routes_to_exclude]

    return routes


@router.get("/routes/{route_id}", response_model=RouteResponse)
def get_route(route_id: str, db: Session = Depends(get_db)):
    """Get a specific route by ID.

    Note: This endpoint requires a specific route_id and won't match /routes/by-coordinates
    """
    if route_id == "by-coordinates":
        raise HTTPException(status_code=400, detail="Use /routes/by-coordinates endpoint with lat/lon parameters")

    route = db.query(RouteModel).filter(RouteModel.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail=f"Route {route_id} not found")
    return route


@router.get("/stops", response_model=List[StopResponse])
def get_stops(
    search: Optional[str] = Query(None, description="Search by name"),
    network_id: Optional[str] = Query(None, description="Filter by network ID (e.g., 51T, TMB_METRO)"),
    location_type: Optional[int] = Query(None, description="Filter by location type (0=stop, 1=station)"),
    parent_station: Optional[str] = Query(None, description="Filter by parent station ID"),
    limit: int = Query(600, ge=1, le=1000, description="Maximum results"),
    db: Session = Depends(get_db),
):
    """Get all stops/stations.

    Optionally filter by name search, network, location type, or parent station.
    """
    query = db.query(StopModel)

    if search:
        search_term = f"%{search}%"
        query = query.filter(StopModel.name.ilike(search_term))

    if network_id:
        # Filter stops by ID prefix based on network
        prefix_map = {
            'TMB_METRO': 'TMB_METRO_%',
            'FGC': 'FGC_%',
            '11T': 'METRO_%',
            '12T': 'ML_%',
            '51T': 'RENFE_%',  # Rodalies Catalunya
            '10T': 'RENFE_%',  # Cercanías Madrid
        }
        if network_id in prefix_map:
            query = query.filter(StopModel.id.like(prefix_map[network_id]))

    if location_type is not None:
        query = query.filter(StopModel.location_type == location_type)

    if parent_station:
        query = query.filter(StopModel.parent_station_id == parent_station)

    stops = query.order_by(StopModel.name).limit(limit).all()
    return stops


@router.get("/stops/by-network", response_model=List[StopResponse])
def get_stops_by_network(
    network_id: str = Query(..., description="Network ID (e.g., 51T, TMB_METRO, FGC)"),
    limit: int = Query(600, ge=1, le=1000, description="Maximum results"),
    db: Session = Depends(get_db),
):
    """Get all stops in a specific network.

    Returns parent stations (location_type=1) or stops without a parent.
    This avoids returning multiple platforms for the same station.
    """
    query = db.query(StopModel)

    # Map network_id to stop ID prefix
    prefix_map = {
        'TMB_METRO': 'TMB_METRO_%',
        'FGC': 'FGC_%',
        'EUSKOTREN': 'EUSKOTREN_%',
        'METRO_BILBAO': 'METRO_BILBAO_%',
        '11T': 'METRO_%',
        '12T': 'ML_%',
    }

    # For Renfe networks, use RENFE_ prefix
    if network_id.endswith('T') and network_id not in prefix_map:
        prefix = 'RENFE_%'
    else:
        prefix = prefix_map.get(network_id, f'{network_id}_%')

    query = query.filter(StopModel.id.like(prefix))

    # Only return parent stations (location_type=1) or stops without a parent
    # This groups platforms under their parent station
    # Exclude bus stops and entrances
    query = query.filter(
        or_(
            StopModel.location_type == 1,  # Parent stations
            and_(
                StopModel.parent_station_id.is_(None),  # Stops without parent
                ~StopModel.id.like('%_2.%'),  # Exclude bus stops
                ~StopModel.id.like('%_E.%'),  # Exclude entrances
            )
        )
    )

    stops = query.order_by(StopModel.name).limit(limit).all()

    if not stops:
        raise HTTPException(
            status_code=404,
            detail=f"No stops found for network {network_id}"
        )

    return stops


@router.get("/stops/by-coordinates", response_model=List[StopResponse])
def get_stops_by_coordinates(
    lat: float = Query(..., ge=-90, le=90, description="Latitude (e.g., 40.42 for Madrid)"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude (e.g., -3.72 for Madrid)"),
    radius_km: float = Query(50, ge=1, le=200, description="Search radius in kilometers"),
    transport_type: Optional[str] = Query(
        None,
        description="Filter by transport type: metro, cercanias, fgc, tram, all. Default returns only stops with GTFS-RT."
    ),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    db: Session = Depends(get_db),
):
    """Get transit stops near the given coordinates, ordered by distance.

    By default, only returns stops that have GTFS-RT real-time data available:
    - Metro (TMB, Madrid, Bilbao, etc.)
    - Cercanías/Rodalies (RENFE)
    - FGC
    - Tram
    - Euskotren

    Use transport_type=all to include all stops (including bus stops without real-time).

    For Barcelona example: lat=41.3851&lon=2.1734
    For Madrid example: lat=40.42&lon=-3.72
    """
    # Calculate distance using Haversine formula (in meters)
    lat_rad = func.radians(lat)
    lon_rad = func.radians(lon)
    stop_lat_rad = func.radians(StopModel.lat)
    stop_lon_rad = func.radians(StopModel.lon)

    # Haversine formula components
    dlat = stop_lat_rad - lat_rad
    dlon = stop_lon_rad - lon_rad

    a = func.power(func.sin(dlat / 2), 2) + \
        func.cos(lat_rad) * func.cos(stop_lat_rad) * func.power(func.sin(dlon / 2), 2)

    # Distance in meters (Earth radius = 6371000m)
    distance = 2 * 6371000 * func.asin(func.sqrt(a))

    # Convert radius to meters
    radius_m = radius_km * 1000

    # Filter by bounding box first for performance, then by actual distance
    lat_delta = radius_km / 111
    lon_delta = radius_km / (111 * math.cos(math.radians(lat)))

    # Build base query
    query = (
        db.query(StopModel)
        .filter(
            StopModel.lat.between(lat - lat_delta, lat + lat_delta),
            StopModel.lon.between(lon - float(lon_delta), lon + float(lon_delta)),
            or_(
                StopModel.location_type == 1,  # Parent stations
                StopModel.parent_station_id.is_(None),  # Stops without parent
            ),
            # Exclude entrances and TMB bus stops (TMB_METRO_2.xxx which are buses, not metro)
            ~StopModel.id.like('%_E.%'),
            ~StopModel.id.like('TMB_METRO_2.%'),
        )
    )

    # Apply transport type filter
    # Only stops with GTFS-RT data available by default
    if transport_type == 'all':
        # Return all stops (including static GTFS without real-time)
        pass
    elif transport_type == 'metro':
        query = query.filter(
            or_(
                StopModel.id.like('TMB_METRO_P.%'),
                StopModel.id.like('TMB_METRO_1.%'),
                StopModel.id.like('METRO_%'),
                StopModel.id.like('ML_%'),
                StopModel.id.like('METRO_BILBAO_%'),
                StopModel.id.like('FGC_%'),
            )
        )
    elif transport_type == 'cercanias':
        query = query.filter(StopModel.id.like('RENFE_%'))
    elif transport_type == 'fgc':
        query = query.filter(StopModel.id.like('FGC_%'))
    elif transport_type == 'tram':
        query = query.filter(StopModel.id.like('TRAM_%'))
    else:
        # Default: only stops with GTFS-RT (metro, cercanías, FGC, tram, euskotren)
        query = query.filter(
            or_(
                # Metro Barcelona (parent stations and line stops)
                StopModel.id.like('TMB_METRO_P.%'),
                StopModel.id.like('TMB_METRO_1.%'),
                # Cercanías/Rodalies
                StopModel.id.like('RENFE_%'),
                # FGC
                StopModel.id.like('FGC_%'),
                # Metro Madrid
                StopModel.id.like('METRO_%'),
                # Metro Ligero Madrid
                StopModel.id.like('ML_%'),
                # Metro Bilbao
                StopModel.id.like('METRO_BILBAO_%'),
                # Euskotren
                StopModel.id.like('EUSKOTREN_%'),
                # Tram
                StopModel.id.like('TRAM_%'),
            )
        )

    stops = (
        query
        .filter(distance <= radius_m)
        .order_by(distance)
        .limit(limit)
        .all()
    )

    return stops


@router.get("/stops/{stop_id}", response_model=StopResponse)
def get_stop(stop_id: str, db: Session = Depends(get_db)):
    """Get a specific stop by ID."""
    stop = db.query(StopModel).filter(StopModel.id == stop_id).first()
    if not stop:
        raise HTTPException(status_code=404, detail=f"Stop {stop_id} not found")
    return stop


def _get_frequency_based_departures(
    db: Session,
    stop: StopModel,
    route_id: Optional[str],
    limit: int,
    now: datetime,
    current_seconds: int,
) -> List[DepartureResponse]:
    """Generate frequency-based departure estimates for Metro/ML stops.

    Since Metro doesn't have GTFS-RT or stop_times data, we use frequency data
    to estimate upcoming departures based on headway intervals.
    """
    departures = []

    # Determine day type considering holidays and pre-holidays (vísperas)
    day_type = get_effective_day_type(now)

    current_time = now.time()
    current_time_str = now.strftime("%H:%M:%S")  # For VARCHAR comparison with end_time

    # Get routes serving this stop from stop_route_sequence
    routes_query = (
        db.query(RouteModel)
        .join(StopRouteSequenceModel, RouteModel.id == StopRouteSequenceModel.route_id)
        .filter(StopRouteSequenceModel.stop_id == stop.id)
    )

    if route_id:
        routes_query = routes_query.filter(RouteModel.id == route_id)

    routes = routes_query.all()

    # If no routes found via sequences, try lineas field
    if not routes and stop.lineas:
        line_names = [l.strip() for l in stop.lineas.split(",")]
        is_metro = stop.id.startswith("METRO_")
        is_ml = stop.id.startswith("ML_")

        for line_name in line_names:
            # Build short_name to search for
            # Metro routes have "L" prefix (L1-L12), ML routes have "ML" prefix
            if is_metro and line_name.isdigit():
                search_name = f"L{line_name}"
            elif is_ml and line_name.isdigit():
                search_name = f"ML{line_name}"
            else:
                search_name = line_name

            # Try to find route by short_name AND same nucleo as the stop
            # This prevents matching Madrid Metro L1 for a Sevilla Metro stop
            route_query = db.query(RouteModel).filter(
                RouteModel.short_name == search_name,
                RouteModel.id.like("METRO_%") | RouteModel.id.like("ML_%") | RouteModel.id.like("TRAM_SEV_%")
            )
            # Filter by network_id to match stop's network
            # Extract network from stop ID prefix (e.g., TMB_METRO_, FGC_, RENFE_)
            stop_prefix = stop.id.split('_')[0] if '_' in stop.id else None
            if stop_prefix:
                network_map = {'TMB': 'TMB_METRO', 'FGC': 'FGC', 'METRO': '11T', 'ML': '12T'}
                if stop_prefix in network_map:
                    route_query = route_query.filter(RouteModel.network_id == network_map[stop_prefix])

            route = route_query.first()
            if route:
                if not route_id or route.id == route_id:
                    routes.append(route)

    if not routes:
        return []

    # For each route, get current frequency and generate departures
    for route in routes:
        # Skip routes that are not currently operating (static GTFS routes only)
        # This prevents showing future departures when service is closed
        if is_static_gtfs_route(route.id) and not is_route_operating(db, route.id, current_seconds, day_type):
            continue

        # Get applicable frequency for current time and day
        # Handle end_time=00:00:00 as "until midnight" (end of service)
        effective_day_type = day_type

        # Note: end_time is VARCHAR to support GTFS 25:30:00 format
        frequency = (
            db.query(RouteFrequencyModel)
            .filter(
                RouteFrequencyModel.route_id == route.id,
                RouteFrequencyModel.day_type == effective_day_type,
                RouteFrequencyModel.start_time <= current_time,
                or_(
                    RouteFrequencyModel.end_time > current_time_str,
                    RouteFrequencyModel.end_time == "00:00:00",  # 00:00:00 means until midnight
                ),
            )
            .first()
        )

        # Fallback: if friday has no data, try weekday
        if not frequency and effective_day_type == 'friday':
            effective_day_type = 'weekday'
            frequency = (
                db.query(RouteFrequencyModel)
                .filter(
                    RouteFrequencyModel.route_id == route.id,
                    RouteFrequencyModel.day_type == effective_day_type,
                    RouteFrequencyModel.start_time <= current_time,
                    or_(
                        RouteFrequencyModel.end_time > current_time_str,
                        RouteFrequencyModel.end_time == "00:00:00",
                    ),
                )
                .first()
            )

        # Track if we're using a future frequency (service hasn't started yet)
        is_future_frequency = False
        frequency_start_seconds = None

        if not frequency:
            # Try to get next upcoming frequency
            frequency = (
                db.query(RouteFrequencyModel)
                .filter(
                    RouteFrequencyModel.route_id == route.id,
                    RouteFrequencyModel.day_type == effective_day_type,
                    RouteFrequencyModel.start_time > current_time,
                )
                .order_by(RouteFrequencyModel.start_time)
                .first()
            )
            if frequency:
                is_future_frequency = True
                # Calculate when this frequency starts in seconds since midnight
                frequency_start_seconds = (
                    frequency.start_time.hour * 3600 +
                    frequency.start_time.minute * 60 +
                    frequency.start_time.second
                )

        if not frequency:
            continue

        headway_secs = frequency.headway_secs

        # Get stop sequence to determine headsign (direction)
        stop_seq = (
            db.query(StopRouteSequenceModel)
            .filter(
                StopRouteSequenceModel.route_id == route.id,
                StopRouteSequenceModel.stop_id == stop.id,
            )
            .first()
        )

        # Get terminal stations for headsign
        first_stop_seq = (
            db.query(StopRouteSequenceModel)
            .filter(StopRouteSequenceModel.route_id == route.id)
            .order_by(StopRouteSequenceModel.sequence)
            .first()
        )
        last_stop_seq = (
            db.query(StopRouteSequenceModel)
            .filter(StopRouteSequenceModel.route_id == route.id)
            .order_by(StopRouteSequenceModel.sequence.desc())
            .first()
        )

        # Generate departures for both directions
        directions = []
        if first_stop_seq and last_stop_seq:
            first_stop = db.query(StopModel).filter(StopModel.id == first_stop_seq.stop_id).first()
            last_stop = db.query(StopModel).filter(StopModel.id == last_stop_seq.stop_id).first()

            # Show valid directions based on position:
            # - Direction 0 (towards last_stop): show if NOT at last stop
            # - Direction 1 (towards first_stop): show if NOT at first stop
            # At terminus: only show direction AWAY from current stop (trains originate here)

            # Check if current stop is a terminus by comparing stop IDs
            is_at_first_stop = (first_stop_seq.stop_id == stop.id)
            is_at_last_stop = (last_stop_seq.stop_id == stop.id)

            if stop_seq:
                # Use sequence numbers for comparison
                is_at_first_stop = (stop_seq.sequence == first_stop_seq.sequence)
                is_at_last_stop = (stop_seq.sequence == last_stop_seq.sequence)

            # Direction 0: towards last_stop - only show if NOT at last stop
            if not is_at_last_stop and last_stop:
                directions.append((0, last_stop.name))
            # Direction 1: towards first_stop - only show if NOT at first stop
            if not is_at_first_stop and first_stop:
                directions.append((1, first_stop.name))

        if not directions:
            directions = [(0, route.long_name or route.short_name)]

        # Generate estimated departures
        # If using a future frequency, start from when service begins
        # Otherwise, start from now (round up to next minute)
        if is_future_frequency and frequency_start_seconds:
            next_departure_seconds = frequency_start_seconds
        else:
            next_departure_seconds = ((current_seconds // 60) + 1) * 60

        # Generate departures for each direction
        departures_per_direction = max(1, limit // len(directions) // len(routes))

        for direction_id, headsign in directions:
            # Offset departures for opposite directions by half headway
            offset = (headway_secs // 2) * direction_id
            departure_seconds = next_departure_seconds + offset

            for i in range(departures_per_direction):
                # Calculate departure time string
                dep_hours = (departure_seconds // 3600) % 24
                dep_minutes = (departure_seconds % 3600) // 60
                dep_secs = departure_seconds % 60
                departure_time_str = f"{dep_hours:02d}:{dep_minutes:02d}:{dep_secs:02d}"

                minutes_until = max(0, (departure_seconds - current_seconds) // 60)

                departures.append(
                    DepartureResponse(
                        trip_id=f"{route.id}_FREQ_{direction_id}_{i}",
                        route_id=route.id,
                        route_short_name=route.short_name.strip() if route.short_name else "",
                        route_color=route.color,
                        headsign=headsign,
                        departure_time=departure_time_str,
                        departure_seconds=departure_seconds,
                        minutes_until=minutes_until,
                        stop_sequence=stop_seq.sequence if stop_seq else 0,
                        frequency_based=True,
                        headway_secs=headway_secs,
                    )
                )

                departure_seconds += headway_secs

    # Sort by minutes_until and limit results
    departures.sort(key=lambda d: d.minutes_until)
    return departures[:limit]


@router.get("/stops/{stop_id}/departures", response_model=List[DepartureResponse])
def get_stop_departures(
    stop_id: str,
    route_id: Optional[str] = Query(None, description="Filter by route ID"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
    db: Session = Depends(get_db),
):
    """Get upcoming departures from a stop.

    Returns the next departures from this stop, filtered by current time and active services.
    """
    # Verify stop exists
    stop = db.query(StopModel).filter(StopModel.id == stop_id).first()
    if not stop:
        raise HTTPException(status_code=404, detail=f"Stop {stop_id} not found")

    # If this is a parent station, get all child stop IDs
    # Parent stations (location_type=1) don't have stop_times, their children do
    if stop.location_type == 1:
        child_stops = db.query(StopModel.id).filter(
            StopModel.parent_station_id == stop_id
        ).all()
        stop_ids_to_query = [child.id for child in child_stops]
        if not stop_ids_to_query:
            # No direct children - try to find related stops by pattern
            # TMB_METRO_P.XXXXXXX -> TMB_METRO_1.XXX (platform stops use last 3 digits)
            if stop_id.startswith("TMB_METRO_P."):
                suffix = stop_id.split(".")[-1][-3:]  # Last 3 digits
                platform_stop_id = f"TMB_METRO_1.{suffix}"
                platform_stop = db.query(StopModel.id).filter(
                    StopModel.id == platform_stop_id
                ).first()
                if platform_stop:
                    stop_ids_to_query = [platform_stop.id]
                else:
                    stop_ids_to_query = [stop_id]
            # FGC_XX -> FGC_XX1, FGC_XX2, etc. (platform stops have numeric suffix)
            elif stop_id.startswith("FGC_") and not stop_id[-1].isdigit():
                platform_stops = db.query(StopModel.id).filter(
                    StopModel.id.like(f"{stop_id}%"),
                    StopModel.id != stop_id
                ).all()
                if platform_stops:
                    stop_ids_to_query = [p.id for p in platform_stops]
                else:
                    stop_ids_to_query = [stop_id]
            else:
                stop_ids_to_query = [stop_id]  # Fallback to parent if no children
    else:
        stop_ids_to_query = [stop_id]

    # Get current time in seconds since midnight (Madrid timezone)
    now = datetime.now(MADRID_TZ)
    current_seconds = now.hour * 3600 + now.minute * 60 + now.second
    today = now.date()
    weekday = today.weekday()  # 0=Monday, 6=Sunday

    # Map weekday to calendar column
    weekday_columns = {
        0: CalendarModel.monday,
        1: CalendarModel.tuesday,
        2: CalendarModel.wednesday,
        3: CalendarModel.thursday,
        4: CalendarModel.friday,
        5: CalendarModel.saturday,
        6: CalendarModel.sunday,
    }

    # Get active service IDs for today
    # 1. Services from calendar that are active today
    active_services_query = db.query(CalendarModel.service_id).filter(
        CalendarModel.start_date <= today,
        CalendarModel.end_date >= today,
        weekday_columns[weekday].is_(True),
    )

    # 2. Add exceptions (type 1 = added)
    added_services = db.query(CalendarDateModel.service_id).filter(
        CalendarDateModel.date == today,
        CalendarDateModel.exception_type == 1,
    )

    # 3. Remove exceptions (type 2 = removed)
    removed_services = db.query(CalendarDateModel.service_id).filter(
        CalendarDateModel.date == today,
        CalendarDateModel.exception_type == 2,
    )

    active_service_ids = set(
        [s.service_id for s in active_services_query.all()] +
        [s.service_id for s in added_services.all()]
    ) - set([s.service_id for s in removed_services.all()])

    if not active_service_ids:
        return []

    # Query stop times with upcoming departures
    # Subquery to get the max stop_sequence for each trip (to filter out last stops)
    max_sequence_subquery = (
        db.query(
            StopTimeModel.trip_id,
            func.max(StopTimeModel.stop_sequence).label("max_seq")
        )
        .group_by(StopTimeModel.trip_id)
        .subquery()
    )

    query = (
        db.query(StopTimeModel, TripModel, RouteModel)
        .join(TripModel, StopTimeModel.trip_id == TripModel.id)
        .join(RouteModel, TripModel.route_id == RouteModel.id)
        .join(
            max_sequence_subquery,
            StopTimeModel.trip_id == max_sequence_subquery.c.trip_id
        )
        .filter(
            StopTimeModel.stop_id.in_(stop_ids_to_query),
            StopTimeModel.departure_seconds >= current_seconds,
            TripModel.service_id.in_(active_service_ids),
            # Exclude trips where this stop is the last stop (train arrives, doesn't depart)
            StopTimeModel.stop_sequence < max_sequence_subquery.c.max_seq,
        )
    )

    if route_id:
        query = query.filter(TripModel.route_id == route_id)

    results = (
        query
        .order_by(StopTimeModel.departure_seconds)
        .limit(limit)
        .all()
    )

    # If no stop_times results, check if this is a Metro/ML/Tranvia/FGC stop and use frequency-based departures
    # For parent stations, check if any child is a metro/fgc stop
    is_metro_stop = any(
        sid.startswith("METRO_") or sid.startswith("ML_") or sid.startswith("TRAM_SEV_") or
        sid.startswith("TMB_METRO_1.") or  # TMB Metro platforms
        sid.startswith("FGC_")  # FGC platforms
        for sid in stop_ids_to_query
    )
    if not results and is_metro_stop:
        return _get_frequency_based_departures(db, stop, route_id, limit, now, current_seconds)

    # For Metro stops that have SOME stop_times results but may have additional lines
    # without stop_times (e.g., Line 12), also get frequency-based departures for those lines
    frequency_departures = []
    if is_metro_stop and results:
        # Get routes that have stop_times results
        routes_with_stop_times = set(route.id for _, _, route in results)

        # Get all routes serving these stops
        all_route_ids_at_stop = set(
            seq.route_id for seq in db.query(StopRouteSequenceModel.route_id)
            .filter(StopRouteSequenceModel.stop_id.in_(stop_ids_to_query))
            .all()
        )

        # Routes that need frequency-based departures
        routes_needing_freq = all_route_ids_at_stop - routes_with_stop_times

        # Filter by route_id if specified
        if route_id and route_id not in routes_needing_freq:
            routes_needing_freq = set()

        if routes_needing_freq:
            # Get frequency departures for routes without stop_times
            for freq_route_id in routes_needing_freq:
                freq_deps = _get_frequency_based_departures(
                    db, stop, freq_route_id, limit, now, current_seconds
                )
                frequency_departures.extend(freq_deps)

    # Get trip IDs for realtime delay lookup
    trip_ids = [trip.id for _, trip, _ in results]

    # Get last stop names for trips (to use as headsign when trip.headsign is null)
    # The headsign should be the final destination of the train
    last_stop_names = {}
    if trip_ids:
        # Subquery to get max stop_sequence for each trip
        max_seq_subq = (
            db.query(
                StopTimeModel.trip_id,
                func.max(StopTimeModel.stop_sequence).label("max_seq")
            )
            .filter(StopTimeModel.trip_id.in_(trip_ids))
            .group_by(StopTimeModel.trip_id)
            .subquery()
        )

        # Get the stop name at max_seq for each trip
        last_stops = (
            db.query(StopTimeModel.trip_id, StopModel.name)
            .join(StopModel, StopTimeModel.stop_id == StopModel.id)
            .join(
                max_seq_subq,
                and_(
                    StopTimeModel.trip_id == max_seq_subq.c.trip_id,
                    StopTimeModel.stop_sequence == max_seq_subq.c.max_seq
                )
            )
            .all()
        )
        last_stop_names = {trip_id: name for trip_id, name in last_stops}

    # Get trip-level delays
    trip_delays = {}
    if trip_ids:
        trip_updates = db.query(TripUpdateModel).filter(
            TripUpdateModel.trip_id.in_(trip_ids)
        ).all()
        trip_delays = {tu.trip_id: tu.delay for tu in trip_updates}

    # Get stop-specific delays and platform info
    stop_delays = {}
    stop_platforms = {}
    if trip_ids:
        stop_time_updates = db.query(StopTimeUpdateModel).filter(
            StopTimeUpdateModel.trip_id.in_(trip_ids),
            StopTimeUpdateModel.stop_id == stop_id,
        ).all()
        for stu in stop_time_updates:
            stop_delays[stu.trip_id] = stu.departure_delay
            if stu.platform:
                stop_platforms[stu.trip_id] = stu.platform

    # For TMB/FGC: Also get platforms by stop_id (RT trip_ids differ from static GTFS)
    # Get all recent platforms for the queried stop_ids
    stop_platforms_by_stop = {}
    if stop_ids_to_query:
        recent_platforms = db.query(StopTimeUpdateModel).filter(
            StopTimeUpdateModel.stop_id.in_(stop_ids_to_query),
            StopTimeUpdateModel.platform.isnot(None)
        ).order_by(StopTimeUpdateModel.arrival_time.desc()).limit(100).all()
        for stu in recent_platforms:
            if stu.stop_id not in stop_platforms_by_stop:
                stop_platforms_by_stop[stu.stop_id] = stu.platform

    # Get train positions: first try GTFS-RT, then fall back to estimated
    train_positions = {}

    # 1. Try GTFS-RT vehicle positions
    vehicle_platforms = {}
    # Extract numeric stop_id for comparison (e.g., "17000" from "RENFE_17000")
    queried_stop_numeric = stop_id.replace("RENFE_", "") if stop_id.startswith("RENFE_") else stop_id

    if trip_ids:
        vehicle_positions = db.query(VehiclePositionModel).filter(
            VehiclePositionModel.trip_id.in_(trip_ids)
        ).all()
        for vp in vehicle_positions:
            # Get current stop name from stop_id (try with RENFE_ prefix)
            current_stop = None
            if vp.stop_id:
                current_stop = db.query(StopModel).filter(StopModel.id == f"RENFE_{vp.stop_id}").first()
                if not current_stop:
                    current_stop = db.query(StopModel).filter(StopModel.id == vp.stop_id).first()

            status = vp.current_status.value if vp.current_status else "IN_TRANSIT_TO"
            train_positions[vp.trip_id] = TrainPositionSchema(
                latitude=vp.latitude,
                longitude=vp.longitude,
                current_stop_name=current_stop.name if current_stop else "En tránsito",
                status=status,
                progress_percent=50.0,  # GTFS-RT doesn't provide progress
                estimated=False  # This is real GTFS-RT data
            )

            # Only store platform if train is AT or INCOMING to the queried stop
            # Compare stop_ids (handle both "17000" and "RENFE_17000" formats)
            vp_stop_numeric = vp.stop_id.replace("RENFE_", "") if vp.stop_id and vp.stop_id.startswith("RENFE_") else vp.stop_id
            train_at_queried_stop = vp_stop_numeric == queried_stop_numeric

            if vp.platform and train_at_queried_stop and status in ("STOPPED_AT", "INCOMING_AT"):
                vehicle_platforms[vp.trip_id] = vp.platform

    # 2. For trips without GTFS-RT, get estimated positions
    trips_without_position = [tid for tid in trip_ids if tid not in train_positions]
    if trips_without_position:
        estimated_service = EstimatedPositionsService(db)
        # Get estimated positions for the specific trips we need
        estimated_positions = estimated_service.get_estimated_positions(
            trip_ids=trips_without_position,
            limit=len(trips_without_position)
        )
        for ep in estimated_positions:
            train_positions[ep.trip_id] = TrainPositionSchema(
                latitude=ep.latitude,
                longitude=ep.longitude,
                current_stop_name=ep.current_stop_name,
                status=ep.current_status.value,
                progress_percent=ep.progress_percent,
                estimated=True
            )

    # Helper function to get estimated platform from history
    def get_estimated_platform(route_short: str, headsign: str) -> Optional[str]:
        """Get most likely platform from historical data.

        Looks at today's data first, then yesterday's if no data for today.
        Uses the platform with highest count (most commonly used).
        Falls back to searching without headsign if exact match not found.
        """
        from datetime import date, timedelta
        today_date = date.today()
        yesterday = today_date - timedelta(days=1)

        # Try today first with exact headsign
        history = db.query(PlatformHistoryModel).filter(
            PlatformHistoryModel.stop_id == queried_stop_numeric,
            PlatformHistoryModel.route_short_name == route_short,
            PlatformHistoryModel.headsign == headsign,
            PlatformHistoryModel.observation_date == today_date,
        ).order_by(PlatformHistoryModel.count.desc()).first()

        if history:
            return history.platform

        # Try today without headsign filter (for "Unknown" headsigns)
        history = db.query(PlatformHistoryModel).filter(
            PlatformHistoryModel.stop_id == queried_stop_numeric,
            PlatformHistoryModel.route_short_name == route_short,
            PlatformHistoryModel.observation_date == today_date,
        ).order_by(PlatformHistoryModel.count.desc()).first()

        if history:
            return history.platform

        # Fall back to yesterday with exact headsign
        history = db.query(PlatformHistoryModel).filter(
            PlatformHistoryModel.stop_id == queried_stop_numeric,
            PlatformHistoryModel.route_short_name == route_short,
            PlatformHistoryModel.headsign == headsign,
            PlatformHistoryModel.observation_date == yesterday,
        ).order_by(PlatformHistoryModel.count.desc()).first()

        if history:
            return history.platform

        # Fall back to yesterday without headsign filter
        history = db.query(PlatformHistoryModel).filter(
            PlatformHistoryModel.stop_id == queried_stop_numeric,
            PlatformHistoryModel.route_short_name == route_short,
            PlatformHistoryModel.observation_date == yesterday,
        ).order_by(PlatformHistoryModel.count.desc()).first()

        return history.platform if history else None

    # Determine day type for operating hours check
    day_type = get_effective_day_type(now)

    departures = []
    for stop_time, trip, route in results:
        # Filter out static GTFS routes outside operating hours
        if is_static_gtfs_route(route.id) and not is_route_operating(db, route.id, current_seconds, day_type):
            continue

        minutes_until = (stop_time.departure_seconds - current_seconds) // 60

        # Get delay: prefer stop-specific delay, fall back to trip delay
        delay_seconds = stop_delays.get(trip.id) or trip_delays.get(trip.id)
        realtime_departure_time = None
        realtime_minutes_until = None
        is_delayed = False

        if delay_seconds is not None and delay_seconds != 0:
            is_delayed = delay_seconds > 60  # More than 1 minute delay
            realtime_departure_seconds = stop_time.departure_seconds + delay_seconds
            # Convert to HH:MM:SS format
            rt_hours = realtime_departure_seconds // 3600
            rt_minutes = (realtime_departure_seconds % 3600) // 60
            rt_seconds = realtime_departure_seconds % 60
            realtime_departure_time = f"{rt_hours:02d}:{rt_minutes:02d}:{rt_seconds:02d}"
            realtime_minutes_until = max(0, (realtime_departure_seconds - current_seconds) // 60)

        # Get train position (from GTFS-RT or estimated)
        train_position = train_positions.get(trip.id)

        # Get headsign: prefer trip.headsign, fall back to last stop name (destination)
        headsign = trip.headsign or last_stop_names.get(trip.id)

        # Get platform from GTFS-RT (prefer stop_time_update, then vehicle_position, then by stop_id)
        platform = stop_platforms.get(trip.id) or vehicle_platforms.get(trip.id)
        # For TMB/FGC: try platform by stop_id if not found by trip_id
        if not platform and stop_time.stop_id in stop_platforms_by_stop:
            platform = stop_platforms_by_stop[stop_time.stop_id]
        platform_estimated = False

        # If no real platform, try to get estimated from history
        if not platform:
            route_short = route.short_name.strip() if route.short_name else ""
            estimated = get_estimated_platform(route_short, headsign or "")
            if estimated:
                platform = estimated
                platform_estimated = True

        departures.append(
            DepartureResponse(
                trip_id=trip.id,
                route_id=route.id,
                route_short_name=route.short_name.strip() if route.short_name else "",
                route_color=route.color,
                headsign=headsign,
                departure_time=stop_time.departure_time,
                departure_seconds=stop_time.departure_seconds,
                minutes_until=minutes_until,
                stop_sequence=stop_time.stop_sequence,
                platform=platform,
                platform_estimated=platform_estimated,
                delay_seconds=delay_seconds,
                realtime_departure_time=realtime_departure_time,
                realtime_minutes_until=realtime_minutes_until,
                is_delayed=is_delayed,
                train_position=train_position,
            )
        )

    # Add frequency-based departures for Metro routes without stop_times
    if frequency_departures:
        departures.extend(frequency_departures)

    # Sort by realtime departure (use realtime_minutes_until if available, else minutes_until)
    departures.sort(key=lambda d: d.realtime_minutes_until if d.realtime_minutes_until is not None else d.minutes_until)

    return departures[:limit]


@router.get("/trips/{trip_id}", response_model=TripDetailResponse)
def get_trip(trip_id: str, db: Session = Depends(get_db)):
    """Get details for a specific trip including all stops."""
    trip = db.query(TripModel).filter(TripModel.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail=f"Trip {trip_id} not found")

    route = db.query(RouteModel).filter(RouteModel.id == trip.route_id).first()

    # Get all stop times for this trip with stop info
    stop_times = (
        db.query(StopTimeModel, StopModel)
        .join(StopModel, StopTimeModel.stop_id == StopModel.id)
        .filter(StopTimeModel.trip_id == trip_id)
        .order_by(StopTimeModel.stop_sequence)
        .all()
    )

    stops = [
        TripStopResponse(
            stop_id=stop.id,
            stop_name=stop.name,
            arrival_time=stop_time.arrival_time,
            departure_time=stop_time.departure_time,
            stop_sequence=stop_time.stop_sequence,
            stop_lat=stop.lat,
            stop_lon=stop.lon,
        )
        for stop_time, stop in stop_times
    ]

    # Get headsign: prefer trip.headsign, fall back to last stop name (destination)
    headsign = trip.headsign
    if not headsign and stops:
        headsign = stops[-1].stop_name

    return TripDetailResponse(
        id=trip.id,
        route_id=trip.route_id,
        route_short_name=route.short_name.strip() if route and route.short_name else "",
        route_long_name=route.long_name.strip() if route and route.long_name else "",
        route_color=route.color if route else None,
        headsign=headsign,
        direction_id=trip.direction_id,
        stops=stops,
    )


@router.get("/routes/{route_id}/stops", response_model=List[RouteStopResponse])
def get_route_stops(route_id: str, db: Session = Depends(get_db)):
    """Get all stops served by a route, ordered by their position along the route.

    Returns stops with their stop_sequence number indicating position in the route.
    For stops with a parent_station, returns the parent station instead to avoid duplicates.
    """
    from src.gtfs_bc.stop_route_sequence.infrastructure.models import StopRouteSequenceModel

    # Verify route exists
    route = db.query(RouteModel).filter(RouteModel.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail=f"Route {route_id} not found")

    # Query stops with sequence using the stop_route_sequence table
    results = (
        db.query(StopModel, StopRouteSequenceModel.sequence)
        .join(
            StopRouteSequenceModel,
            StopModel.id == StopRouteSequenceModel.stop_id
        )
        .filter(StopRouteSequenceModel.route_id == route_id)
        .order_by(StopRouteSequenceModel.sequence)
        .all()
    )

    if results:
        # Group by parent station to avoid duplicates
        # If stop has parent_station_id, use the parent station instead
        seen_stations = {}  # parent_id or stop_id -> (stop_or_parent, min_sequence)
        parent_cache = {}  # Cache for parent station lookups

        for stop, sequence in results:
            if stop.parent_station_id:
                # This stop has a parent - use the parent station
                station_key = stop.parent_station_id
                if station_key not in seen_stations:
                    # Fetch parent station if not cached
                    if station_key not in parent_cache:
                        parent = db.query(StopModel).filter(StopModel.id == station_key).first()
                        parent_cache[station_key] = parent
                    parent = parent_cache[station_key]
                    if parent:
                        seen_stations[station_key] = (parent, sequence)
                # Keep the minimum sequence (first occurrence)
            else:
                # No parent - use the stop itself
                station_key = stop.id
                if station_key not in seen_stations:
                    seen_stations[station_key] = (stop, sequence)

        # Sort by sequence and build response
        sorted_stations = sorted(seen_stations.values(), key=lambda x: x[1])

        return [
            RouteStopResponse(
                id=stop.id,
                name=stop.name,
                lat=stop.lat,
                lon=stop.lon,
                code=stop.code,
                location_type=stop.location_type,
                parent_station_id=stop.parent_station_id,
                zone_id=stop.zone_id,
                province=stop.province,
                lineas=stop.lineas,
                parking_bicis=stop.parking_bicis,
                accesibilidad=stop.accesibilidad,
                cor_bus=stop.cor_bus,
                cor_metro=stop.cor_metro,
                cor_ml=stop.cor_ml,
                cor_cercanias=stop.cor_cercanias,
                cor_tranvia=stop.cor_tranvia,
                is_hub=stop.is_hub,
                stop_sequence=sequence,
            )
            for stop, sequence in sorted_stations
        ]

    # If no sequences found, fallback to lineas-based search with alphabetical order
    short_name = route.short_name

    # Build filter based on stop ID prefix matching route's network
    # Use more specific prefix for routes like TRAM_BARCELONA_1 -> TRAM_BARCELONA
    # or TMB_METRO_1.1.1 -> TMB_METRO
    route_parts = route.id.split('_')
    if len(route_parts) >= 2:
        # Use first two parts: TRAM_BARCELONA, TMB_METRO, TRAM_SEV, etc.
        route_prefix = f"{route_parts[0]}_{route_parts[1]}"
    else:
        route_prefix = route_parts[0] if route_parts else None

    stops = (
        db.query(StopModel)
        .filter(
            and_(
                StopModel.id.like(f"{route_prefix}%") if route_prefix else True,
                StopModel.lineas.isnot(None),
                or_(
                    StopModel.lineas == short_name,
                    StopModel.lineas.startswith(f"{short_name},"),
                    StopModel.lineas.endswith(f",{short_name}"),
                    StopModel.lineas.contains(f",{short_name},"),
                )
            )
        )
        .order_by(StopModel.name)
        .all()
    )

    # Return with generated sequence numbers for fallback
    return [
        RouteStopResponse(
            id=stop.id,
            name=stop.name,
            lat=stop.lat,
            lon=stop.lon,
            code=stop.code,
            location_type=stop.location_type,
            parent_station_id=stop.parent_station_id,
            zone_id=stop.zone_id,
            province=stop.province,
            lineas=stop.lineas,
            parking_bicis=stop.parking_bicis,
            accesibilidad=stop.accesibilidad,
            cor_bus=stop.cor_bus,
            cor_metro=stop.cor_metro,
            cor_ml=stop.cor_ml,
            cor_cercanias=stop.cor_cercanias,
            cor_tranvia=stop.cor_tranvia,
            is_hub=stop.is_hub,
            stop_sequence=idx + 1,
        )
        for idx, stop in enumerate(stops)
    ]


@router.get("/routes/{route_id}/frequencies", response_model=List[RouteFrequencyResponse])
def get_route_frequencies(route_id: str, db: Session = Depends(get_db)):
    """Get frequency data for a route (operating hours and headways).

    Returns frequency information for Metro, Metro Ligero, Tranvía, and other
    frequency-based services. Includes start/end times and headway for each
    day type (weekday, saturday, sunday).

    Returns empty list for schedule-based routes (like Cercanías) that use
    stop_times instead of frequencies.
    """
    # Verify route exists
    route = db.query(RouteModel).filter(RouteModel.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail=f"Route {route_id} not found")

    # Get frequencies for this route
    frequencies = (
        db.query(RouteFrequencyModel)
        .filter(RouteFrequencyModel.route_id == route_id)
        .order_by(RouteFrequencyModel.day_type, RouteFrequencyModel.start_time)
        .all()
    )

    return [
        RouteFrequencyResponse(
            route_id=freq.route_id,
            day_type=freq.day_type,
            start_time=freq.start_time.strftime("%H:%M:%S") if hasattr(freq.start_time, 'strftime') else str(freq.start_time),
            end_time=freq.end_time.strftime("%H:%M:%S") if hasattr(freq.end_time, 'strftime') else str(freq.end_time),
            headway_secs=freq.headway_secs,
            headway_minutes=round(freq.headway_secs / 60, 1),
        )
        for freq in frequencies
    ]


@router.get("/routes/{route_id}/operating-hours", response_model=RouteOperatingHoursResponse)
def get_route_operating_hours(route_id: str, db: Session = Depends(get_db)):
    """Get operating hours for a route (first/last departure times).

    Works for both schedule-based routes (Cercanías) and frequency-based
    routes (Metro, Tranvía). For Cercanías, derives from stop_times.
    For Metro/Tranvía, derives from frequencies table.

    Returns first and last departure times for each day type (weekday,
    saturday, sunday) along with total trip count (0 for frequency-based).
    """
    # Verify route exists
    route = db.query(RouteModel).filter(RouteModel.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail=f"Route {route_id} not found")

    # Check for service suspension alerts
    is_suspended = False
    suspension_message = None

    fetcher = GTFSRealtimeFetcher(db)
    alerts = fetcher.get_alerts_for_route(route_id)

    # Keywords that indicate TRAIN SERVICE suspension (not facilities)
    suspension_keywords = [
        "suspende el servicio de trenes",
        "servicio de trenes suspendido",
        "se suspende el servicio",
        "sin servicio de trenes",
        "no circula",
        "circulación suspendida",
        "línea cerrada",
    ]

    # Keywords that indicate facility issues (NOT service suspension)
    facility_keywords = [
        "ascensor",
        "escalera",
        "aseo",
        "igogailu",  # Ascensor en euskera
        "eskailera",  # Escalera en euskera
    ]

    for alert in alerts:
        alert_text = (alert.description_text or "") + " " + (alert.header_text or "")
        alert_text_lower = alert_text.lower()

        # Skip alerts about facilities (elevators, escalators, bathrooms)
        is_facility_alert = any(fk in alert_text_lower for fk in facility_keywords)
        if is_facility_alert:
            continue

        for keyword in suspension_keywords:
            if keyword in alert_text_lower:
                is_suspended = True
                suspension_message = alert.description_text or alert.header_text
                break
        if is_suspended:
            break

    # Get all trips for this route with their calendar info
    trips_with_calendar = (
        db.query(TripModel, CalendarModel)
        .join(CalendarModel, TripModel.service_id == CalendarModel.service_id)
        .filter(TripModel.route_id == route_id)
        .all()
    )

    if not trips_with_calendar:
        # No schedule data - check if it's a frequency-based route
        frequencies = (
            db.query(RouteFrequencyModel)
            .filter(RouteFrequencyModel.route_id == route_id)
            .all()
        )

        if frequencies:
            # Derive operating hours from frequencies
            freq_by_day = {"weekday": [], "friday": [], "saturday": [], "sunday": []}
            for freq in frequencies:
                if freq.day_type in freq_by_day:
                    freq_by_day[freq.day_type].append(freq)

            def get_freq_hours(day_freqs: list) -> Optional[DayOperatingHours]:
                if not day_freqs:
                    return None

                def format_time(t) -> str:
                    """Format time object or string to HH:MM:SS."""
                    if hasattr(t, 'strftime'):
                        return t.strftime("%H:%M:%S")
                    return str(t)

                def get_end_time_for_sort(f) -> str:
                    """Get end_time as string for sorting (GTFS format already handles 24+)."""
                    return str(f.end_time)

                # Separate morning frequencies (start >= 05:00) from late-night (start < 05:00)
                morning_cutoff = time(5, 0, 0)
                morning_freqs = [f for f in day_freqs if f.start_time >= morning_cutoff]

                # First departure: earliest morning frequency start time
                if morning_freqs:
                    first_dep = min(f.start_time for f in morning_freqs)
                else:
                    first_dep = min(f.start_time for f in day_freqs)

                # Last departure: find max end_time (GTFS format: 25:30:00 > 23:00:00)
                # String comparison works because GTFS format is sortable
                last_dep_str = max(get_end_time_for_sort(f) for f in day_freqs)

                return DayOperatingHours(
                    first_departure=format_time(first_dep) if first_dep else None,
                    last_departure=last_dep_str,
                    total_trips=0,  # Not applicable for frequency-based
                )

            return RouteOperatingHoursResponse(
                route_id=route_id,
                route_short_name=route.short_name.strip() if route.short_name else "",
                weekday=None if is_suspended else get_freq_hours(freq_by_day["weekday"]),
                friday=None if is_suspended else (get_freq_hours(freq_by_day["friday"]) or get_freq_hours(freq_by_day["weekday"])),
                saturday=None if is_suspended else get_freq_hours(freq_by_day["saturday"]),
                sunday=None if is_suspended else get_freq_hours(freq_by_day["sunday"]),
                is_suspended=is_suspended,
                suspension_message=suspension_message,
            )

        # No schedule data and no frequencies
        return RouteOperatingHoursResponse(
            route_id=route_id,
            route_short_name=route.short_name or "",
            weekday=None,
            friday=None,
            saturday=None,
            sunday=None,
            is_suspended=is_suspended,
            suspension_message=suspension_message,
        )

    # Group trips by day type
    trips_by_day = {"weekday": [], "saturday": [], "sunday": []}

    for trip, calendar in trips_with_calendar:
        # Determine day type from calendar
        if calendar.saturday and not calendar.sunday:
            trips_by_day["saturday"].append(trip.id)
        elif calendar.sunday:
            trips_by_day["sunday"].append(trip.id)
        elif calendar.monday or calendar.tuesday or calendar.wednesday:
            trips_by_day["weekday"].append(trip.id)

    def get_day_hours(trip_ids: list) -> Optional[DayOperatingHours]:
        if not trip_ids:
            return None

        # Get first departure (min) and last departure (max) for these trips
        # We use departure_time from the first stop of each trip (stop_sequence = 1 or min)
        from sqlalchemy import func as sqlfunc

        # First departure: filter out late-night services (00:00-04:59) which are
        # actually services from the previous day in GTFS format.
        # Real morning service starts >= 05:00:00
        # Note: departure_time is VARCHAR in GTFS format "HH:MM:SS", so string comparison works
        morning_cutoff = "05:00:00"

        # Get first departure from morning services only
        first_dep_result = (
            db.query(
                sqlfunc.min(StopTimeModel.departure_time).label("first_dep"),
            )
            .filter(StopTimeModel.trip_id.in_(trip_ids))
            .filter(StopTimeModel.departure_time >= morning_cutoff)
            .first()
        )

        # Get last departure and trip count (include all services)
        last_dep_result = (
            db.query(
                sqlfunc.max(StopTimeModel.departure_time).label("last_dep"),
                sqlfunc.count(sqlfunc.distinct(StopTimeModel.trip_id)).label("trip_count"),
            )
            .filter(StopTimeModel.trip_id.in_(trip_ids))
            .first()
        )

        if not first_dep_result or not first_dep_result.first_dep:
            return None

        return DayOperatingHours(
            first_departure=str(first_dep_result.first_dep),
            last_departure=str(last_dep_result.last_dep) if last_dep_result else None,
            total_trips=last_dep_result.trip_count or 0 if last_dep_result else 0,
        )

    return RouteOperatingHoursResponse(
        route_id=route_id,
        route_short_name=route.short_name.strip() if route.short_name else "",
        weekday=None if is_suspended else get_day_hours(trips_by_day["weekday"]),
        friday=None if is_suspended else get_day_hours(trips_by_day["weekday"]),  # Cercanías: Friday same as weekday
        saturday=None if is_suspended else get_day_hours(trips_by_day["saturday"]),
        sunday=None if is_suspended else get_day_hours(trips_by_day["sunday"]),
        is_suspended=is_suspended,
        suspension_message=suspension_message,
    )


@router.get("/stops/{stop_id}/transfers", response_model=List[TransferResponse])
def get_stop_transfers(
    stop_id: str,
    direction: Optional[str] = Query(
        None,
        description="Filter direction: 'from' (transfers FROM this stop), 'to' (transfers TO this stop), or None (both)"
    ),
    db: Session = Depends(get_db),
):
    """Get transfer/interchange information for a stop.

    Returns transfer times and instructions between this stop and nearby lines.
    Data comes from GTFS transfers.txt or manual entries.

    Transfer types:
    - 0: Recommended transfer point
    - 1: Timed transfer (vehicle waits)
    - 2: Minimum time required
    - 3: Transfer not possible
    """
    if direction == "from":
        transfers = db.query(LineTransferModel).filter(
            LineTransferModel.from_stop_id == stop_id
        ).all()
    elif direction == "to":
        transfers = db.query(LineTransferModel).filter(
            LineTransferModel.to_stop_id == stop_id
        ).all()
    else:
        # Both directions
        transfers = db.query(LineTransferModel).filter(
            or_(
                LineTransferModel.from_stop_id == stop_id,
                LineTransferModel.to_stop_id == stop_id,
            )
        ).all()

    return transfers
