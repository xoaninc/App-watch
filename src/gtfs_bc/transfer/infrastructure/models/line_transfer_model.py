from sqlalchemy import Column, String, Integer, Text, Float
from core.base import Base


class LineTransferModel(Base):
    """SQLAlchemy model for line transfers (interchange information).

    Stores transfer times and instructions between stops/lines at interchanges.
    Data comes from GTFS transfers.txt or manual entries.
    """
    __tablename__ = "line_transfer"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Stop IDs (required)
    from_stop_id = Column(String(100), nullable=False, index=True)
    to_stop_id = Column(String(100), nullable=False, index=True)

    # Route IDs (optional - for route-specific transfers)
    from_route_id = Column(String(100), nullable=True)
    to_route_id = Column(String(100), nullable=True)

    # Platform/stop coordinates (specific to each line's platform)
    from_lat = Column(Float, nullable=True)
    from_lon = Column(Float, nullable=True)
    to_lat = Column(Float, nullable=True)
    to_lon = Column(Float, nullable=True)

    # Transfer type (GTFS standard)
    # 0 = Recommended transfer point
    # 1 = Timed transfer (vehicle waits)
    # 2 = Minimum time required
    # 3 = Transfer not possible
    # 4 = In-seat transfer (stay on vehicle)
    # 5 = In-seat transfer not allowed
    transfer_type = Column(Integer, nullable=False, default=0)

    # Minimum transfer time in seconds
    min_transfer_time = Column(Integer, nullable=True)

    # Denormalized stop names for quick access
    from_stop_name = Column(String(255), nullable=True)
    to_stop_name = Column(String(255), nullable=True)

    # Line names (e.g., "L1", "C4a", "T1")
    from_line = Column(String(50), nullable=True)
    to_line = Column(String(50), nullable=True)

    # Network ID for filtering (e.g., "10T", "TMB_METRO")
    network_id = Column(String(20), nullable=True, index=True)

    # Additional info
    instructions = Column(Text, nullable=True)  # Walking instructions
    exit_name = Column(String(255), nullable=True)  # Exit/entrance to use

    # Source of data
    source = Column(String(50), nullable=True)  # 'gtfs', 'manual', 'nap'

    def __repr__(self):
        return f"<LineTransfer {self.from_stop_id} -> {self.to_stop_id} ({self.min_transfer_time}s)>"
