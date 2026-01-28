#!/usr/bin/env python3
"""Import transfers.txt data from GTFS feeds into line_transfer table.

Imports transfer/interchange data from:
- TMB Metro Barcelona (60 transfers)
- Renfe Cercanías (19 transfers, distribuidos por network)
- Euskotren (13 transfers)
- Metro Tenerife (2 transfers)
- Metro Málaga (4 transfers, manual)

Nota: Metro Bilbao y FGC se incluyen en la config pero sus GTFS
no contienen transfers.txt (verificado 2026-01-25).

Usage:
    python scripts/import_transfers.py
"""

import sys
import os
import csv
import io
import zipfile
import logging
from pathlib import Path
from typing import Optional, Dict, List

import httpx

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from core.database import SessionLocal
from src.gtfs_bc.transfer.infrastructure.models import LineTransferModel
from src.gtfs_bc.stop.infrastructure.models import StopModel

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Operator GTFS feed configurations
OPERATORS_WITH_TRANSFERS = {
    'metro_bilbao': {
        'name': 'Metro Bilbao',
        'gtfs_url': 'https://opendata.euskadi.eus/transport/moveuskadi/metro_bilbao/gtfs_metro_bilbao.zip',
        'network_id': 'METRO_BILBAO',
        'stop_prefix': 'METRO_BILBAO_',
    },
    'euskotren': {
        'name': 'Euskotren',
        'gtfs_url': 'https://opendata.euskadi.eus/transport/moveuskadi/euskotren/gtfs_euskotren.zip',
        'network_id': 'EUSKOTREN',
        'stop_prefix': 'EUSKOTREN_',
    },
    'fgc': {
        'name': 'FGC',
        'gtfs_url': 'https://www.fgc.cat/google/google_transit.zip',
        'network_id': 'FGC',
        'stop_prefix': 'FGC_',
    },
    'tmb_metro': {
        'name': 'TMB Metro Barcelona',
        'gtfs_url': f'https://api.tmb.cat/v1/static/datasets/gtfs.zip?app_id={os.getenv("TMB_APP_ID", "")}&app_key={os.getenv("TMB_APP_KEY", "")}',
        'network_id': 'TMB_METRO',
        'stop_prefix': 'TMB_METRO_',
    },
    'metro_tenerife': {
        'name': 'Metro Tenerife',
        'gtfs_url': 'https://metrotenerife.com/transit/google_transit.zip',
        'network_id': 'METRO_TENERIFE',
        'stop_prefix': 'METRO_TENERIFE_',
    },
    'renfe_cercanias': {
        'name': 'Renfe Cercanías (all regions)',
        'gtfs_url': 'https://ssl.renfe.com/ftransit/Fichero_CER_FOMENTO/fomento_transit.zip',
        'network_id': None,  # Se extrae del route_id (40T, 10T, etc.)
        'stop_prefix': 'RENFE_',
        'skip_line_lookup': True,
        'extract_network_from_route': True,
    },
}


def download_gtfs(url: str) -> Optional[bytes]:
    """Download GTFS zip file."""
    try:
        logger.info(f"Downloading GTFS from {url}")
        response = httpx.get(url, timeout=60.0, follow_redirects=True)
        response.raise_for_status()
        logger.info(f"Downloaded {len(response.content)} bytes")
        return response.content
    except Exception as e:
        logger.error(f"Error downloading GTFS: {e}")
        return None


