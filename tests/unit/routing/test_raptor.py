"""Unit tests for RAPTOR algorithm data structures and helpers."""

import pytest
from datetime import datetime, time

from src.gtfs_bc.routing.raptor import (
    StopTime,
    Trip,
    Transfer,
    RoutePattern,
    Label,
    Journey,
    JourneyLeg,
    INFINITY,
    MAX_ROUNDS,
    WALKING_SPEED_KMH,
    TRANSFER_PENALTY_SECONDS,
)


class TestStopTime:
    """Tests for StopTime data structure."""

    def test_create_stop_time(self):
        """StopTime should store arrival/departure times in seconds."""
        st = StopTime(
            trip_id="TRIP_001",
            stop_id="STOP_A",
            stop_sequence=1,
            arrival_seconds=28800,  # 08:00:00
            departure_seconds=28860,  # 08:01:00
        )
        assert st.trip_id == "TRIP_001"
        assert st.stop_id == "STOP_A"
        assert st.arrival_seconds == 28800
        assert st.departure_seconds == 28860

    def test_stop_time_sequence(self):
        """stop_sequence should indicate order within a trip."""
        st1 = StopTime("T1", "A", 1, 0, 60)
        st2 = StopTime("T1", "B", 2, 120, 180)
        assert st1.stop_sequence < st2.stop_sequence


class TestTrip:
    """Tests for Trip data structure."""

    def test_create_trip(self):
        """Trip should contain route info and stop times."""
        trip = Trip(
            trip_id="TRIP_001",
            route_id="ROUTE_L1",
            service_id="SERVICE_WEEKDAY",
            headsign="Terminus",
        )
        assert trip.trip_id == "TRIP_001"
        assert trip.route_id == "ROUTE_L1"
        assert trip.stop_times == []

    def test_trip_with_stop_times(self):
        """Trip can have multiple stop times."""
        trip = Trip("T1", "R1", "S1", "Destination")
        trip.stop_times = [
            StopTime("T1", "A", 1, 0, 60),
            StopTime("T1", "B", 2, 300, 360),
            StopTime("T1", "C", 3, 600, 660),
        ]
        assert len(trip.stop_times) == 3
        assert trip.stop_times[0].stop_id == "A"
        assert trip.stop_times[-1].stop_id == "C"


class TestTransfer:
    """Tests for Transfer (walking connection) data structure."""

    def test_create_transfer(self):
        """Transfer should represent walking between stops."""
        transfer = Transfer(
            from_stop_id="METRO_A",
            to_stop_id="RENFE_A",
            walk_seconds=180,  # 3 minutes
        )
        assert transfer.from_stop_id == "METRO_A"
        assert transfer.to_stop_id == "RENFE_A"
        assert transfer.walk_seconds == 180

    def test_transfer_time_calculation(self):
        """Walking time should be reasonable for short distances."""
        # 300m at 4.5 km/h = 300 / (4500/3600) = 240 seconds
        transfer = Transfer("A", "B", 240)
        assert transfer.walk_seconds == 240


class TestRoutePattern:
    """Tests for RoutePattern data structure."""

    def test_create_pattern(self):
        """RoutePattern defines stop sequence for a route."""
        pattern = RoutePattern(
            route_id="L1",
            stops=["A", "B", "C", "D"],
        )
        assert pattern.route_id == "L1"
        assert len(pattern.stops) == 4
        assert pattern.stops[0] == "A"
        assert pattern.stops[-1] == "D"

    def test_pattern_with_trips(self):
        """RoutePattern can contain multiple trips."""
        pattern = RoutePattern("L1", ["A", "B", "C"])
        pattern.trips = [
            Trip("T1", "L1", "S1", "C"),
            Trip("T2", "L1", "S1", "C"),
        ]
        assert len(pattern.trips) == 2


class TestLabel:
    """Tests for Label (arrival state) data structure."""

    def test_create_label(self):
        """Label tracks arrival time and journey info."""
        label = Label(
            arrival_time=28800,
            trip_id="TRIP_001",
            boarding_stop_id="STOP_A",
            boarding_time=28500,
            route_id="ROUTE_L1",
        )
        assert label.arrival_time == 28800
        assert label.trip_id == "TRIP_001"
        assert not label.is_transfer

    def test_transfer_label(self):
        """Label can represent a walking transfer."""
        label = Label(
            arrival_time=29000,
            is_transfer=True,
            from_stop_id="METRO_A",
        )
        assert label.is_transfer
        assert label.from_stop_id == "METRO_A"
        assert label.trip_id is None

    def test_initial_label_infinity(self):
        """Initial labels should have infinite arrival time."""
        label = Label(arrival_time=INFINITY)
        assert label.arrival_time == float('inf')


class TestJourney:
    """Tests for Journey (complete route result) data structure."""

    def test_create_journey(self):
        """Journey contains complete trip information."""
        journey = Journey(
            departure_time=28800,
            arrival_time=30600,
            transfers=0,
            legs=[],
        )
        assert journey.departure_time == 28800
        assert journey.arrival_time == 30600
        assert journey.legs == []
        assert journey.transfers == 0

    def test_journey_duration(self):
        """Journey duration is arrival minus departure."""
        journey = Journey(
            departure_time=28800,  # 08:00
            arrival_time=30600,    # 08:30
            transfers=0,
        )
        assert journey.duration_seconds == 1800  # 30 minutes
        assert journey.duration_minutes == 30


class TestJourneyLeg:
    """Tests for JourneyLeg (segment of journey) data structure."""

    def test_transit_leg(self):
        """Transit leg represents travel on a vehicle."""
        leg = JourneyLeg(
            type="transit",
            from_stop_id="A",
            to_stop_id="B",
            departure_time=28800,
            arrival_time=29400,
            route_id="L1",
            trip_id="T1",
        )
        assert leg.type == "transit"
        assert leg.route_id == "L1"

    def test_walking_leg(self):
        """Walking leg represents transfer on foot."""
        leg = JourneyLeg(
            type="walking",
            from_stop_id="METRO_A",
            to_stop_id="RENFE_A",
            departure_time=29400,
            arrival_time=29580,
        )
        assert leg.type == "walking"
        assert leg.route_id is None


class TestConstants:
    """Tests for RAPTOR algorithm constants."""

    def test_max_rounds(self):
        """MAX_ROUNDS should be reasonable (typically 4-6)."""
        assert 3 <= MAX_ROUNDS <= 10

    def test_walking_speed(self):
        """Walking speed should be reasonable (4-5 km/h)."""
        assert 4.0 <= WALKING_SPEED_KMH <= 5.5

    def test_transfer_penalty(self):
        """Transfer penalty should be 2-5 minutes."""
        assert 120 <= TRANSFER_PENALTY_SECONDS <= 300

    def test_infinity(self):
        """INFINITY should be larger than any time value."""
        max_seconds_in_day = 24 * 60 * 60
        assert INFINITY > max_seconds_in_day * 2
