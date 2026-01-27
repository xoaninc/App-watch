"""Route planning service using Dijkstra's algorithm.

This service finds optimal routes between two stops in the transit network,
considering:
- Direct routes on the same line
- Transfers between different lines at the same station
- Walking transfers between nearby stations (correspondences)

The algorithm builds a graph where:
- Nodes are (stop_id, route_id) pairs (or just stop_id for walking)
- Edges are connections with time costs
"""

import heapq
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from sqlalchemy.orm import Session

from src.gtfs_bc.stop.infrastructure.models import StopModel
from src.gtfs_bc.route.infrastructure.models import RouteModel
from src.gtfs_bc.stop_route_sequence.infrastructure.models import StopRouteSequenceModel
from src.gtfs_bc.stop.infrastructure.models.stop_correspondence_model import StopCorrespondenceModel
from src.gtfs_bc.shape.infrastructure.models.shape_model import ShapePointModel
from src.gtfs_bc.trip.infrastructure.models import TripModel
from adapters.http.api.gtfs.utils.shape_utils import normalize_shape, haversine_distance


# Constants for time estimation
AVERAGE_SPEED_METRO_KMH = 30  # Average commercial speed for metro/subway
AVERAGE_SPEED_CERCANIAS_KMH = 45  # Average commercial speed for commuter rail
AVERAGE_SPEED_TRAM_KMH = 18  # Average commercial speed for tram
WALKING_SPEED_KMH = 4.5  # Average walking speed
TRANSFER_PENALTY_MINUTES = 3  # Additional penalty for each transfer


@dataclass
class GraphNode:
    """A node in the routing graph.

    Represents being at a specific stop, optionally on a specific route.
    """
    stop_id: str
    route_id: Optional[str] = None  # None for walking nodes

    def __hash__(self):
        return hash((self.stop_id, self.route_id))

    def __eq__(self, other):
        return self.stop_id == other.stop_id and self.route_id == other.route_id


@dataclass
class GraphEdge:
    """An edge in the routing graph.

    Represents a connection between two nodes with a time cost.
    """
    from_node: GraphNode
    to_node: GraphNode
    time_minutes: float
    edge_type: str  # "transit", "transfer_same_station", "transfer_walking"
    route_id: Optional[str] = None
    intermediate_stops: List[str] = field(default_factory=list)


@dataclass(order=True)
class PriorityQueueItem:
    """Item for the priority queue in Dijkstra's algorithm."""
    priority: float
    node: GraphNode = field(compare=False)
    path: List[GraphEdge] = field(compare=False, default_factory=list)


