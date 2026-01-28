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

from dataclasses import dataclass, field
from datetime import date, time
from typing import Dict, List, Optional, Set
from collections import defaultdict

from src.gtfs_bc.routing.gtfs_store import gtfs_store


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

    Uses GTFSStore singleton for in-memory data access (no SQL queries).
    """

    def __init__(self, db=None):
        """Initialize RAPTOR algorithm.

        Args:
            db: Deprecated - kept for backwards compatibility. Not used.
        """
        self.store = gtfs_store
        self._travel_date: Optional[date] = None
        self._active_services: Set[str] = set()

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
        # Get active services for this date from GTFSStore
        self._travel_date = travel_date
        self._active_services = self.store.get_active_services(travel_date)

        # Validate stops using GTFSStore
        if origin_stop_id not in self.store.stops_info:
            raise ValueError(f"Origin stop not found: {origin_stop_id}")
        if destination_stop_id not in self.store.stops_info:
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

            # Copy previous round's labels (referencia directa, no crear objeto nuevo)
            for stop_id, label in labels[k - 1].items():
                if stop_id not in labels[k] or label.arrival_time < labels[k][stop_id].arrival_time:
                    labels[k][stop_id] = label

            new_marked_stops: Set[str] = set()

            # Step 1: Scan PATTERNS that serve marked stops (using GTFSStore)
            patterns_to_scan: Set[str] = set()
            for stop_id in marked_stops:
                patterns_to_scan.update(self.store.get_patterns_at_stop(stop_id))

            for pattern_id in patterns_to_scan:
                # Get stops sequence from store
                pattern_stops = self.store.get_pattern_stops(pattern_id)
                if not pattern_stops:
                    continue

                # Check if any marked stop is in this pattern
                if not any(s in marked_stops for s in pattern_stops):
                    continue

                # Skip if pattern has no trips
                if not self.store.trips_by_pattern.get(pattern_id):
                    continue

                # Scan this pattern
                improved = self._scan_pattern(
                    pattern_id, pattern_stops,
                    labels[k - 1], labels[k], best_arrival, marked_stops
                )
                new_marked_stops.update(improved)

            # Step 2: Process transfers (walking) - using GTFSStore tuples
            # Solo procesamos new_marked_stops (paradas mejoradas en ESTA ronda)
            # Las marked_stops ya tuvieron su fase de transbordos en la ronda anterior
            # IMPORTANTE: Copiamos el set porque lo modificamos durante la iteración
            transfer_improved: Set[str] = set()
            for stop_id in list(new_marked_stops):
                if stop_id not in labels[k]:
                    continue

                arrival_at_stop = labels[k][stop_id].arrival_time

                # transfers is List[Tuple[to_stop_id, walk_seconds]]
                for to_stop_id, walk_seconds in self.store.get_transfers(stop_id):
                    arrival_after_walk = arrival_at_stop + walk_seconds + TRANSFER_PENALTY_SECONDS

                    if arrival_after_walk < best_arrival[to_stop_id]:
                        if to_stop_id not in labels[k] or arrival_after_walk < labels[k][to_stop_id].arrival_time:
                            labels[k][to_stop_id] = Label(
                                arrival_time=arrival_after_walk,
                                is_transfer=True,
                                from_stop_id=stop_id
                            )
                            best_arrival[to_stop_id] = arrival_after_walk
                            transfer_improved.add(to_stop_id)

            new_marked_stops.update(transfer_improved)
            marked_stops = new_marked_stops

        return labels

    def _scan_pattern(
        self,
        pattern_id: str,
        pattern_stops: List[str],
        prev_labels: Dict[str, Label],
        curr_labels: Dict[str, Label],
        best_arrival: Dict[str, int],
        marked_stops: Set[str]
    ) -> Set[str]:
        """Scan a single pattern for improvements.

        Args:
            pattern_id: The pattern ID (e.g., "METRO_1_0")
            pattern_stops: List of stop_ids in order
            prev_labels: Labels from previous round
            curr_labels: Labels for current round (to update)
            best_arrival: Best arrival times across all rounds
            marked_stops: Stops that were improved in previous round

        Returns:
            Set of stop_ids that were improved
        """
        improved_stops: Set[str] = set()

        # Find first marked stop in this pattern
        board_stop_idx = None
        for idx, stop_id in enumerate(pattern_stops):
            if stop_id in marked_stops and stop_id in prev_labels:
                board_stop_idx = idx
                break

        if board_stop_idx is None:
            return improved_stops

        # Try to board at each marked stop and ride
        current_trip_id: Optional[str] = None
        boarding_time: Optional[int] = None
        boarding_stop_id: Optional[str] = None
        boarding_stop_idx: Optional[int] = None

        for idx in range(board_stop_idx, len(pattern_stops)):
            stop_id = pattern_stops[idx]

            # Can we board here?
            if stop_id in prev_labels:
                arrival_at_stop = prev_labels[stop_id].arrival_time

                # Find earliest trip we can board at this stop (usando Store)
                new_trip_id = self.store.get_earliest_trip(
                    pattern_id, idx, arrival_at_stop, self._active_services
                )

                # Solo montarnos si no estamos ya en un trip
                # En sistemas FIFO (Metro/Cercanías), el trip actual siempre es mejor
                # que cualquier otro que salga más tarde de la misma línea
                if new_trip_id and current_trip_id is None:
                    current_trip_id = new_trip_id
                    boarding_stop_id = stop_id
                    boarding_stop_idx = idx
                    boarding_time = arrival_at_stop

            # If we're on a trip, check if we improve arrival at this stop
            if current_trip_id and boarding_stop_idx is not None and idx > boarding_stop_idx:
                arrival_time = self._get_trip_arrival(current_trip_id, idx)

                if arrival_time is not None and arrival_time < best_arrival[stop_id]:
                    # Found improvement - get route_id from trip_info
                    trip_info = self.store.get_trip_info(current_trip_id)
                    route_id = trip_info[0] if trip_info else None

                    if stop_id not in curr_labels or arrival_time < curr_labels[stop_id].arrival_time:
                        curr_labels[stop_id] = Label(
                            arrival_time=arrival_time,
                            trip_id=current_trip_id,
                            boarding_stop_id=boarding_stop_id,
                            boarding_time=boarding_time,
                            route_id=route_id
                        )
                        best_arrival[stop_id] = arrival_time
                        improved_stops.add(stop_id)

        return improved_stops

    def _get_trip_arrival(self, trip_id: str, stop_index: int) -> Optional[int]:
        """Get arrival time at a stop for a trip using O(1) index access.

        Args:
            trip_id: The trip ID
            stop_index: Index of the stop in the pattern sequence

        Returns:
            Arrival time in seconds, or None if index out of bounds
        """
        try:
            # O(1) access: stop_times_by_trip[trip_id][stop_index] = (stop_id, arrival, departure)
            return self.store.stop_times_by_trip[trip_id][stop_index][1]
        except (KeyError, IndexError):
            return None

    def _get_trip_departure(self, trip_id: str, stop_id: str) -> Optional[int]:
        """Get departure time at a stop for a trip.

        Args:
            trip_id: The trip ID
            stop_id: The stop to get departure time for

        Returns:
            Departure time in seconds, or None if stop not found
        """
        stop_times = self.store.get_stop_times(trip_id)
        for st_stop_id, _, departure_sec in stop_times:
            if st_stop_id == stop_id:
                return departure_sec
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

        # Safety counter para evitar infinite loops con datos corruptos
        safety_counter = 0
        MAX_STEPS = 20  # 5 rondas * 2 tramos + margen

        while current_stop != origin_stop_id and current_round >= 0:
            safety_counter += 1
            if safety_counter > MAX_STEPS:
                print(f"⚠️ Infinite loop detected reconstructing journey to {destination_stop_id}")
                return []  # Abortar ruta corrupta

            if current_stop not in labels[current_round]:
                break

            label = labels[current_round][current_stop]

            if label.is_transfer:
                # Walking leg
                from_stop = label.from_stop_id
                if from_stop:
                    # Get arrival time at from_stop (validar existencia, no inventar 0)
                    from_label = labels[current_round].get(from_stop)
                    if not from_label:
                        # Datos inconsistentes - saltar este leg
                        current_stop = from_stop
                        continue
                    from_arrival = from_label.arrival_time

                    legs.append(JourneyLeg(
                        type="walking",
                        from_stop_id=from_stop,
                        to_stop_id=current_stop,
                        departure_time=from_arrival,
                        arrival_time=label.arrival_time
                    ))
                    current_stop = from_stop
            elif label.boarding_stop_id:
                # Transit leg - use GTFSStore to get departure time
                actual_departure = None
                headsign = None

                if label.trip_id:
                    # Get actual departure time from stop_times (fuente de verdad)
                    dep_time = self._get_trip_departure(label.trip_id, label.boarding_stop_id)
                    if dep_time is not None:
                        actual_departure = dep_time

                    # Get headsign from trip_info
                    trip_info = self.store.get_trip_info(label.trip_id)
                    if trip_info:
                        headsign = trip_info[1]  # index 1 is headsign

                # Fallback a boarding_time del label si store no tiene dato
                if actual_departure is None:
                    actual_departure = label.boarding_time

                # Si aún no tenemos tiempo, datos corruptos - skip leg
                if actual_departure is None:
                    current_stop = label.boarding_stop_id
                    current_round -= 1
                    continue

                legs.append(JourneyLeg(
                    type="transit",
                    from_stop_id=label.boarding_stop_id,
                    to_stop_id=current_stop,
                    departure_time=actual_departure,
                    arrival_time=label.arrival_time,
                    route_id=label.route_id,
                    trip_id=label.trip_id,
                    headsign=headsign
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