def parse_transfers_txt(zip_content: bytes) -> List[Dict]:
    """Parse transfers.txt from GTFS zip file."""
    transfers = []

    try:
        with zipfile.ZipFile(io.BytesIO(zip_content)) as zf:
            # Check if transfers.txt exists
            file_list = zf.namelist()
            transfers_file = None

            for name in file_list:
                if name.endswith('transfers.txt') or name == 'transfers.txt':
                    transfers_file = name
                    break

            if not transfers_file:
                logger.warning("No transfers.txt found in GTFS feed")
                return []

            logger.info(f"Found {transfers_file}")

            with zf.open(transfers_file) as f:
                # Read and decode
                content = f.read().decode('utf-8-sig')
                reader = csv.DictReader(io.StringIO(content))
                # Strip whitespace from field names (some GTFS feeds have trailing spaces)
                reader.fieldnames = [name.strip() for name in reader.fieldnames]

                for row in reader:
                    # Strip all values
                    row = {k: v.strip() if v else '' for k, v in row.items()}
                    transfers.append({
                        'from_stop_id': row.get('from_stop_id', ''),
                        'to_stop_id': row.get('to_stop_id', ''),
                        'from_route_id': row.get('from_route_id', '') or None,
                        'to_route_id': row.get('to_route_id', '') or None,
                        'transfer_type': int(row.get('transfer_type', 0) or 0),
                        'min_transfer_time': int(row.get('min_transfer_time', 0) or 0) if row.get('min_transfer_time') else None,
                    })

                logger.info(f"Parsed {len(transfers)} transfers")

    except Exception as e:
        logger.error(f"Error parsing transfers.txt: {e}")

    return transfers


def get_stop_name(db, stop_id: str, prefix: str) -> Optional[str]:
    """Get stop name from database."""
    # Try with prefix
    full_id = f"{prefix}{stop_id}" if not stop_id.startswith(prefix) else stop_id
    stop = db.query(StopModel).filter(StopModel.id == full_id).first()
    if stop:
        return stop.name

    # Try without prefix
    stop = db.query(StopModel).filter(StopModel.id == stop_id).first()
    if stop:
        return stop.name

    return None


def extract_network_from_route_id(route_id: str) -> Optional[str]:
    """Extract network code from Renfe route_id (e.g., '40T0002C1' -> '40T')."""
    if not route_id:
        return None
    import re
    match = re.match(r'^(\d+T)', route_id)
    if match:
        return match.group(1)
    return None


def get_line_from_route(db, route_id: str) -> Optional[str]:
    """Extract line name from route_id."""
    if not route_id:
        return None

    try:
        from src.gtfs_bc.route.infrastructure.models import RouteModel
        route = db.query(RouteModel).filter(RouteModel.id == route_id).first()
        if route:
            return route.short_name
    except Exception:
        # Route lookup may fail for operators not in our database
        pass

    return None