class RoutingService:
    """Service for finding optimal routes in the transit network.

    Uses Dijkstra's algorithm on a dynamically constructed graph.
    """

    def __init__(self, db: Session):
        self.db = db
        self._stops_cache: Dict[str, StopModel] = {}
        self._routes_cache: Dict[str, RouteModel] = {}
        self._route_stops_cache: Dict[str, List[Tuple[str, int]]] = {}  # route_id -> [(stop_id, sequence)]
        self._stop_routes_cache: Dict[str, List[str]] = {}  # stop_id -> [route_ids]
        self._correspondences_cache: Dict[str, List[Tuple[str, int]]] = {}  # stop_id -> [(to_stop_id, walk_time_s)]

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

    def _get_routes_at_stop(self, stop_id: str) -> List[str]:
        """Get all routes serving a stop."""
        if stop_id not in self._stop_routes_cache:
            sequences = self.db.query(StopRouteSequenceModel.route_id).filter(
                StopRouteSequenceModel.stop_id == stop_id
            ).distinct().all()
            self._stop_routes_cache[stop_id] = [s.route_id for s in sequences]
        return self._stop_routes_cache[stop_id]

    def _get_stops_on_route(self, route_id: str) -> List[Tuple[str, int]]:
        """Get all stops on a route, ordered by sequence."""
        if route_id not in self._route_stops_cache:
            sequences = self.db.query(
                StopRouteSequenceModel.stop_id,
                StopRouteSequenceModel.sequence
            ).filter(
                StopRouteSequenceModel.route_id == route_id
            ).order_by(StopRouteSequenceModel.sequence).all()
            self._route_stops_cache[route_id] = [(s.stop_id, s.sequence) for s in sequences]
        return self._route_stops_cache[route_id]

    def _get_correspondences(self, stop_id: str) -> List[Tuple[str, int]]:
        """Get walking correspondences from a stop."""
        if stop_id not in self._correspondences_cache:
            corrs = self.db.query(
                StopCorrespondenceModel.to_stop_id,
                StopCorrespondenceModel.walk_time_s
            ).filter(
                StopCorrespondenceModel.from_stop_id == stop_id
            ).all()
            self._correspondences_cache[stop_id] = [(c.to_stop_id, c.walk_time_s) for c in corrs]
        return self._correspondences_cache[stop_id]

    def _estimate_travel_time(self, from_stop: StopModel, to_stop: StopModel, route: RouteModel) -> float:
        """Estimate travel time between two stops on the same route.

        Uses distance and average speed based on transport type.
        """
        distance_km = haversine_distance(
            from_stop.lat, from_stop.lon,
            to_stop.lat, to_stop.lon
        ) / 1000

        # Determine speed based on route type
        route_type = route.route_type if route else 1
        if route_type == 1:  # Metro/subway
            speed = AVERAGE_SPEED_METRO_KMH
        elif route_type == 2:  # Rail (Cercanías)
            speed = AVERAGE_SPEED_CERCANIAS_KMH
        elif route_type == 0:  # Tram
            speed = AVERAGE_SPEED_TRAM_KMH
        else:
            speed = AVERAGE_SPEED_METRO_KMH

        # Time = distance / speed (in hours), convert to minutes
        time_minutes = (distance_km / speed) * 60

        # Add minimum dwell time at station (30 seconds)
        time_minutes += 0.5

        return max(1, time_minutes)  # At least 1 minute

    def _estimate_segment_time(self, route_id: str, from_seq: int, to_seq: int) -> Tuple[float, List[str]]:
        """Estimate travel time for a segment of a route.

        Returns (time_minutes, intermediate_stop_ids).
        """
        stops = self._get_stops_on_route(route_id)
        route = self._get_route(route_id)

        total_time = 0
        intermediate_stops = []

        # Find stops in the sequence range
        segment_stops = [(sid, seq) for sid, seq in stops if from_seq <= seq <= to_seq]
        segment_stops.sort(key=lambda x: x[1])

        for i in range(len(segment_stops) - 1):
            from_stop_id = segment_stops[i][0]
            to_stop_id = segment_stops[i + 1][0]

            from_stop = self._get_stop(from_stop_id)
            to_stop = self._get_stop(to_stop_id)

            if from_stop and to_stop:
                total_time += self._estimate_travel_time(from_stop, to_stop, route)

            # Add to intermediate stops (excluding origin and destination)
            if i > 0:
                intermediate_stops.append(from_stop_id)

        return total_time, intermediate_stops

    def _get_neighbors(self, node: GraphNode, destination_stop_id: str) -> List[GraphEdge]:
        """Get all neighboring nodes from the current node.

        Returns edges to:
        1. Next stops on the same route (if on a route)
        2. Other routes at the same stop (transfer)
        3. Walking correspondences to other stations
        """
        edges = []
        current_stop = self._get_stop(node.stop_id)
        if not current_stop:
            return edges

        # 1. If on a route, can continue to next stops on same route
        if node.route_id:
            stops = self._get_stops_on_route(node.route_id)
            route = self._get_route(node.route_id)

            # Find current position in sequence
            current_seq = None
            for stop_id, seq in stops:
                if stop_id == node.stop_id:
                    current_seq = seq
                    break

            if current_seq is not None:
                # Can travel to any future stop on this route (both directions)
                for stop_id, seq in stops:
                    if stop_id != node.stop_id:
                        # Calculate segment time
                        if seq > current_seq:
                            time, intermediate = self._estimate_segment_time(
                                node.route_id, current_seq, seq
                            )
                        else:
                            time, intermediate = self._estimate_segment_time(
                                node.route_id, seq, current_seq
                            )
                            intermediate = list(reversed(intermediate))

                        edges.append(GraphEdge(
                            from_node=node,
                            to_node=GraphNode(stop_id, node.route_id),
                            time_minutes=time,
                            edge_type="transit",
                            route_id=node.route_id,
                            intermediate_stops=intermediate
                        ))

        # 2. Transfer to other routes at the same stop
        routes_at_stop = self._get_routes_at_stop(node.stop_id)
        for route_id in routes_at_stop:
            if route_id != node.route_id:
                edges.append(GraphEdge(
                    from_node=node,
                    to_node=GraphNode(node.stop_id, route_id),
                    time_minutes=TRANSFER_PENALTY_MINUTES,
                    edge_type="transfer_same_station"
                ))

        # 3. Walking correspondences to other stations
        correspondences = self._get_correspondences(node.stop_id)
        for to_stop_id, walk_time_s in correspondences:
            walk_minutes = walk_time_s / 60
            edges.append(GraphEdge(
                from_node=node,
                to_node=GraphNode(to_stop_id, None),  # Arrive at stop without a route
                time_minutes=walk_minutes + TRANSFER_PENALTY_MINUTES,
                edge_type="transfer_walking"
            ))

        # 4. If not on a route, can board any route at this stop
        if node.route_id is None:
            for route_id in routes_at_stop:
                edges.append(GraphEdge(
                    from_node=node,
                    to_node=GraphNode(node.stop_id, route_id),
                    time_minutes=2,  # Average waiting time
                    edge_type="board"
                ))

        return edges

    def find_route(
        self,
        from_stop_id: str,
        to_stop_id: str,
        max_transfers: int = 3
    ) -> Optional[List[GraphEdge]]:
        """Find the optimal route between two stops using Dijkstra's algorithm.

        Args:
            from_stop_id: Origin stop ID
            to_stop_id: Destination stop ID
            max_transfers: Maximum number of transfers allowed

        Returns:
            List of edges representing the optimal path, or None if no route found
        """
        # Validate stops exist
        from_stop = self._get_stop(from_stop_id)
        to_stop = self._get_stop(to_stop_id)
        if not from_stop or not to_stop:
            return None

        # Initialize Dijkstra
        start_node = GraphNode(from_stop_id, None)
        visited: Set[GraphNode] = set()
        queue: List[PriorityQueueItem] = []

        heapq.heappush(queue, PriorityQueueItem(0, start_node, []))

        while queue:
            item = heapq.heappop(queue)
            current_time = item.priority
            current_node = item.node
            current_path = item.path

            # Skip if already visited
            if current_node in visited:
                continue
            visited.add(current_node)

            # Check if reached destination
            if current_node.stop_id == to_stop_id:
                return current_path

            # Count transfers in current path
            transfer_count = sum(1 for e in current_path if e.edge_type.startswith("transfer"))
            if transfer_count >= max_transfers:
                continue

            # Explore neighbors
            for edge in self._get_neighbors(current_node, to_stop_id):
                if edge.to_node not in visited:
                    new_time = current_time + edge.time_minutes
                    new_path = current_path + [edge]
                    heapq.heappush(queue, PriorityQueueItem(new_time, edge.to_node, new_path))

        return None  # No route found

    def get_route_shape(self, route_id: str) -> List[Tuple[float, float]]:
        """Get shape coordinates for a route."""
        trip = self.db.query(TripModel).filter(
            TripModel.route_id == route_id,
            TripModel.shape_id.isnot(None)
        ).first()

        if not trip or not trip.shape_id:
            return []

        points = self.db.query(ShapePointModel).filter(
            ShapePointModel.shape_id == trip.shape_id
        ).order_by(ShapePointModel.sequence).all()

        return [(p.lat, p.lon) for p in points]

    def extract_segment_shape(
        self,
        route_id: str,
        from_stop_id: str,
        to_stop_id: str,
        max_gap: Optional[float] = None
    ) -> List[Tuple[float, float]]:
        """Extract shape coordinates for a segment of a route.

        Finds the portion of the route shape between two stops.
        """
        full_shape = self.get_route_shape(route_id)
        if not full_shape:
            # Fallback: straight line between stops
            from_stop = self._get_stop(from_stop_id)
            to_stop = self._get_stop(to_stop_id)
            if from_stop and to_stop:
                return [(from_stop.lat, from_stop.lon), (to_stop.lat, to_stop.lon)]
            return []

        # Get stop coordinates
        from_stop = self._get_stop(from_stop_id)
        to_stop = self._get_stop(to_stop_id)
        if not from_stop or not to_stop:
            return full_shape

        # Find closest points in shape to origin and destination
        def find_closest_point_index(lat: float, lon: float) -> int:
            min_dist = float('inf')
            min_idx = 0
            for i, (plat, plon) in enumerate(full_shape):
                dist = haversine_distance(lat, lon, plat, plon)
                if dist < min_dist:
                    min_dist = dist
                    min_idx = i
            return min_idx

        from_idx = find_closest_point_index(from_stop.lat, from_stop.lon)
        to_idx = find_closest_point_index(to_stop.lat, to_stop.lon)

        # Extract segment (handle both directions)
        if from_idx <= to_idx:
            segment = full_shape[from_idx:to_idx + 1]
        else:
            segment = list(reversed(full_shape[to_idx:from_idx + 1]))

        # Normalize if requested
        if max_gap and segment:
            points_with_seq = [(lat, lon, i) for i, (lat, lon) in enumerate(segment)]
            normalized = normalize_shape(points_with_seq, max_gap)
            segment = [(lat, lon) for lat, lon, _ in normalized]

        return segment
