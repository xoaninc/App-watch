from typing import List, Optional, Tuple
from datetime import datetime, time
from zoneinfo import ZoneInfo
import math
import re as regex_module
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from core.rate_limiter import limiter, RateLimits

# Centralized imports
from adapters.http.api.gtfs.utils.holiday_utils import get_effective_day_type, MADRID_TZ
from adapters.http.api.gtfs.utils.route_utils import is_static_gtfs_route, is_route_operating, has_real_cercanias
from adapters.http.api.gtfs.utils.shape_utils import normalize_shape
from adapters.http.api.gtfs.utils.walking_route import generate_walking_route, coords_to_json, json_to_coords
from adapters.http.api.gtfs.utils.occupancy_utils import (
    percentage_to_status,
    parse_occupancy_per_car,
    estimate_occupancy_by_time,
)
from adapters.http.api.gtfs.utils.civis_utils import detect_civis
from adapters.http.api.gtfs.utils.text_utils import normalize_headsign
from adapters.http.api.gtfs.schemas import (
    RouteResponse,
    RouteFrequencyResponse,
    DayOperatingHours,
    RouteOperatingHoursResponse,
    ShapePointResponse,
    RouteShapeResponse,
    StopResponse,
    RouteStopResponse,
    PlatformResponse,
    StopPlatformsResponse,
    CorrespondenceResponse,
    StopCorrespondencesResponse,
    WalkingShapePoint,
    TrainPositionSchema,
    DepartureResponse,
    CompactDepartureResponse,
    CompactDeparturesWrapper,
    TripStopResponse,
    TripDetailResponse,
    AgencyResponse,
    JourneyStopResponse,
    JourneyCoordinate,
    JourneySegmentResponse,
    JourneyResponse,
    JourneyAlertResponse,
    RoutePlannerResponse,
)

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
from src.gtfs_bc.stop.infrastructure.models.stop_platform_model import StopPlatformModel
from src.gtfs_bc.stop.infrastructure.models.stop_correspondence_model import StopCorrespondenceModel
from src.gtfs_bc.routing import RaptorService
from src.gtfs_bc.routing.gtfs_store import gtfs_store


router = APIRouter(prefix="/gtfs", tags=["GTFS Query"])


def resolve_stop_to_platforms(stop_id: str) -> List[str]:
    """Resolve a parent station ID to its platform children.

    If the stop_id is a parent station, returns its child platforms.
    If it has no children (is already a platform or simple stop), returns [stop_id].

    This is essential for networks like Metro Bilbao where stop_times
    reference platform IDs (e.g., METRO_BILBAO_7.0) but users search
    by station ID (e.g., METRO_BILBAO_7).
    """
    children = gtfs_store.get_children_stops(stop_id)
    if children:
        return children
    return [stop_id]


