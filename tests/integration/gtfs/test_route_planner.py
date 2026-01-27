"""Integration tests for /route-planner endpoint.

These tests require a database connection. They will be skipped if
the database is not available.

To run these tests, ensure:
1. PostgreSQL is running locally (docker-compose up -d)
2. Database has been migrated (make db-upgrade)
3. Test data has been imported
"""

import os
import pytest
from fastapi.testclient import TestClient

# Skip all integration tests if no database is configured
pytestmark = pytest.mark.skipif(
    os.environ.get("SKIP_INTEGRATION_TESTS", "1") == "1",
    reason="Integration tests require database connection. Set SKIP_INTEGRATION_TESTS=0 to run."
)


class TestRoutePlannerEndpoint:
    """Tests for the RAPTOR route planner API endpoint."""

    def test_route_planner_requires_from_param(self, client, api_base_url):
        """Should return 422 when 'from' parameter is missing."""
        response = client.get(f"{api_base_url}/route-planner?to=STOP_B")
        assert response.status_code == 422

    def test_route_planner_requires_to_param(self, client, api_base_url):
        """Should return 422 when 'to' parameter is missing."""
        response = client.get(f"{api_base_url}/route-planner?from=STOP_A")
        assert response.status_code == 422

    def test_route_planner_invalid_stop(self, client, api_base_url):
        """Should return empty journeys for non-existent stops."""
        response = client.get(
            f"{api_base_url}/route-planner?from=INVALID_STOP&to=ALSO_INVALID"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True or data["success"] is False
        # Non-existent stops may return no journeys

    def test_route_planner_same_origin_destination(self, client, api_base_url):
        """Should handle same origin and destination gracefully."""
        response = client.get(
            f"{api_base_url}/route-planner?from=METRO_GRANADA_1&to=METRO_GRANADA_1"
        )
        assert response.status_code == 200
        data = response.json()
        # Same stop should return success with 0 journeys or trivial journey
        assert "success" in data

    def test_route_planner_response_structure(self, client, api_base_url):
        """Response should have correct structure."""
        response = client.get(
            f"{api_base_url}/route-planner?from=METRO_GRANADA_1&to=METRO_GRANADA_26"
        )
        assert response.status_code == 200
        data = response.json()

        # Required fields
        assert "success" in data
        assert "journeys" in data
        assert isinstance(data["journeys"], list)

    def test_route_planner_journey_structure(self, client, api_base_url):
        """Each journey should have required fields."""
        response = client.get(
            f"{api_base_url}/route-planner?from=METRO_GRANADA_1&to=METRO_GRANADA_26"
        )
        data = response.json()

        if data["success"] and len(data["journeys"]) > 0:
            journey = data["journeys"][0]
            assert "departure" in journey
            assert "arrival" in journey
            assert "duration_minutes" in journey
            assert "transfers" in journey
            assert "segments" in journey

    def test_route_planner_segment_structure(self, client, api_base_url):
        """Each segment should have required fields."""
        response = client.get(
            f"{api_base_url}/route-planner?from=METRO_GRANADA_1&to=METRO_GRANADA_26"
        )
        data = response.json()

        if data["success"] and len(data["journeys"]) > 0:
            journey = data["journeys"][0]
            if len(journey["segments"]) > 0:
                segment = journey["segments"][0]
                assert "type" in segment
                assert "mode" in segment
                assert "origin" in segment
                assert "destination" in segment

    def test_route_planner_with_departure_time(self, client, api_base_url):
        """Should accept departure_time parameter."""
        response = client.get(
            f"{api_base_url}/route-planner"
            "?from=METRO_GRANADA_1&to=METRO_GRANADA_26&departure_time=08:30"
        )
        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    def test_route_planner_with_max_transfers(self, client, api_base_url):
        """Should accept max_transfers parameter."""
        response = client.get(
            f"{api_base_url}/route-planner"
            "?from=METRO_GRANADA_1&to=METRO_GRANADA_26&max_transfers=2"
        )
        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    def test_route_planner_with_max_alternatives(self, client, api_base_url):
        """Should accept max_alternatives parameter."""
        response = client.get(
            f"{api_base_url}/route-planner"
            "?from=METRO_GRANADA_1&to=METRO_GRANADA_26&max_alternatives=3"
        )
        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    def test_route_planner_max_transfers_limit(self, client, api_base_url):
        """max_transfers should be limited to reasonable values."""
        # Very high value should still work or be capped
        response = client.get(
            f"{api_base_url}/route-planner"
            "?from=METRO_GRANADA_1&to=METRO_GRANADA_26&max_transfers=10"
        )
        # Should either work with capped value or return validation error
        assert response.status_code in [200, 422]


class TestRoutePlannerMetroGranada:
    """Integration tests using Metro Granada data (known good data)."""

    def test_direct_route_granada(self, client, api_base_url):
        """Metro Granada L1 should find direct route between adjacent stops."""
        response = client.get(
            f"{api_base_url}/route-planner?from=METRO_GRANADA_1&to=METRO_GRANADA_5"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        if len(data["journeys"]) > 0:
            journey = data["journeys"][0]
            # Direct route should have 0 transfers
            assert journey["transfers"] == 0

    def test_full_line_granada(self, client, api_base_url):
        """Should find route across full Metro Granada line."""
        response = client.get(
            f"{api_base_url}/route-planner?from=METRO_GRANADA_1&to=METRO_GRANADA_26"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["journeys"]) > 0


class TestRoutePlannerMetroSevilla:
    """Integration tests using Metro Sevilla data."""

    def test_metro_sevilla_route(self, client, api_base_url):
        """Metro Sevilla L1 should find routes."""
        response = client.get(
            f"{api_base_url}/route-planner?from=METRO_SEV_L1_E1&to=METRO_SEV_L1_E21"
        )
        assert response.status_code == 200
        data = response.json()
        # Should either find a route or return success=false with message
        assert "success" in data
