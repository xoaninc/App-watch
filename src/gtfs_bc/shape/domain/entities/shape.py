from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ShapePoint:
    """A single point in a shape."""

    lat: float
    lon: float
    sequence: int
    dist_traveled: Optional[float] = None


@dataclass
class Shape:
    """GTFS Shape entity - represents the path of a route."""

    id: str
    points: List[ShapePoint] = field(default_factory=list)

    def add_point(self, lat: float, lon: float, sequence: int, dist_traveled: Optional[float] = None):
        """Add a point to the shape."""
        self.points.append(ShapePoint(lat, lon, sequence, dist_traveled))
        self.points.sort(key=lambda p: p.sequence)

    @classmethod
    def from_gtfs_rows(cls, shape_id: str, rows: List[dict]) -> "Shape":
        """Create Shape from multiple GTFS CSV rows."""
        shape = cls(id=shape_id)
        for row in rows:
            shape.add_point(
                lat=float(row.get("shape_pt_lat", 0)),
                lon=float(row.get("shape_pt_lon", 0)),
                sequence=int(row.get("shape_pt_sequence", 0)),
                dist_traveled=float(row["shape_dist_traveled"]) if row.get("shape_dist_traveled") else None,
            )
        return shape

    def to_coordinates(self) -> List[List[float]]:
        """Return shape as list of [lat, lon] coordinates."""
        return [[p.lat, p.lon] for p in self.points]