def import_transfers_for_operator(db, operator_code: str, config: Dict):
    """Import transfers for a specific operator."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Importing transfers for {config['name']}")
    logger.info(f"{'='*60}")

    # Download GTFS
    zip_content = download_gtfs(config['gtfs_url'])
    if not zip_content:
        logger.error(f"Failed to download GTFS for {config['name']}")
        return 0

    # Parse transfers
    transfers = parse_transfers_txt(zip_content)
    if not transfers:
        logger.warning(f"No transfers found for {config['name']}")
        return 0

    # Delete existing transfers for this network
    if config.get('extract_network_from_route', False):
        # Para Renfe: borrar transfers donde stop_id empieza con el prefijo
        deleted = db.query(LineTransferModel).filter(
            LineTransferModel.from_stop_id.like(f"{config['stop_prefix']}%")
        ).delete(synchronize_session=False)
        logger.info(f"Deleted {deleted} existing transfers for prefix {config['stop_prefix']}")
    else:
        deleted = db.query(LineTransferModel).filter(
            LineTransferModel.network_id == config['network_id']
        ).delete()
        logger.info(f"Deleted {deleted} existing transfers for {config['network_id']}")

    # Insert new transfers
    count = 0
    for t in transfers:
        # Build stop IDs with prefix if needed
        from_stop = t['from_stop_id']
        to_stop = t['to_stop_id']

        if not from_stop.startswith(config['stop_prefix']):
            from_stop = f"{config['stop_prefix']}{from_stop}"
        if not to_stop.startswith(config['stop_prefix']):
            to_stop = f"{config['stop_prefix']}{to_stop}"

        # Skip line lookup for operators without routes in our DB (e.g., Renfe)
        skip_line_lookup = config.get('skip_line_lookup', False)

        # Extraer network del route_id para Renfe (40T0002C1 -> 40T)
        network_id = config['network_id']
        if config.get('extract_network_from_route', False):
            extracted = extract_network_from_route_id(t['from_route_id']) or extract_network_from_route_id(t['to_route_id'])
            if extracted:
                network_id = extracted

        transfer = LineTransferModel(
            from_stop_id=from_stop,
            to_stop_id=to_stop,
            from_route_id=t['from_route_id'],
            to_route_id=t['to_route_id'],
            transfer_type=t['transfer_type'],
            min_transfer_time=t['min_transfer_time'],
            from_stop_name=get_stop_name(db, t['from_stop_id'], config['stop_prefix']) if not skip_line_lookup else None,
            to_stop_name=get_stop_name(db, t['to_stop_id'], config['stop_prefix']) if not skip_line_lookup else None,
            from_line=get_line_from_route(db, t['from_route_id']) if not skip_line_lookup else None,
            to_line=get_line_from_route(db, t['to_route_id']) if not skip_line_lookup else None,
            network_id=network_id,
            source='gtfs',
        )
        db.add(transfer)
        count += 1

    db.commit()
    logger.info(f"Imported {count} transfers for {config['name']}")

    return count


def import_metro_malaga_transfers(db):
    """Import Metro Málaga transfers manually (no public GTFS URL available).

    Data from NAP: https://nap.transportes.gob.es/Files/Detail/1296
    Transfers between platforms at same station (6 seconds).
    """
    logger.info(f"\n{'='*60}")
    logger.info("Importing transfers for Metro Málaga (manual)")
    logger.info(f"{'='*60}")

    network_id = 'METRO_MALAGA'
    stop_prefix = 'METRO_MALAGA_'

    # Delete existing
    deleted = db.query(LineTransferModel).filter(
        LineTransferModel.network_id == network_id
    ).delete()
    logger.info(f"Deleted {deleted} existing transfers for {network_id}")

    # Metro Málaga transfers - intercambiadores L1/L2
    # PC = El Perchel (L1 y L2)
    # GD = Guadalmedina (L1 y L2)
    transfers_data = [
        ('PC1', 'PC2', 2, 6),  # El Perchel L1 -> L2
        ('PC2', 'PC1', 2, 6),  # El Perchel L2 -> L1
        ('GD1', 'GD2', 2, 6),  # Guadalmedina L1 -> L2
        ('GD2', 'GD1', 2, 6),  # Guadalmedina L2 -> L1
    ]

    count = 0
    for from_id, to_id, transfer_type, min_time in transfers_data:
        transfer = LineTransferModel(
            from_stop_id=f"{stop_prefix}{from_id}",
            to_stop_id=f"{stop_prefix}{to_id}",
            transfer_type=transfer_type,
            min_transfer_time=min_time,
            network_id=network_id,
            source='nap',
        )
        db.add(transfer)
        count += 1

    db.commit()
    logger.info(f"Imported {count} transfers for Metro Málaga")
    return count


def main():
    """Main entry point."""
    db = SessionLocal()

    try:
        total_count = 0

        for operator_code, config in OPERATORS_WITH_TRANSFERS.items():
            count = import_transfers_for_operator(db, operator_code, config)
            total_count += count

        # Import Metro Málaga manually (no public URL)
        total_count += import_metro_malaga_transfers(db)

        logger.info(f"\n{'='*60}")
        logger.info(f"TOTAL: Imported {total_count} transfers")
        logger.info(f"{'='*60}")

        # Show summary
        result = db.execute(text("""
            SELECT network_id, COUNT(*) as count
            FROM line_transfer
            GROUP BY network_id
            ORDER BY count DESC
        """))

        logger.info("\nTransfers by network:")
        for row in result:
            logger.info(f"  {row[0]}: {row[1]} transfers")

    except Exception as e:
        logger.error(f"Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
