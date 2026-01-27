"""Routing module for transit pathfinding.

Provides Dijkstra-based route planning between stops in the transit network.
"""

from .routing_service import RoutingService

__all__ = ["RoutingService"]