def _calculate_is_hub(stop: StopModel) -> bool:
    """Calculate if a stop is a transport hub.

    A hub is a station with 2 or more DIFFERENT transport types.
    """
    transport_count = 0
    if stop.cor_metro:
        transport_count += 1
    if has_real_cercanias(stop.cor_cercanias):
        transport_count += 1
    if stop.cor_ml:
        transport_count += 1
    if stop.cor_tranvia:
        transport_count += 1
    return transport_count >= 2


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
@limiter.limit(RateLimits.COORDINATES)
def get_stops_by_coordinates(
    request: Request,
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


@router.get("/stops/{stop_id}/departures")
@limiter.limit(RateLimits.DEPARTURES)
def get_stop_departures(
    request: Request,
    stop_id: str,
    route_id: Optional[str] = Query(None, description="Filter by route ID"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
    compact: bool = Query(False, description="Return compact response for widgets/Siri"),
    db: Session = Depends(get_db),
):
    """Get upcoming departures from a stop.

    Returns the next departures from this stop, filtered by current time and active services.

    Use `?compact=true` for a minimal response suitable for widgets (<100 bytes per departure).
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

    # Query with higher limit to account for duplicates that will be filtered later
    # (GTFS data may have overlapping frequency periods causing duplicate departure times)
    query_limit = limit * 3

    results = (
        query
        .order_by(StopTimeModel.departure_seconds)
        .limit(query_limit)
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

    # Get stop count per trip (for CIVIS express detection)
    trip_stop_counts = {}
    if trip_ids:
        stop_count_query = (
            db.query(
                StopTimeModel.trip_id,
                func.count(StopTimeModel.stop_id).label("stop_count")
            )
            .filter(StopTimeModel.trip_id.in_(trip_ids))
            .group_by(StopTimeModel.trip_id)
            .all()
        )
        trip_stop_counts = {row.trip_id: row.stop_count for row in stop_count_query}

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

    # Get stop-specific delays, platform info, and occupancy
    stop_delays = {}
    stop_platforms = {}
    stop_occupancy = {}  # {trip_id: (occupancy_percent, occupancy_per_car)}
    if trip_ids:
        stop_time_updates = db.query(StopTimeUpdateModel).filter(
            StopTimeUpdateModel.trip_id.in_(trip_ids),
            StopTimeUpdateModel.stop_id == stop_id,
        ).all()
        for stu in stop_time_updates:
            stop_delays[stu.trip_id] = stu.departure_delay
            if stu.platform:
                stop_platforms[stu.trip_id] = stu.platform
            # Extract occupancy data (available from TMB Metro Barcelona)
            if stu.occupancy_percent is not None or stu.occupancy_per_car:
                stop_occupancy[stu.trip_id] = (
                    stu.occupancy_percent,
                    stu.occupancy_per_car
                )

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
        # Check if the DEPARTURE time is within operating hours (not current time)
        # This allows showing upcoming departures even if service hasn't started yet
        if is_static_gtfs_route(route.id) and not is_route_operating(db, route.id, stop_time.departure_seconds, day_type):
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
        # Normalize to Title Case (some GTFS data has ALL CAPS headsigns)
        headsign = normalize_headsign(trip.headsign or last_stop_names.get(trip.id))

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

        # Get occupancy data from GTFS-RT (available for TMB Metro Barcelona)
        occupancy_percent = None
        occupancy_status = None
        occupancy_per_car = None
        if trip.id in stop_occupancy:
            occ_pct, occ_per_car_json = stop_occupancy[trip.id]
            occupancy_percent = occ_pct
            occupancy_status = percentage_to_status(occ_pct)
            occupancy_per_car = parse_occupancy_per_car(occ_per_car_json)

        # Detect CIVIS express service (Madrid Cercanías semi-direct trains)
        stop_count = trip_stop_counts.get(trip.id, 0)
        route_short = route.short_name.strip() if route.short_name else ""

        is_express, express_name, express_color = detect_civis(
            route_id=route.id,
            route_short_name=route_short,
            stop_count=stop_count,
            network_id=route.network_id
        )

        departures.append(
            DepartureResponse(
                trip_id=trip.id,
                route_id=route.id,
                route_short_name=route_short,
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
                occupancy_status=occupancy_status,
                occupancy_percentage=occupancy_percent,
                occupancy_per_car=occupancy_per_car,
                is_express=is_express,
                express_name=express_name,
                express_color=express_color,
            )
        )

    # Add frequency-based departures for Metro routes without stop_times
    if frequency_departures:
        departures.extend(frequency_departures)

    # Deduplicate departures with overlapping times (GTFS frequency overlap bug)
    # ONLY deduplicate static entries (no realtime data) - GTFS-RT may have legitimate
    # multiple trains at same time which should NOT be deduplicated
    #
    # Use a minimum gap of 90 seconds between departures of same route+headsign
    # to filter out duplicates caused by overlapping frequency periods in GTFS
    MIN_GAP_SECONDS = 90

    # First, separate realtime and static departures
    realtime_departures = []
    static_departures = []
    for dep in departures:
        if dep.delay_seconds is not None:
            realtime_departures.append(dep)
        else:
            static_departures.append(dep)

    # Sort static departures by departure time
    static_departures.sort(key=lambda d: d.departure_seconds)

    # Deduplicate static departures using minimum time gap
    # Key: (route_short_name, headsign) -> last_departure_seconds
    last_departure_by_route_headsign: dict = {}
    deduplicated_static = []

    for dep in static_departures:
        key = (dep.route_short_name, dep.headsign)
        last_dep_seconds = last_departure_by_route_headsign.get(key)

        # Keep if no previous departure or gap is >= MIN_GAP_SECONDS
        if last_dep_seconds is None or (dep.departure_seconds - last_dep_seconds) >= MIN_GAP_SECONDS:
            deduplicated_static.append(dep)
            last_departure_by_route_headsign[key] = dep.departure_seconds

    # Combine: all realtime departures + deduplicated static departures
    departures = realtime_departures + deduplicated_static

    # Sort by realtime departure (use realtime_minutes_until if available, else minutes_until)
    departures.sort(key=lambda d: d.realtime_minutes_until if d.realtime_minutes_until is not None else d.minutes_until)

    departures = departures[:limit]

    # Return compact response if requested (for widgets/Siri)
    if compact:
        compact_departures = [
            CompactDepartureResponse(
                line=d.route_short_name,
                color=d.route_color,
                dest=d.headsign[:20] if d.headsign else None,  # Truncate to 20 chars
                mins=d.realtime_minutes_until if d.realtime_minutes_until is not None else d.minutes_until,
                plat=d.platform,
                delay=d.is_delayed,
                occ=d.occupancy_status,
                exp=d.is_express,
                exp_color=d.express_color,
            )
            for d in departures
        ]
        return CompactDeparturesWrapper(
            stop_id=stop_id,
            stop_name=stop.name,
            departures=compact_departures,
            updated_at=now,
        )

    return departures


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
    # Normalize to Title Case (some GTFS data has ALL CAPS headsigns)
    headsign = trip.headsign
    if not headsign and stops:
        headsign = stops[-1].stop_name
    headsign = normalize_headsign(headsign)

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


def _get_combined_variant_shape(
    db: Session,
    route_short_name: str,
    variant_shape_id: str,
) -> List[Tuple[float, float, int]]:
    """Get combined shape for route variants (e.g., C4a = C4 base + C4a branch).

    Renfe GTFS exports variant routes (C4a, C4b, C8a, C8b) with shapes that only
    cover the branch section, not the common trunk. This function combines:
    - Base route shape (e.g., 10_C4 for the Parla-Cantoblanco trunk)
    - Variant branch shape (e.g., 10_C4a for Cantoblanco-Alcobendas)

    The shapes are joined at their common endpoint (bifurcation point).
    """
    from src.gtfs_bc.shape.infrastructure.models.shape_model import ShapePointModel
    from adapters.http.api.gtfs.utils.shape_utils import haversine_distance

    # Mapping of variants to their base routes
    # Format: variant_suffix -> base_short_name
    VARIANT_BASES = {
        'C4a': 'C4',
        'C4b': 'C4',
        'C8a': 'C8',
        'C8b': 'C8',
    }

    # Check if this is a variant route
    if route_short_name not in VARIANT_BASES:
        return []

    base_short_name = VARIANT_BASES[route_short_name]

    # Build base shape_id (convention: 10_<base_route>)
    base_shape_id = f"10_{base_short_name}"

    # Get base shape points
    base_points = (
        db.query(ShapePointModel)
        .filter(ShapePointModel.shape_id == base_shape_id)
        .order_by(ShapePointModel.sequence)
        .all()
    )

    if not base_points:
        return []

    # Get variant shape points
    variant_points = (
        db.query(ShapePointModel)
        .filter(ShapePointModel.shape_id == variant_shape_id)
        .order_by(ShapePointModel.sequence)
        .all()
    )

    if not variant_points:
        # Return just base if no variant shape
        return [(p.lat, p.lon, p.sequence) for p in base_points]

    # Find how to connect the shapes
    # Check distances between endpoints to determine connection order
    base_first = (base_points[0].lat, base_points[0].lon)
    base_last = (base_points[-1].lat, base_points[-1].lon)
    var_first = (variant_points[0].lat, variant_points[0].lon)
    var_last = (variant_points[-1].lat, variant_points[-1].lon)

    # Calculate distances between all endpoint combinations
    distances = {
        'base_last_to_var_first': haversine_distance(base_last[0], base_last[1], var_first[0], var_first[1]),
        'base_last_to_var_last': haversine_distance(base_last[0], base_last[1], var_last[0], var_last[1]),
        'base_first_to_var_first': haversine_distance(base_first[0], base_first[1], var_first[0], var_first[1]),
        'base_first_to_var_last': haversine_distance(base_first[0], base_first[1], var_last[0], var_last[1]),
    }

    # Find the closest connection
    min_dist_key = min(distances, key=distances.get)

    # Build combined shape based on closest connection
    combined = []
    seq = 0

    if min_dist_key == 'base_last_to_var_first':
        # Base -> Variant (normal order)
        for p in base_points:
            combined.append((p.lat, p.lon, seq))
            seq += 1
        for p in variant_points[1:]:  # Skip first point (duplicate)
            combined.append((p.lat, p.lon, seq))
            seq += 1

    elif min_dist_key == 'base_last_to_var_last':
        # Base -> Variant (reversed)
        for p in base_points:
            combined.append((p.lat, p.lon, seq))
            seq += 1
        for p in reversed(variant_points[:-1]):  # Skip last point, reverse
            combined.append((p.lat, p.lon, seq))
            seq += 1

    elif min_dist_key == 'base_first_to_var_first':
        # Variant (reversed) -> Base
        for p in reversed(variant_points[1:]):
            combined.append((p.lat, p.lon, seq))
            seq += 1
        for p in base_points:
            combined.append((p.lat, p.lon, seq))
            seq += 1

    else:  # base_first_to_var_last
        # Variant -> Base
        for p in variant_points[:-1]:
            combined.append((p.lat, p.lon, seq))
            seq += 1
        for p in base_points:
            combined.append((p.lat, p.lon, seq))
            seq += 1

    return combined


@router.get("/routes/{route_id}/shape", response_model=RouteShapeResponse)
def get_route_shape(
    route_id: str,
    max_gap: Optional[float] = Query(
        None,
        ge=10,
        le=500,
        description="Maximum gap in meters between points. When set, interpolates points using spherical interpolation (slerp) to ensure smooth curves. Recommended: 50 for 3D animations."
    ),
    db: Session = Depends(get_db),
):
    """Get the shape (path) of a route for drawing on maps.

    Returns the sequence of coordinates that define the physical path
    of the route. Useful for drawing the actual line trajectory on maps
    (showing curves, tunnels, etc.) instead of just straight lines between stops.

    **Variant routes (C4a, C4b, C8a, C8b):**
    For routes with branches, this endpoint automatically combines the base
    trunk shape with the branch shape to return the complete route.

    **Normalization (max_gap parameter):**
    When `max_gap` is specified, the server interpolates additional points
    using spherical linear interpolation (slerp) to ensure no gap between
    consecutive points exceeds the threshold. This is useful for:
    - 3D map animations (smooth camera movements)
    - Accurate distance calculations
    - Preventing visual artifacts from large gaps

    Example: `?max_gap=50` ensures points are at most 50m apart.

    Data source: shapes.txt from GTFS feed.
    """
    from src.gtfs_bc.trip.infrastructure.models import TripModel
    from src.gtfs_bc.shape.infrastructure.models.shape_model import ShapeModel, ShapePointModel

    # Verify route exists
    route = db.query(RouteModel).filter(RouteModel.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail=f"Route {route_id} not found")

    route_short = route.short_name.strip() if route.short_name else ""

    # Get a trip for this route to find its shape_id
    trip = db.query(TripModel).filter(
        TripModel.route_id == route_id,
        TripModel.shape_id.isnot(None)
    ).first()

    if not trip or not trip.shape_id:
        # No shape data for this route
        return RouteShapeResponse(
            route_id=route_id,
            route_short_name=route_short,
            shape=[]
        )

    # Check if this is a variant route that needs combined shapes
    points = []
    if route_short in ('C4a', 'C4b', 'C8a', 'C8b'):
        points = _get_combined_variant_shape(db, route_short, trip.shape_id)

    # If no combined shape (or not a variant), get regular shape
    if not points:
        shape_points = (
            db.query(ShapePointModel)
            .filter(ShapePointModel.shape_id == trip.shape_id)
            .order_by(ShapePointModel.sequence)
            .all()
        )
        points = [(p.lat, p.lon, p.sequence) for p in shape_points]

    # Normalize if max_gap is specified
    if max_gap is not None and points:
        points = normalize_shape(points, max_gap_meters=max_gap)

    return RouteShapeResponse(
        route_id=route_id,
        route_short_name=route_short,
        shape=[
            ShapePointResponse(
                lat=lat,
                lon=lon,
                sequence=seq
            )
            for lat, lon, seq in points
        ]
    )


@router.get("/stops/{stop_id}/platforms", response_model=StopPlatformsResponse)
def get_stop_platforms(
    stop_id: str,
    db: Session = Depends(get_db),
):
    """Get platform coordinates for each line at a stop.

    Returns the specific coordinates for each platform/line at this station.
    Useful for showing walking directions between platforms at interchanges.

    Example response for Nuevos Ministerios:
    - L6: (40.446620, -3.692410)
    - L8: (40.446550, -3.692410)
    - L10: (40.446590, -3.692410)
    - C4a: (40.447100, -3.691800)

    Data sources: GTFS stops.txt, OpenStreetMap, or manual entries.
    """
    # Get stop name
    stop = db.query(StopModel).filter(StopModel.id == stop_id).first()
    if not stop:
        raise HTTPException(status_code=404, detail=f"Stop {stop_id} not found")

    # Get all platforms for this stop
    platforms = db.query(StopPlatformModel).filter(
        StopPlatformModel.stop_id == stop_id
    ).order_by(StopPlatformModel.lines).all()

    # Build response with color lookup from routes if not stored
    platform_responses = []
    for p in platforms:
        resp = PlatformResponse.model_validate(p)
        # If no color in platform, try to get it from the route
        if not resp.color and resp.lines:
            # Get first line (e.g., "L6" from "L6" or "C2" from "C2, C3, C4a")
            first_line = resp.lines.split(",")[0].strip()
            # Find route with this short_name
            route = db.query(RouteModel).filter(
                RouteModel.short_name == first_line
            ).first()
            if route and route.color:
                resp.color = route.color
        platform_responses.append(resp)

    return StopPlatformsResponse(
        stop_id=stop_id,
        stop_name=stop.name,
        platforms=platform_responses
    )


@router.get("/stops/{stop_id}/correspondences", response_model=StopCorrespondencesResponse)
@limiter.limit(RateLimits.CORRESPONDENCES)
def get_stop_correspondences(
    request: Request,
    stop_id: str,
    include_shape: bool = Query(False, description="Include walking route shape (generates on-demand if not cached)"),
    db: Session = Depends(get_db),
):
    """Get walking correspondences to nearby stations.

    Returns stations connected via walking passages (different from platforms
    at the same station). Example: Acacias (L5) ↔ Embajadores (L3, C5).

    These are different stations that share underground walking connections.

    If include_shape=true, returns pedestrian route coordinates for each
    correspondence. Routes are generated on-demand using BRouter and cached
    for subsequent requests.
    """
    # Get stop
    stop = db.query(StopModel).filter(StopModel.id == stop_id).first()
    if not stop:
        raise HTTPException(status_code=404, detail=f"Stop {stop_id} not found")

    # Get correspondences FROM this stop
    correspondences = db.query(StopCorrespondenceModel).filter(
        StopCorrespondenceModel.from_stop_id == stop_id
    ).all()

    result = []
    for corr in correspondences:
        # Get destination stop info
        to_stop = db.query(StopModel).filter(StopModel.id == corr.to_stop_id).first()
        if to_stop:
            # Get all lines at destination (combine all types)
            lines_parts = []
            transport_types = []

            if to_stop.cor_metro:
                lines_parts.append(to_stop.cor_metro)
                transport_types.append("metro")
            if to_stop.cor_cercanias:
                lines_parts.append(to_stop.cor_cercanias)
                transport_types.append("cercanias")
            if to_stop.cor_ml:
                lines_parts.append(to_stop.cor_ml)
                transport_types.append("metro_ligero")
            if to_stop.cor_tranvia:
                lines_parts.append(to_stop.cor_tranvia)
                transport_types.append("tranvia")

            to_lines = ", ".join(lines_parts) if lines_parts else None

            # Handle walking shape
            walking_shape = None
            if include_shape:
                # Check if shape is cached
                if corr.walking_shape:
                    # Parse cached shape
                    coords = json_to_coords(corr.walking_shape)
                    walking_shape = [WalkingShapePoint(lat=lat, lon=lon) for lat, lon in coords]
                else:
                    # Generate shape on-demand using BRouter
                    route_result = generate_walking_route(
                        stop.lat, stop.lon,
                        to_stop.lat, to_stop.lon
                    )
                    if route_result:
                        coords, distance_m, walk_time_s = route_result
                        # Cache the shape and update distance/time
                        corr.walking_shape = coords_to_json(coords)
                        if distance_m and (not corr.distance_m or corr.distance_m == 0):
                            corr.distance_m = distance_m
                        if walk_time_s and (not corr.walk_time_s or corr.walk_time_s == 0):
                            corr.walk_time_s = walk_time_s
                        db.commit()
                        walking_shape = [WalkingShapePoint(lat=lat, lon=lon) for lat, lon in coords]

            result.append(CorrespondenceResponse(
                id=corr.id,
                to_stop_id=corr.to_stop_id,
                to_stop_name=to_stop.name,
                to_lines=to_lines,
                to_transport_types=transport_types,
                distance_m=corr.distance_m,
                walk_time_s=corr.walk_time_s,
                source=corr.source,
                walking_shape=walking_shape
            ))

    return StopCorrespondencesResponse(
        stop_id=stop_id,
        stop_name=stop.name,
        correspondences=result
    )


@router.get("/route-planner", response_model=RoutePlannerResponse)
@limiter.limit(RateLimits.ROUTE_PLANNER)
def plan_route(
    request: Request,
    from_stop: str = Query(..., alias="from", description="Origin stop ID"),
    to_stop: str = Query(..., alias="to", description="Destination stop ID"),
    departure_time: Optional[str] = Query(
        None,
        description="Departure time in HH:MM format or ISO8601. Defaults to current time."
    ),
    max_transfers: int = Query(3, ge=0, le=5, description="Maximum number of transfers allowed"),
    max_alternatives: int = Query(3, ge=1, le=5, description="Maximum number of alternative journeys to return"),
    db: Session = Depends(get_db),
):
    """Plan a route between two stops using RAPTOR algorithm.

    Returns Pareto-optimal journey alternatives, considering:
    - Direct routes on the same line
    - Transfers between lines at the same station
    - Walking transfers between nearby stations
    - Actual departure times from GTFS stop_times

    The algorithm returns up to `max_alternatives` Pareto-optimal journeys,
    where each journey is not dominated by another in all criteria (time, transfers, walking).

    Each journey includes:
    - Exact departure and arrival timestamps
    - Transit segments with line info and coordinates
    - Walking segments with distance
    - Active alerts for affected routes
    - Suggested camera heading for 3D animations

    **Example requests:**
    ```
    GET /gtfs/route-planner?from=METRO_SEV_L1_E21&to=RENFE_43004
    GET /gtfs/route-planner?from=METRO_SEV_L1_E21&to=RENFE_43004&departure_time=08:30
    GET /gtfs/route-planner?from=METRO_SEV_L1_E21&to=RENFE_43004&departure_time=08:30&max_alternatives=5
    ```

    **Use cases:**
    - Journey planning in mobile apps
    - 3D route animations with suggested_heading
    - Multi-modal trip planning
    - Widget/Siri integration (use fewer alternatives)
    """
    from datetime import date, time as dt_time

    # Parse departure_time if provided
    dep_time = None
    if departure_time:
        try:
            # Try HH:MM format first
            if len(departure_time) == 5 and ":" in departure_time:
                parts = departure_time.split(":")
                dep_time = dt_time(int(parts[0]), int(parts[1]))
            else:
                # Try ISO8601 parsing
                from datetime import datetime as dt
                parsed = dt.fromisoformat(departure_time.replace("Z", "+00:00"))
                dep_time = parsed.time()
        except (ValueError, IndexError):
            return RoutePlannerResponse(
                success=False,
                message=f"Invalid departure_time format: {departure_time}. Use HH:MM or ISO8601."
            )

    # Resolve station IDs to platform IDs (for networks like Metro Bilbao)
    # This handles cases where users search by station (METRO_BILBAO_7) but
    # stop_times reference platforms (METRO_BILBAO_7.0)
    real_origins = resolve_stop_to_platforms(from_stop)
    real_destinations = resolve_stop_to_platforms(to_stop)

    # Initialize RAPTOR service
    raptor_service = RaptorService(db)

    # Plan journey (passing lists for multi-platform support)
    result = raptor_service.plan_journey(
        origin_stop_id=real_origins,
        destination_stop_id=real_destinations,
        departure_time=dep_time,
        travel_date=date.today(),
        max_transfers=max_transfers,
        max_alternatives=max_alternatives
    )

    # Convert to response schema
    journeys = []
    for j in result.get("journeys", []):
        segments = []
        for s in j.get("segments", []):
            segments.append(JourneySegmentResponse(
                type=s["type"],
                mode=s["mode"],
                line_id=s.get("line_id"),
                line_name=s.get("line_name"),
                line_color=s.get("line_color"),
                headsign=s.get("headsign"),
                origin=JourneyStopResponse(**s["origin"]),
                destination=JourneyStopResponse(**s["destination"]),
                departure=s["departure"],
                arrival=s["arrival"],
                duration_minutes=s["duration_minutes"],
                intermediate_stops=[JourneyStopResponse(**stop) for stop in s.get("intermediate_stops", [])],
                distance_meters=s.get("distance_meters"),
                coordinates=[JourneyCoordinate(**c) for c in s.get("coordinates", [])],
                suggested_heading=s.get("suggested_heading", 0.0)
            ))

        journeys.append(JourneyResponse(
            departure=j["departure"],
            arrival=j["arrival"],
            duration_minutes=j["duration_minutes"],
            transfers=j["transfers"],
            walking_minutes=j["walking_minutes"],
            segments=segments
        ))

    # Convert alerts
    alerts = []
    for a in result.get("alerts", []):
        alerts.append(JourneyAlertResponse(
            id=a["id"],
            line_id=a["line_id"],
            line_name=a["line_name"],
            message=a["message"],
            severity=a["severity"],
            active_from=a.get("active_from"),
            active_until=a.get("active_until")
        ))

    return RoutePlannerResponse(
        success=result["success"],
        message=result.get("message"),
        journeys=journeys,
        alerts=alerts
    )
