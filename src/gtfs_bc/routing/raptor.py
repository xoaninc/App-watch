"""RAPTOR Algorithm Implementation.

RAPTOR = Round-bAsed Public Transit Optimized Router

This module implements the RAPTOR algorithm for finding optimal journeys
in a public transit network. Based on the paper:
"Round-Based Public Transit Routing" (Delling et al., 2012)

Reference implementation: https://github.com/planarnetwork/raptor

Key concepts:
- Rounds: Each round represents one additional transfer
- Pareto-optimal: Returns journeys that are optimal in at least one criterion
- Time-dependent: Considers actual departure times from stop_times

Author: Claude (Anthropic)
Date: 2026-01-27
"""

import math
from dataclasses import dataclass, field
from datetime import datetime, date, time, timedelta
from typing import Dict, List, Optional, Set, Tuple, NamedTuple
from collections import defaultdict

from sqlalchemy.orm import Session

from src.gtfs_bc.stop.infrastructure.models import StopModel
from src.gtfs_bc.route.infrastructure.models import RouteModel
from src.gtfs_bc.trip.infrastructure.models import TripModel
from src.gtfs_bc.stop_time.infrastructure.models import StopTimeModel
from src.gtfs_bc.calendar.infrastructure.models import CalendarModel
from src.gtfs_bc.stop_route_sequence.infrastructure.models import StopRouteSequenceModel
from src.gtfs_bc.stop.infrastructure.models.stop_correspondence_model import StopCorrespondenceModel


# =============================================================================
# Constants
# =============================================================================

MAX_ROUNDS = 5  # Maximum number of transfers + 1
INFINITY = float('inf')
WALKING_SPEED_KMH = 4.5
TRANSFER_PENALTY_SECONDS = 180  # 3 minutes penalty for each transfer


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class StopTime:
    """A single stop time event (arrival/departure at a stop)."""
    trip_id: str
    stop_id: str
    stop_sequence: int
    arrival_seconds: int  # Seconds since midnight
    departure_seconds: int


@dataclass
class Trip:
    """A trip with its stop times."""
    trip_id: str
    route_id: str
    service_id: str
    headsign: Optional[str]
    stop_times: List[StopTime] = field(default_factory=list)


@dataclass
class Transfer:
    """A walking transfer between two stops."""
    from_stop_id: str
    to_stop_id: str
    walk_seconds: int


@dataclass
class RoutePattern:
    """A pattern of stops for a route (sequence of stop_ids)."""
    route_id: str
    stops: List[str]  # Ordered list of stop_ids
    trips: List[Trip] = field(default_factory=list)


@dataclass
class Label:
    """Arrival label at a stop for a specific round.

    Tracks the earliest arrival time and how we got there.
    """
    arrival_time: int  # Seconds since midnight
    trip_id: Optional[str] = None
    boarding_stop_id: Optional[str] = None
    boarding_time: Optional[int] = None
    route_id: Optional[str] = None
    is_transfer: bool = False
    from_stop_id: Optional[str] = None  # For transfers


@dataclass
class Journey:
    """A complete journey from origin to destination."""
    departure_time: int  # Seconds since midnight
    arrival_time: int  # Seconds since midnight
    transfers: int
    legs: List['JourneyLeg'] = field(default_factory=list)

    @property
    def duration_seconds(self) -> int:
        return self.arrival_time - self.departure_time

    @property
    def duration_minutes(self) -> int:
        return self.duration_seconds // 60


@dataclass
class JourneyLeg:
    """A single leg of a journey (transit or walking)."""
    type: str  # "transit" or "walking"
    from_stop_id: str
    to_stop_id: str
    departure_time: int  # Seconds since midnight
    arrival_time: int  # Seconds since midnight
    route_id: Optional[str] = None
    trip_id: Optional[str] = None
    headsign: Optional[str] = None
    intermediate_stops: List[str] = field(default_factory=list)


# =============================================================================
# RAPTOR Algorithm
# =============================================================================

