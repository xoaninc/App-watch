#!/usr/bin/env python3
"""Base class for GTFS importers.

Provides standardized patterns for importing GTFS data from various transit operators.
All import scripts should inherit from GTFSImporterBase to ensure consistent behavior.

Usage:
    from scripts.gtfs_importer_base import GTFSImporterBase

    class MyTransitImporter(GTFSImporterBase):
        NETWORK_CONFIG = {...}
        AGENCY_CONFIG = {...}
        ...
"""

import csv
import logging
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.database import SessionLocal
from src.gtfs_bc.stop.infrastructure.models import StopModel
from src.gtfs_bc.route.infrastructure.models import RouteModel, RouteFrequencyModel
from src.gtfs_bc.agency.infrastructure.models import AgencyModel
from src.gtfs_bc.stop_route_sequence.infrastructure.models import StopRouteSequenceModel
from src.gtfs_bc.network.infrastructure.models import NetworkModel


logger = logging.getLogger(__name__)


@dataclass
class NetworkConfig:
    """Configuration for a transit network."""
    code: str  # Must match route ID prefix for route_count to work
    name: str
    region: str
    color: str  # Hex color with # (e.g., "#E30613")
    text_color: str = "#FFFFFF"
    description: Optional[str] = None
    logo_url: Optional[str] = None
    wikipedia_url: Optional[str] = None
    nucleo_id_renfe: Optional[int] = None  # Solo para redes de Cercanías


@dataclass
class AgencyConfig:
    """Configuration for a transit agency."""
    id: str
    name: str
    url: str = ""
    timezone: str = "Europe/Madrid"
    lang: str = "es"
    phone: str = ""


@dataclass
class RouteConfig:
    """Configuration for a transit route."""
    id: str
    short_name: str
    long_name: str
    route_type: int  # 0=Tram, 1=Metro, 2=Rail, 3=Bus
    color: str
    text_color: str = "FFFFFF"


@dataclass
class ImportStats:
    """Statistics from an import operation."""
    network_created: bool = False
    agency_created: bool = False
    routes_created: int = 0
    routes_updated: int = 0
    stops_created: int = 0
    stops_updated: int = 0
    sequences_created: int = 0
    frequencies_created: int = 0

    def __str__(self) -> str:
        return (
            f"Network: {'created' if self.network_created else 'updated'}, "
            f"Agency: {'created' if self.agency_created else 'updated'}, "
            f"Routes: {self.routes_created} new / {self.routes_updated} updated, "
            f"Stops: {self.stops_created} new / {self.stops_updated} updated, "
            f"Sequences: {self.sequences_created}, "
            f"Frequencies: {self.frequencies_created}"
        )


