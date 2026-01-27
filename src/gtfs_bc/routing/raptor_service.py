"""RAPTOR Service - High-level interface for RAPTOR journey planning.

This service wraps the RAPTOR algorithm and provides:
- Formatted responses with full stop/route details
- Coordinate arrays for map display
- Suggested heading for 3D animations
- Active alerts for routes used in journeys

Author: Claude (Anthropic)
Date: 2026-01-27
"""

import math
from datetime import datetime, date, time, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from src.gtfs_bc.routing.raptor import RaptorAlgorithm, Journey, JourneyLeg
from src.gtfs_bc.stop.infrastructure.models import StopModel
from src.gtfs_bc.route.infrastructure.models import RouteModel
from src.gtfs_bc.trip.infrastructure.models import TripModel
from src.gtfs_bc.shape.infrastructure.models.shape_model import ShapePointModel
from src.gtfs_bc.realtime.infrastructure.models.alert import AlertModel
from adapters.http.api.gtfs.utils.shape_utils import normalize_shape


def calculate_heading(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate bearing between two points.

    Args:
        lat1, lon1: First point coordinates
        lat2, lon2: Second point coordinates

    Returns:
        Bearing in degrees (0-360, where 0=North, 90=East, 180=South, 270=West)
    """
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)

    bearing = math.atan2(x, y)
    bearing = math.degrees(bearing)
    bearing = (bearing + 360) % 360

    return round(bearing, 1)


def seconds_to_iso(seconds: int, base_date: date) -> str:
    """Convert seconds since midnight to ISO8601 datetime string."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    # Handle times past midnight (e.g., 25:30:00)
    days_offset = hours // 24
    hours = hours % 24

    dt = datetime.combine(base_date, time(hours, minutes, secs))
    if days_offset > 0:
        dt += timedelta(days=days_offset)

    return dt.isoformat()


class RaptorService:
    """High-level service for RAPTOR journey planning."""

    def __init__(self, db: Session):
        self.db = db
        self._raptor = RaptorAlgorithm(db)

        # Caches
        self._stops_cache: Dict[str, StopModel] = {}
        self._routes_cache: Dict[str, RouteModel] = {}
        self._trips_cache: Dict[str, TripModel] = {}

    def _get_stop(self, stop_id: str) -> Optional[StopModel]:
        """Get stop from cache or database."""
        if stop_id not in self._stops_cache:
            stop = self.db.query(StopModel).filter(StopModel.id == stop_id).first()
            if stop:
                self._stops_cache[stop_id] = stop
        return self._stops_cache.get(stop_id)

    def _get_route(self, route_id: str) -> Optional[RouteModel]:
        """Get route from cache or database."""
        if route_id not in self._routes_cache:
            route = self.db.query(RouteModel).filter(RouteModel.id == route_id).first()
            if route:
                self._routes_cache[route_id] = route
        return self._routes_cache.get(route_id)

    def _get_trip(self, trip_id: str) -> Optional[TripModel]:
        """Get trip from cache or database."""
        if trip_id not in self._trips_cache:
            trip = self.db.query(TripModel).filter(TripModel.id == trip_id).first()
            if trip:
                self._trips_cache[trip_id] = trip
        return self._trips_cache.get(trip_id)

    def _format_stop(self, stop_id: str) -> dict:
        """Format stop for API response."""
        stop = self._get_stop(stop_id)
        if not stop:
            return {"id": stop_id, "name": stop_id, "lat": 0, "lon": 0}

        return {
            "id": stop.id,
            "name": stop.name,
            "lat": float(stop.lat) if stop.lat else 0,
            "lon": float(stop.lon) if stop.lon else 0
        }

    def _get_route_type_name(self, route_type: int) -> str:
        """Convert GTFS route_type to readable name."""
        type_names = {
            0: "tram",
            1: "metro",
            2: "cercanias",
            3: "bus",
            4: "ferry",
            5: "cable_car",
            6: "gondola",
            7: "funicular",
            11: "trolleybus",
            12: "monorail"
        }
        return type_names.get(route_type, "transit")

    def _get_shape_coordinates(
        self,
        route_id: str,
        from_stop_id: str,
        to_stop_id: str,
        max_gap: float = 50.0
    ) -> List[dict]:
        """Get shape coordinates for a route segment.

        Args:
            route_id: Route ID
            from_stop_id: Starting stop
            to_stop_id: Ending stop
            max_gap: Maximum gap for normalization (meters)

        Returns:
            List of coordinate dicts with lat/lon
        """
        # For now, return straight line between stops
        # TODO: Implement actual shape segment extraction
        from_stop = self._get_stop(from_stop_id)
        to_stop = self._get_stop(to_stop_id)

        if not from_stop or not to_stop:
            return []

        coords = [
            {"lat": float(from_stop.lat), "lon": float(from_stop.lon)},
            {"lat": float(to_stop.lat), "lon": float(to_stop.lon)}
        ]

        return coords

    def _get_walking_coordinates(
        self,
        from_stop_id: str,
        to_stop_id: str
    ) -> List[dict]:
        """Get coordinates for walking segment (straight line)."""
        from_stop = self._get_stop(from_stop_id)
        to_stop = self._get_stop(to_stop_id)

        if not from_stop or not to_stop:
            return []

        return [
            {"lat": float(from_stop.lat), "lon": float(from_stop.lon)},
            {"lat": float(to_stop.lat), "lon": float(to_stop.lon)}
        ]

    def _calculate_segment_heading(self, coordinates: List[dict]) -> float:
        """Calculate suggested heading for a segment."""
        if len(coordinates) < 2:
            return 0.0

        first = coordinates[0]
        last = coordinates[-1]

        return calculate_heading(
            first["lat"], first["lon"],
            last["lat"], last["lon"]
        )

    def _get_active_alerts(self, route_ids: List[str], travel_date: date) -> List[dict]:
        """Get active alerts for the given routes.

        Args:
            route_ids: List of route IDs used in journeys
            travel_date: Date of travel

        Returns:
            List of alert dicts
        """
        if not route_ids:
            return []

        now = datetime.now()

        # Query active alerts
        # Note: This assumes AlertModel has these fields - adjust as needed
        try:
            alerts = (
                self.db.query(AlertModel)
                .filter(AlertModel.route_id.in_(route_ids))
                .filter(AlertModel.active_from <= now)
                .filter(AlertModel.active_until >= now)
                .all()
            )

            return [
                {
                    "id": str(alert.id),
                    "line_id": alert.route_id,
                    "line_name": self._get_route(alert.route_id).short_name if self._get_route(alert.route_id) else "",
                    "message": alert.message,
                    "severity": alert.severity or "info",
                    "active_from": alert.active_from.isoformat() if alert.active_from else None,
                    "active_until": alert.active_until.isoformat() if alert.active_until else None
                }
                for alert in alerts
            ]
        except Exception:
            # If alerts table doesn't exist or has different schema, return empty
            return []

    def _format_leg(self, leg: JourneyLeg, travel_date: date) -> dict:
        """Format a journey leg for API response."""
        from_stop = self._format_stop(leg.from_stop_id)
        to_stop = self._format_stop(leg.to_stop_id)

        result = {
            "type": leg.type,
            "origin": from_stop,
            "destination": to_stop,
            "departure": seconds_to_iso(leg.departure_time, travel_date),
            "arrival": seconds_to_iso(leg.arrival_time, travel_date),
            "duration_minutes": (leg.arrival_time - leg.departure_time) // 60
        }

        if leg.type == "transit":
            route = self._get_route(leg.route_id) if leg.route_id else None
            trip = self._get_trip(leg.trip_id) if leg.trip_id else None

            result["mode"] = self._get_route_type_name(route.route_type) if route else "transit"
            result["line_id"] = leg.route_id
            result["line_name"] = route.short_name if route else ""
            result["line_color"] = route.color if route else "888888"
            result["headsign"] = leg.headsign or (trip.headsign if trip else "")
            result["intermediate_stops"] = [
                self._format_stop(stop_id) for stop_id in leg.intermediate_stops
            ]

            # Get coordinates
            coordinates = self._get_shape_coordinates(
                leg.route_id, leg.from_stop_id, leg.to_stop_id
            )
            result["coordinates"] = coordinates
            result["suggested_heading"] = self._calculate_segment_heading(coordinates)
        else:
            # Walking
            result["mode"] = "walking"
            result["line_id"] = None
            result["line_name"] = None
            result["line_color"] = None
            result["headsign"] = None
            result["intermediate_stops"] = []

            # Calculate distance
            from_s = self._get_stop(leg.from_stop_id)
            to_s = self._get_stop(leg.to_stop_id)
            if from_s and to_s:
                from adapters.http.api.gtfs.utils.shape_utils import haversine_distance
                dist = haversine_distance(from_s.lat, from_s.lon, to_s.lat, to_s.lon)
                result["distance_meters"] = int(dist)
            else:
                result["distance_meters"] = 0

            coordinates = self._get_walking_coordinates(leg.from_stop_id, leg.to_stop_id)
            result["coordinates"] = coordinates
            result["suggested_heading"] = self._calculate_segment_heading(coordinates)

        return result

    def _format_journey(self, journey: Journey, travel_date: date) -> dict:
        """Format a journey for API response."""
        # Calculate walking time
        walking_seconds = sum(
            leg.arrival_time - leg.departure_time
            for leg in journey.legs
            if leg.type == "walking"
        )

        return {
            "departure": seconds_to_iso(journey.departure_time, travel_date),
            "arrival": seconds_to_iso(journey.arrival_time, travel_date),
            "duration_minutes": journey.duration_minutes,
            "transfers": journey.transfers,
            "walking_minutes": walking_seconds // 60,
            "segments": [self._format_leg(leg, travel_date) for leg in journey.legs]
        }

    def plan_journey(
        self,
        origin_stop_id: str,
        destination_stop_id: str,
        departure_time: Optional[time] = None,
        travel_date: Optional[date] = None,
        max_transfers: int = 3,
        max_alternatives: int = 3
    ) -> dict:
        """Plan journeys between two stops.

        Args:
            origin_stop_id: Starting stop ID
            destination_stop_id: Destination stop ID
            departure_time: Departure time (defaults to now)
            travel_date: Travel date (defaults to today)
            max_transfers: Maximum transfers allowed
            max_alternatives: Maximum alternatives to return

        Returns:
            API response dict with journeys and alerts
        """
        # Defaults
        if travel_date is None:
            travel_date = date.today()
        if departure_time is None:
            departure_time = datetime.now().time()

        # Run RAPTOR
        try:
            journeys = self._raptor.plan(
                origin_stop_id=origin_stop_id,
                destination_stop_id=destination_stop_id,
                departure_time=departure_time,
                travel_date=travel_date,
                max_transfers=max_transfers
            )
        except ValueError as e:
            return {
                "success": False,
                "message": str(e),
                "journeys": [],
                "alerts": []
            }

        if not journeys:
            return {
                "success": False,
                "message": f"No route found from {origin_stop_id} to {destination_stop_id}",
                "journeys": [],
                "alerts": []
            }

        # Limit alternatives
        journeys = journeys[:max_alternatives]

        # Format journeys
        formatted_journeys = [
            self._format_journey(j, travel_date) for j in journeys
        ]

        # Collect route IDs for alerts
        route_ids = set()
        for journey in journeys:
            for leg in journey.legs:
                if leg.route_id:
                    route_ids.add(leg.route_id)

        # Get alerts
        alerts = self._get_active_alerts(list(route_ids), travel_date)

        return {
            "success": True,
            "message": None,
            "journeys": formatted_journeys,
            "alerts": alerts
        }