class RaptorAlgorithm:
    """RAPTOR journey planner.

    Finds Pareto-optimal journeys between two stops, considering:
    - Arrival time (minimize)
    - Number of transfers (minimize)
    """

    def __init__(self, db: Session):
        self.db = db
        self._data_loaded = False

        # Data structures populated by _load_data()
        self._stops: Dict[str, StopModel] = {}
        self._routes: Dict[str, RouteModel] = {}
        self._route_patterns: Dict[str, RoutePattern] = {}  # route_id -> RoutePattern
        self._stop_routes: Dict[str, Set[str]] = defaultdict(set)  # stop_id -> set of route_ids
        self._transfers: Dict[str, List[Transfer]] = defaultdict(list)  # from_stop_id -> [Transfer]
        self._trips_by_route: Dict[str, List[Trip]] = defaultdict(list)  # route_id -> [Trip] sorted by departure

    def _load_data(self, travel_date: date) -> None:
        """Load all required data from the database.

        Args:
            travel_date: The date of travel (for calendar filtering)
        """
        if self._data_loaded:
            return

        # Load stops
        stops = self.db.query(StopModel).all()
        self._stops = {s.id: s for s in stops}

        # Load routes
        routes = self.db.query(RouteModel).all()
        self._routes = {r.id: r for r in routes}

        # Load trips and stop_times for the given date
        self._load_trips(travel_date)

        # Build route patterns from loaded trips (ensures correct travel direction)
        self._build_route_patterns_from_trips()

        # Load transfers (walking connections)
        self._load_transfers()

        self._data_loaded = True

    def _load_route_patterns(self) -> None:
        """Load route patterns from stop_times data.

        Instead of using stop_route_sequence (geometry order), we derive
        route patterns from actual trip stop_times. This ensures correct
        travel order for each route.
        """
        # This method now does nothing - patterns will be derived from trips
        # in _load_trips after we have the actual stop_times data.
        pass

    def _build_route_patterns_from_trips(self) -> None:
        """Build route patterns from loaded trip data.

        Each trip defines a stop sequence. Routes can have trips going
        in opposite directions, so we create a pattern for EACH unique
        stop sequence (identified by route_id + direction hash).
        """
        # Group stop sequences by route
        route_sequences: Dict[str, Dict[tuple, int]] = defaultdict(lambda: defaultdict(int))

        for route_id, trips in self._trips_by_route.items():
            for trip in trips:
                # Get the stop sequence for this trip
                stop_seq = tuple(st.stop_id for st in trip.stop_times)
                route_sequences[route_id][stop_seq] += 1

        # Create a pattern for each unique stop sequence
        # Use pattern_id = route_id + "_dir_" + hash to distinguish directions
        for route_id, sequences in route_sequences.items():
            if not sequences:
                continue

            for idx, (stop_seq, count) in enumerate(sorted(sequences.items(), key=lambda x: -x[1])):
                # Create pattern ID that includes direction
                pattern_id = f"{route_id}_dir_{idx}" if len(sequences) > 1 else route_id

                self._route_patterns[pattern_id] = RoutePattern(
                    route_id=route_id,  # Original route_id for display
                    stops=list(stop_seq)
                )

                # Update stop->route mapping (use pattern_id so algorithm can find it)
                for stop_id in stop_seq:
                    self._stop_routes[stop_id].add(pattern_id)

                # Also update _trips_by_route to use pattern_id
                # Move trips that match this pattern to the pattern_id
                if pattern_id != route_id:
                    if pattern_id not in self._trips_by_route:
                        self._trips_by_route[pattern_id] = []

                    # Find trips that match this pattern and move them
                    original_trips = self._trips_by_route.get(route_id, [])
                    for trip in original_trips[:]:  # Copy list to modify
                        trip_seq = tuple(st.stop_id for st in trip.stop_times)
                        if trip_seq == stop_seq:
                            self._trips_by_route[pattern_id].append(trip)

            # Clean up: if we created sub-patterns, remove trips from original route_id
            if len(sequences) > 1:
                # Keep only the trips in sub-patterns
                self._trips_by_route[route_id] = []

    def _load_trips(self, travel_date: date) -> None:
        """Load trips and their stop times for a specific date.

        Args:
            travel_date: The date to get active services for
        """
        # Get day of week
        day_of_week = travel_date.weekday()  # 0=Monday, 6=Sunday
        day_columns = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        day_column = day_columns[day_of_week]

        # Get active service_ids for this date
        # This is simplified - a full implementation would also check calendar_dates
        calendars = (
            self.db.query(CalendarModel)
            .filter(CalendarModel.start_date <= travel_date)
            .filter(CalendarModel.end_date >= travel_date)
            .all()
        )

        active_service_ids = set()
        for cal in calendars:
            if getattr(cal, day_column, False):
                active_service_ids.add(cal.service_id)

        if not active_service_ids:
            return

        # Load trips for active services
        trips = (
            self.db.query(TripModel)
            .filter(TripModel.service_id.in_(active_service_ids))
            .all()
        )

        trip_ids = [t.id for t in trips]
        trips_dict = {t.id: t for t in trips}

        # Load stop times for these trips
        stop_times = (
            self.db.query(StopTimeModel)
            .filter(StopTimeModel.trip_id.in_(trip_ids))
            .order_by(StopTimeModel.trip_id, StopTimeModel.stop_sequence)
            .all()
        )

        # Group stop times by trip
        trip_stop_times: Dict[str, List[StopTime]] = defaultdict(list)
        for st in stop_times:
            trip_stop_times[st.trip_id].append(StopTime(
                trip_id=st.trip_id,
                stop_id=st.stop_id,
                stop_sequence=st.stop_sequence,
                arrival_seconds=st.arrival_seconds or 0,
                departure_seconds=st.departure_seconds or 0
            ))

        # Create Trip objects and group by route
        for trip_id, trip_model in trips_dict.items():
            if trip_id not in trip_stop_times:
                continue

            trip = Trip(
                trip_id=trip_id,
                route_id=trip_model.route_id,
                service_id=trip_model.service_id,
                headsign=trip_model.headsign,
                stop_times=trip_stop_times[trip_id]
            )
            self._trips_by_route[trip_model.route_id].append(trip)

        # Sort trips by first departure time
        for route_id in self._trips_by_route:
            self._trips_by_route[route_id].sort(
                key=lambda t: t.stop_times[0].departure_seconds if t.stop_times else INFINITY
            )

    def _load_transfers(self) -> None:
        """Load walking transfers from stop_correspondence table."""
        correspondences = (
            self.db.query(StopCorrespondenceModel)
            .filter(StopCorrespondenceModel.walk_time_s.isnot(None))
            .all()
        )

        for corr in correspondences:
            self._transfers[corr.from_stop_id].append(Transfer(
                from_stop_id=corr.from_stop_id,
                to_stop_id=corr.to_stop_id,
                walk_seconds=corr.walk_time_s
            ))

    def plan(
        self,
        origin_stop_id: str,
        destination_stop_id: str,
        departure_time: time,
        travel_date: date,
        max_transfers: int = 3
    ) -> List[Journey]:
        """Find optimal journeys from origin to destination.

        Args:
            origin_stop_id: Starting stop ID
            destination_stop_id: Destination stop ID
            departure_time: Earliest departure time
            travel_date: Date of travel
            max_transfers: Maximum number of transfers allowed

        Returns:
            List of Pareto-optimal journeys
        """
        # Load data if not already loaded
        self._load_data(travel_date)

        # Validate stops
        if origin_stop_id not in self._stops:
            raise ValueError(f"Origin stop not found: {origin_stop_id}")
        if destination_stop_id not in self._stops:
            raise ValueError(f"Destination stop not found: {destination_stop_id}")

        # Convert departure time to seconds since midnight
        departure_seconds = departure_time.hour * 3600 + departure_time.minute * 60 + departure_time.second

        # Run RAPTOR algorithm
        rounds = min(max_transfers + 1, MAX_ROUNDS)
        labels = self._run_raptor(origin_stop_id, destination_stop_id, departure_seconds, rounds)

        # Extract journeys from labels
        journeys = self._extract_journeys(
            labels, origin_stop_id, destination_stop_id, departure_seconds
        )

        # Apply Pareto filter
        journeys = self._pareto_filter(journeys)

        return journeys

    def _run_raptor(
        self,
        origin_stop_id: str,
        destination_stop_id: str,
        departure_seconds: int,
        max_rounds: int
    ) -> Dict[int, Dict[str, Label]]:
        """Run the RAPTOR algorithm.

        Args:
            origin_stop_id: Starting stop
            destination_stop_id: Destination stop
            departure_seconds: Departure time in seconds since midnight
            max_rounds: Maximum number of rounds (transfers + 1)

        Returns:
            Dictionary of round -> stop_id -> Label
        """
        # Initialize labels for each round
        # labels[k][stop_id] = earliest arrival at stop in round k
        labels: Dict[int, Dict[str, Label]] = {k: {} for k in range(max_rounds + 1)}

        # Best overall arrival time at each stop (across all rounds)
        best_arrival: Dict[str, int] = defaultdict(lambda: INFINITY)

        # Initialize round 0 with origin
        labels[0][origin_stop_id] = Label(arrival_time=departure_seconds)
        best_arrival[origin_stop_id] = departure_seconds

        # Marked stops (stops improved in previous round)
        marked_stops: Set[str] = {origin_stop_id}

        # Run rounds
        for k in range(1, max_rounds + 1):
            if not marked_stops:
                break

            # Copy previous round's labels
            for stop_id, label in labels[k - 1].items():
                if stop_id not in labels[k] or label.arrival_time < labels[k][stop_id].arrival_time:
                    labels[k][stop_id] = Label(arrival_time=label.arrival_time)

            new_marked_stops: Set[str] = set()

            # Step 1: Scan routes that serve marked stops
            routes_to_scan = set()
            for stop_id in marked_stops:
                routes_to_scan.update(self._stop_routes.get(stop_id, set()))

            for route_id in routes_to_scan:
                pattern = self._route_patterns.get(route_id)
                if not pattern:
                    continue

                trips = self._trips_by_route.get(route_id, [])
                if not trips:
                    continue

                # Scan this route
                improved = self._scan_route(
                    pattern, trips, labels[k - 1], labels[k],
                    best_arrival, marked_stops, k
                )
                new_marked_stops.update(improved)

            # Step 2: Process transfers (walking)
            for stop_id in list(new_marked_stops) + list(marked_stops):
                if stop_id not in labels[k]:
                    continue

                arrival_at_stop = labels[k][stop_id].arrival_time

                for transfer in self._transfers.get(stop_id, []):
                    arrival_after_walk = arrival_at_stop + transfer.walk_seconds + TRANSFER_PENALTY_SECONDS

                    if arrival_after_walk < best_arrival[transfer.to_stop_id]:
                        if transfer.to_stop_id not in labels[k] or arrival_after_walk < labels[k][transfer.to_stop_id].arrival_time:
                            labels[k][transfer.to_stop_id] = Label(
                                arrival_time=arrival_after_walk,
                                is_transfer=True,
                                from_stop_id=stop_id
                            )
                            best_arrival[transfer.to_stop_id] = arrival_after_walk
                            new_marked_stops.add(transfer.to_stop_id)

            marked_stops = new_marked_stops

        return labels

    def _scan_route(
        self,
        pattern: RoutePattern,
        trips: List[Trip],
        prev_labels: Dict[str, Label],
        curr_labels: Dict[str, Label],
        best_arrival: Dict[str, int],
        marked_stops: Set[str],
        round_num: int
    ) -> Set[str]:
        """Scan a single route for improvements.

        Args:
            pattern: The route pattern (stop sequence)
            trips: Available trips on this route
            prev_labels: Labels from previous round
            curr_labels: Labels for current round (to update)
            best_arrival: Best arrival times across all rounds
            marked_stops: Stops that were improved in previous round
            round_num: Current round number

        Returns:
            Set of stop_ids that were improved
        """
        improved_stops: Set[str] = set()

        # Find first marked stop in this route's pattern
        board_stop_idx = None
        for idx, stop_id in enumerate(pattern.stops):
            if stop_id in marked_stops and stop_id in prev_labels:
                board_stop_idx = idx
                break

        if board_stop_idx is None:
            return improved_stops

        # Try to board at each marked stop and ride
        current_trip: Optional[Trip] = None
        boarding_time: Optional[int] = None
        boarding_stop_id: Optional[str] = None
        boarding_stop_idx: Optional[int] = None

        for idx in range(board_stop_idx, len(pattern.stops)):
            stop_id = pattern.stops[idx]

            # Can we board here?
            if stop_id in prev_labels:
                arrival_at_stop = prev_labels[stop_id].arrival_time

                # Find earliest trip we can board
                new_trip = self._find_earliest_trip(trips, stop_id, idx, arrival_at_stop)

                if new_trip:
                    if current_trip is None:
                        # First boarding
                        current_trip = new_trip
                        boarding_stop_id = stop_id
                        boarding_stop_idx = idx
                        boarding_time = arrival_at_stop
                    elif self._trip_arrives_earlier(new_trip, current_trip, idx, pattern.stops):
                        # Switch to earlier trip
                        current_trip = new_trip
                        boarding_stop_id = stop_id
                        boarding_stop_idx = idx
                        boarding_time = arrival_at_stop

            # If we're on a trip, check if we improve arrival at this stop
            if current_trip and boarding_stop_id:
                arrival_time = self._get_arrival_time_with_boarding(
                    current_trip, stop_id, boarding_stop_id
                )

                if arrival_time is not None and arrival_time < best_arrival[stop_id]:
                    # Found improvement
                    if stop_id not in curr_labels or arrival_time < curr_labels[stop_id].arrival_time:
                        curr_labels[stop_id] = Label(
                            arrival_time=arrival_time,
                            trip_id=current_trip.trip_id,
                            boarding_stop_id=boarding_stop_id,
                            boarding_time=boarding_time,
                            route_id=pattern.route_id
                        )
                        best_arrival[stop_id] = arrival_time
                        improved_stops.add(stop_id)

        return improved_stops

    def _find_earliest_trip(
        self,
        trips: List[Trip],
        stop_id: str,
        stop_idx: int,
        min_departure: int
    ) -> Optional[Trip]:
        """Find the earliest trip departing from a stop after a given time.

        Args:
            trips: List of trips sorted by departure time
            stop_id: The stop to board at
            stop_idx: Index of the stop in the route pattern
            min_departure: Minimum departure time (seconds since midnight)

        Returns:
            The earliest valid trip, or None
        """
        for trip in trips:
            # Find this stop in the trip's stop_times
            for st in trip.stop_times:
                if st.stop_id == stop_id:
                    if st.departure_seconds >= min_departure:
                        return trip
                    break
        return None

    def _trip_arrives_earlier(
        self,
        trip1: Trip,
        trip2: Trip,
        stop_idx: int,
        route_stops: List[str]
    ) -> bool:
        """Check if trip1 arrives earlier than trip2 at subsequent stops."""
        # Compare arrival at the next stop
        if stop_idx + 1 < len(route_stops):
            next_stop = route_stops[stop_idx + 1]
            arr1 = self._get_arrival_time(trip1, next_stop, stop_idx + 1)
            arr2 = self._get_arrival_time(trip2, next_stop, stop_idx + 1)
            if arr1 is not None and arr2 is not None:
                return arr1 < arr2
        return False

    def _get_arrival_time_with_boarding(
        self,
        trip: Trip,
        stop_id: str,
        boarding_stop_id: Optional[str]
    ) -> Optional[int]:
        """Get arrival time at a stop for a trip, ensuring correct direction.

        Args:
            trip: The trip to check
            stop_id: The stop to get arrival time for
            boarding_stop_id: The stop where we boarded (must come before stop_id in trip)

        Returns:
            Arrival time in seconds, or None if stop not found or wrong direction
        """
        boarding_seq = None
        stop_seq = None
        arrival_time = None

        for st in trip.stop_times:
            if st.stop_id == boarding_stop_id:
                boarding_seq = st.stop_sequence
            if st.stop_id == stop_id:
                stop_seq = st.stop_sequence
                arrival_time = st.arrival_seconds

        # Only return if destination comes AFTER boarding in the trip
        if boarding_seq is not None and stop_seq is not None and stop_seq > boarding_seq:
            return arrival_time
        elif boarding_stop_id is None:
            # No boarding yet, just return the arrival time if found
            return arrival_time if stop_seq is not None else None

        return None

    def _get_arrival_time(self, trip: Trip, stop_id: str, expected_idx: int) -> Optional[int]:
        """Get arrival time at a stop for a trip (legacy, use _get_arrival_time_with_boarding)."""
        for st in trip.stop_times:
            if st.stop_id == stop_id:
                return st.arrival_seconds
        return None

    def _extract_journeys(
        self,
        labels: Dict[int, Dict[str, Label]],
        origin_stop_id: str,
        destination_stop_id: str,
        departure_seconds: int
    ) -> List[Journey]:
        """Extract journeys from the labels.

        Args:
            labels: Labels computed by RAPTOR
            origin_stop_id: Starting stop
            destination_stop_id: Destination stop
            departure_seconds: Original departure time

        Returns:
            List of journeys (one per round that reached destination)
        """
        journeys: List[Journey] = []

        for round_num, round_labels in labels.items():
            if destination_stop_id not in round_labels:
                continue

            label = round_labels[destination_stop_id]
            if label.arrival_time >= INFINITY:
                continue

            # Reconstruct journey by backtracking
            legs = self._reconstruct_legs(labels, destination_stop_id, round_num, origin_stop_id)

            if legs:
                journey = Journey(
                    departure_time=departure_seconds,
                    arrival_time=label.arrival_time,
                    transfers=max(0, round_num - 1),
                    legs=legs
                )
                journeys.append(journey)

        return journeys

    def _reconstruct_legs(
        self,
        labels: Dict[int, Dict[str, Label]],
        destination_stop_id: str,
        round_num: int,
        origin_stop_id: str
    ) -> List[JourneyLeg]:
        """Reconstruct the journey legs by backtracking through labels."""
        legs: List[JourneyLeg] = []

        current_stop = destination_stop_id
        current_round = round_num

        while current_stop != origin_stop_id and current_round >= 0:
            if current_stop not in labels[current_round]:
                break

            label = labels[current_round][current_stop]

            if label.is_transfer:
                # Walking leg
                from_stop = label.from_stop_id
                if from_stop:
                    # Get arrival time at from_stop
                    from_arrival = labels[current_round].get(from_stop, Label(arrival_time=0)).arrival_time

                    legs.append(JourneyLeg(
                        type="walking",
                        from_stop_id=from_stop,
                        to_stop_id=current_stop,
                        departure_time=from_arrival,
                        arrival_time=label.arrival_time
                    ))
                    current_stop = from_stop
            elif label.boarding_stop_id:
                # Transit leg
                # Look up actual departure time from trip's stop_times
                actual_departure = label.boarding_time or 0
                if label.trip_id and label.route_id:
                    trips = self._trips_by_route.get(label.route_id, [])
                    for trip in trips:
                        if trip.trip_id == label.trip_id:
                            for st in trip.stop_times:
                                if st.stop_id == label.boarding_stop_id:
                                    actual_departure = st.departure_seconds
                                    break
                            break

                legs.append(JourneyLeg(
                    type="transit",
                    from_stop_id=label.boarding_stop_id,
                    to_stop_id=current_stop,
                    departure_time=actual_departure,
                    arrival_time=label.arrival_time,
                    route_id=label.route_id,
                    trip_id=label.trip_id
                ))
                current_stop = label.boarding_stop_id
                current_round -= 1
            else:
                # Origin
                break

        # Reverse to get legs in order
        legs.reverse()
        return legs

    def _pareto_filter(self, journeys: List[Journey]) -> List[Journey]:
        """Filter journeys to keep only Pareto-optimal ones.

        A journey is Pareto-optimal if no other journey is better in ALL criteria:
        - arrival_time (earlier is better)
        - transfers (fewer is better)

        Args:
            journeys: List of journeys to filter

        Returns:
            Pareto-optimal journeys
        """
        if len(journeys) <= 1:
            return journeys

        # Sort by arrival time
        sorted_journeys = sorted(journeys, key=lambda j: (j.arrival_time, j.transfers))

        pareto_optimal: List[Journey] = []

        for journey in sorted_journeys:
            # Check if this journey is dominated by any in pareto_optimal
            is_dominated = False
            for other in pareto_optimal:
                if (other.arrival_time <= journey.arrival_time and
                    other.transfers <= journey.transfers and
                    (other.arrival_time < journey.arrival_time or other.transfers < journey.transfers)):
                    is_dominated = True
                    break

            if not is_dominated:
                # Remove any journeys dominated by this one
                pareto_optimal = [
                    j for j in pareto_optimal
                    if not (journey.arrival_time <= j.arrival_time and
                            journey.transfers <= j.transfers and
                            (journey.arrival_time < j.arrival_time or journey.transfers < j.transfers))
                ]
                pareto_optimal.append(journey)

        # Limit to 3 journeys
        return pareto_optimal[:3]