class GTFSImporterBase(ABC):
    """Base class for GTFS importers.

    Subclasses must implement:
    - NETWORK_CONFIG: NetworkConfig instance
    - AGENCY_CONFIG: AgencyConfig instance
    - import_routes(): Import routes from GTFS data
    - import_stops(): Import stops from GTFS data
    """

    # Subclasses must define these
    NETWORK_CONFIG: NetworkConfig = None
    AGENCY_CONFIG: AgencyConfig = None

    def __init__(self, db: Session, gtfs_path: Optional[Path] = None):
        self.db = db
        self.gtfs_path = gtfs_path
        self.stats = ImportStats()
        self._route_mapping: Dict[str, str] = {}  # gtfs_id -> our_id
        self._stop_mapping: Dict[str, str] = {}  # gtfs_id -> our_id

    @staticmethod
    def read_csv(file_path: Path) -> List[dict]:
        """Read CSV file and return list of dicts."""
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            return list(reader)

    def validate_config(self):
        """Validate that required configuration is set."""
        if self.NETWORK_CONFIG is None:
            raise ValueError(f"{self.__class__.__name__} must define NETWORK_CONFIG")
        if self.AGENCY_CONFIG is None:
            raise ValueError(f"{self.__class__.__name__} must define AGENCY_CONFIG")

    def check_network(self) -> NetworkModel:
        """Check that the network exists in the database."""
        network = self.db.query(NetworkModel).filter(
            NetworkModel.code == self.NETWORK_CONFIG.code
        ).first()
        if network:
            logger.info(f"Using network: {network.name} (code={network.code})")
        return network

    def import_network(self) -> str:
        """Create or update the network entry."""
        config = self.NETWORK_CONFIG
        existing = self.db.query(NetworkModel).filter(
            NetworkModel.code == config.code
        ).first()

        if existing:
            logger.info(f"Network {config.code} already exists, updating...")
            existing.name = config.name
            existing.region = config.region
            existing.color = config.color
            existing.text_color = config.text_color
            existing.description = config.description
            existing.logo_url = config.logo_url
            existing.wikipedia_url = config.wikipedia_url
            existing.nucleo_id_renfe = config.nucleo_id_renfe
        else:
            network = NetworkModel(
                code=config.code,
                name=config.name,
                region=config.region,
                color=config.color,
                text_color=config.text_color,
                description=config.description,
                logo_url=config.logo_url,
                wikipedia_url=config.wikipedia_url,
                nucleo_id_renfe=config.nucleo_id_renfe,
            )
            self.db.add(network)
            self.stats.network_created = True
            logger.info(f"Created network: {config.code}")

        self.db.flush()
        return config.code

    def import_agency(self) -> str:
        """Create or update the agency entry."""
        config = self.AGENCY_CONFIG
        existing = self.db.query(AgencyModel).filter(
            AgencyModel.id == config.id
        ).first()

        if existing:
            logger.info(f"Agency {config.id} already exists, updating...")
            existing.name = config.name
            existing.url = config.url
            existing.timezone = config.timezone
            existing.lang = config.lang
            existing.phone = config.phone
        else:
            agency = AgencyModel(
                id=config.id,
                name=config.name,
                url=config.url,
                timezone=config.timezone,
                lang=config.lang,
                phone=config.phone,
            )
            self.db.add(agency)
            self.stats.agency_created = True
            logger.info(f"Created agency: {config.id}")

        self.db.flush()
        return config.id

    def create_stop(
        self,
        stop_id: str,
        name: str,
        lat: float,
        lon: float,
        lineas: str,
        location_type: int = 1,  # 1 = Station by default
        **kwargs
    ) -> StopModel:
        """Create or update a stop."""
        existing = self.db.query(StopModel).filter(StopModel.id == stop_id).first()

        if existing:
            existing.name = name
            existing.lat = lat
            existing.lon = lon
            existing.lineas = lineas
            existing.location_type = location_type
            for key, value in kwargs.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            self.stats.stops_updated += 1
            return existing
        else:
            stop = StopModel(
                id=stop_id,
                name=name,
                lat=lat,
                lon=lon,
                lineas=lineas,
                location_type=location_type,
                **kwargs
            )
            self.db.add(stop)
            self.stats.stops_created += 1
            logger.info(f"Created stop: {stop_id} ({name})")
            return stop

    def create_route(
        self,
        route_id: str,
        short_name: str,
        long_name: str,
        route_type: int,
        color: str,
        agency_id: str,
        text_color: str = "FFFFFF",
        **kwargs
    ) -> RouteModel:
        """Create or update a route."""
        existing = self.db.query(RouteModel).filter(RouteModel.id == route_id).first()

        if existing:
            existing.short_name = short_name
            existing.long_name = long_name
            existing.route_type = route_type
            existing.color = color
            existing.text_color = text_color
            existing.agency_id = agency_id
            existing.network_id = self.NETWORK_CONFIG.code
            for key, value in kwargs.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            self.stats.routes_updated += 1
            return existing
        else:
            route = RouteModel(
                id=route_id,
                short_name=short_name,
                long_name=long_name,
                route_type=route_type,
                color=color,
                text_color=text_color,
                agency_id=agency_id,
                network_id=self.NETWORK_CONFIG.code,
                **kwargs
            )
            self.db.add(route)
            self.stats.routes_created += 1
            logger.info(f"Created route: {route_id} ({short_name})")
            return route

    def create_stop_sequence(self, route_id: str, stop_id: str, sequence: int):
        """Create a stop sequence entry."""
        seq = StopRouteSequenceModel(
            route_id=route_id,
            stop_id=stop_id,
            sequence=sequence,
        )
        self.db.add(seq)
        self.stats.sequences_created += 1

    def delete_stop_sequences(self, route_id: str):
        """Delete all stop sequences for a route."""
        self.db.query(StopRouteSequenceModel).filter(
            StopRouteSequenceModel.route_id == route_id
        ).delete()

    @abstractmethod
    def import_routes(self, agency_id: str) -> Dict[str, str]:
        """Import routes from GTFS data. Returns mapping of gtfs_id -> our_id."""
        pass

    @abstractmethod
    def import_stops(self) -> Dict[str, str]:
        """Import stops from GTFS data. Returns mapping of gtfs_id -> our_id."""
        pass

    def import_stop_sequences(self):
        """Import stop sequences. Override in subclass if needed."""
        pass

    def import_frequencies(self):
        """Import frequencies. Override in subclass if needed."""
        pass

    def run(self) -> ImportStats:
        """Run the full import process."""
        self.validate_config()

        logger.info(f"Starting {self.NETWORK_CONFIG.name} import...")

        # Import in order
        network_code = self.import_network()
        agency_id = self.import_agency()
        self._route_mapping = self.import_routes(agency_id)
        self._stop_mapping = self.import_stops()
        self.import_stop_sequences()
        self.import_frequencies()

        self.db.commit()

        logger.info("=" * 60)
        logger.info(f"{self.NETWORK_CONFIG.name.upper()} IMPORT COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Network: {network_code}")
        logger.info(f"Agency: {agency_id}")
        logger.info(str(self.stats))

        return self.stats


def setup_logging():
    """Setup standard logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def create_cli_main(importer_class):
    """Create a standard main() function for CLI usage.

    Usage in import script:
        if __name__ == "__main__":
            from scripts.gtfs_importer_base import create_cli_main
            create_cli_main(MyTransitImporter)()
    """
    def main():
        setup_logging()

        if len(sys.argv) < 2:
            print(f"Usage: python {sys.argv[0]} <gtfs_folder_path>")
            sys.exit(1)

        gtfs_path = Path(sys.argv[1])
        if not gtfs_path.exists():
            print(f"Error: Path not found: {gtfs_path}")
            sys.exit(1)

        db = SessionLocal()
        try:
            importer = importer_class(db, gtfs_path)
            importer.run()
        except Exception as e:
            logger.error(f"Import failed: {e}")
            db.rollback()
            raise
        finally:
            db.close()

    return main
