#!/usr/bin/env python3
"""Automatic GTFS data updater.

Downloads, validates, and imports GTFS data from all sources every 15 days.

Usage:
    # Update all sources
    python scripts/auto_update_gtfs.py [--dry-run]

    # Update specific Renfe núcleo only
    python scripts/auto_update_gtfs.py --nucleo 10
    python scripts/auto_update_gtfs.py --nucleo madrid

    # List available sources and núcleos
    python scripts/auto_update_gtfs.py --list

    # Skip validation (not recommended)
    python scripts/auto_update_gtfs.py --skip-validation

Sources:
    - Renfe Cercanías: https://ssl.renfe.com/ftransit/Fichero_CER_FOMENTO/fomento_transit.zip
    - Metro Madrid: CRTM ArcGIS API (import_metro.py)
    - Metro Ligero: CRTM ArcGIS API (import_metro.py)
    - Metro Sevilla: https://metro-sevilla.es/google-transit/google_transit.zip
    - TUSSAM (Bus+Tranvía Sevilla): NAP API (requires NAP_API_KEY env var)

Environment variables:
    NAP_API_KEY: API key for nap.transportes.gob.es (required for TUSSAM)
"""

import sys
import os
import argparse
import logging
import tempfile
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple

import httpx

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.gtfs_validator import GTFSValidator

# Configure logging - try file handler, fall back to console only
log_handlers = [logging.StreamHandler()]
try:
    log_file = Path('/var/log/renfeserver/gtfs_update.log')
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_handlers.append(logging.FileHandler(log_file, mode='a'))
except (PermissionError, OSError):
    pass  # Skip file logging if not writable

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=log_handlers
)
logger = logging.getLogger(__name__)

# Núcleo ID to name mapping (same as in import_gtfs_static.py)
NUCLEO_NAMES = {
    10: 'Madrid',
    20: 'Asturias',
    30: 'Santander',
    31: 'Bilbao',
    32: 'San Sebastián',
    40: 'Zaragoza',
    50: 'Barcelona (Rodalies)',
    60: 'Valencia',
    61: 'Murcia/Alicante',
    62: 'Castellón',
    70: 'Sevilla',
    71: 'Cádiz',
    72: 'Málaga',
}

# GTFS source URLs
GTFS_SOURCES = {
    'renfe_cercanias': {
        'url': 'https://ssl.renfe.com/ftransit/Fichero_CER_FOMENTO/fomento_transit.zip',
        'import_script': 'import_gtfs_static.py',
        'description': 'Renfe Cercanías y Rodalies',
        'is_zip': True,
    },
    # Metro Madrid and Metro Ligero use ArcGIS Feature Service (import_metro.py)
    # They don't have a simple ZIP download - use the existing import_metro.py script
    'metro_madrid': {
        'url': None,  # Uses ArcGIS API directly
        'import_script': 'import_metro.py',
        'description': 'Metro Madrid y Metro Ligero (CRTM)',
        'is_zip': False,
    },
    'metro_sevilla': {
        'url': 'https://metro-sevilla.es/google-transit/google_transit.zip',
        'import_script': 'import_metro_sevilla.py',
        'description': 'Metro de Sevilla',
        'is_zip': True,
        'extract_folder': True,  # Script expects folder, not zip
    },
    'tussam': {
        'url': 'https://nap.transportes.gob.es/api/Fichero/download/1567',
        'import_script': 'import_tranvia_sevilla.py',
        'description': 'TUSSAM (Bus y Tranvía de Sevilla)',
        'is_zip': True,
        'extract_folder': True,
        'requires_api_key': True,  # Requires NAP_API_KEY env var
    },
}


def parse_nucleo_arg(nucleo_arg: str) -> Optional[int]:
    """Parse --nucleo argument (ID or name) and return núcleo ID."""
    if nucleo_arg is None:
        return None

    # Try as integer ID
    try:
        nucleo_id = int(nucleo_arg)
        if nucleo_id in NUCLEO_NAMES:
            return nucleo_id
        logger.error(f"Unknown núcleo ID: {nucleo_id}")
        logger.info(f"Valid IDs: {list(NUCLEO_NAMES.keys())}")
        return None
    except ValueError:
        pass

    # Try as name (case-insensitive)
    nucleo_lower = nucleo_arg.lower()
    for nid, name in NUCLEO_NAMES.items():
        if nucleo_lower in name.lower():
            return nid

    logger.error(f"Unknown núcleo name: {nucleo_arg}")
    logger.info(f"Valid names: {list(NUCLEO_NAMES.values())}")
    return None


def list_sources_and_nucleos():
    """Print available sources and núcleos."""
    print("\n" + "=" * 60)
    print("GTFS SOURCES")
    print("=" * 60)
    for source_id, source in GTFS_SOURCES.items():
        status = "API" if source['url'] is None else "ZIP"
        print(f"  {source_id}: {source['description']} [{status}]")

    print("\n" + "=" * 60)
    print("RENFE NÚCLEOS (for --nucleo option)")
    print("=" * 60)
    print(f"{'ID':<5} {'Name'}")
    print("-" * 30)
    for nid in sorted(NUCLEO_NAMES.keys()):
        print(f"{nid:<5} {NUCLEO_NAMES[nid]}")
    print("=" * 60)
    print("\nUsage examples:")
    print("  python auto_update_gtfs.py --nucleo 10       # Update Madrid only")
    print("  python auto_update_gtfs.py --nucleo sevilla  # Update Sevilla only")


def download_file(url: str, dest_path: Path, headers: dict = None) -> bool:
    """Download a file from URL with optional headers."""
    try:
        logger.info(f"Downloading {url}...")
        with httpx.Client(timeout=120.0, follow_redirects=True) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()

            dest_path.parent.mkdir(parents=True, exist_ok=True)
            with open(dest_path, 'wb') as f:
                f.write(response.content)

            logger.info(f"Downloaded {len(response.content)} bytes to {dest_path}")
            return True
    except Exception as e:
        logger.error(f"Failed to download {url}: {e}")
        return False


def download_and_validate(url: str, dest_path: Path, source_name: str,
                          skip_validation: bool = False,
                          headers: dict = None) -> Tuple[bool, Path]:
    """Download and validate GTFS before importing.

    Returns (success, path) tuple.
    """
    if not download_file(url, dest_path, headers=headers):
        return False, dest_path

    if skip_validation:
        logger.info(f"Skipping validation for {source_name}")
        return True, dest_path

    logger.info(f"Validating GTFS data for {source_name}...")
    validator = GTFSValidator(dest_path)
    is_valid, report = validator.validate()

    if not is_valid:
        logger.error(f"GTFS validation failed for {source_name}:")
        for error in report.errors:
            logger.error(f"  - {error}")
        return False, dest_path

    logger.info(f"GTFS validated: {report.summary()}")

    # Log warnings but don't fail
    for warning in report.warnings:
        logger.warning(f"  - {warning}")

    return True, dest_path


def run_import_script(script_name: str, *args) -> bool:
    """Run an import script."""
    script_path = project_root / 'scripts' / script_name
    if not script_path.exists():
        logger.error(f"Script not found: {script_path}")
        return False

    cmd = [sys.executable, str(script_path)] + list(args)
    logger.info(f"Running: {' '.join(cmd)}")

    # Set PYTHONPATH to project root so scripts can find modules
    env = os.environ.copy()
    env['PYTHONPATH'] = str(project_root)

    try:
        result = subprocess.run(
            cmd,
            cwd=str(project_root),
            env=env,
            capture_output=True,
            text=True,
            timeout=1800  # 30 minutes max (Renfe has millions of stop_times)
        )

        if result.returncode == 0:
            logger.info(f"Script {script_name} completed successfully")
            if result.stdout:
                logger.debug(result.stdout[-1000:])  # Last 1000 chars
            return True
        else:
            logger.error(f"Script {script_name} failed with code {result.returncode}")
            if result.stderr:
                logger.error(result.stderr[-1000:])
            return False
    except subprocess.TimeoutExpired:
        logger.error(f"Script {script_name} timed out")
        return False
    except Exception as e:
        logger.error(f"Error running {script_name}: {e}")
        return False


def update_renfe_cercanias(dry_run: bool = False, skip_validation: bool = False) -> bool:
    """Update Renfe Cercanías GTFS data (all núcleos)."""
    source = GTFS_SOURCES['renfe_cercanias']
    logger.info(f"Updating {source['description']}...")

    if dry_run:
        logger.info("[DRY RUN] Would download, validate, and import Renfe Cercanías")
        return True

    # Download and validate
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = Path(tmpdir) / 'fomento_transit.zip'

        success, _ = download_and_validate(
            source['url'], zip_path, 'Renfe Cercanías',
            skip_validation=skip_validation
        )
        if not success:
            return False

        # Run import
        return run_import_script(source['import_script'], str(zip_path))


def update_renfe_nucleo(nucleo_id: int, dry_run: bool = False,
                        skip_validation: bool = False) -> bool:
    """Update a specific Renfe núcleo only."""
    nucleo_name = NUCLEO_NAMES.get(nucleo_id, f'Unknown ({nucleo_id})')
    source = GTFS_SOURCES['renfe_cercanias']
    logger.info(f"Updating Renfe núcleo {nucleo_id} ({nucleo_name})...")

    if dry_run:
        logger.info(f"[DRY RUN] Would download, validate, and import núcleo {nucleo_id}")
        return True

    # Download and validate
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = Path(tmpdir) / 'fomento_transit.zip'

        success, _ = download_and_validate(
            source['url'], zip_path, f'Renfe núcleo {nucleo_id}',
            skip_validation=skip_validation
        )
        if not success:
            return False

        # Run import with --nucleo filter
        return run_import_script(source['import_script'], str(zip_path),
                                 '--nucleo', str(nucleo_id))


def update_metro_madrid(dry_run: bool = False) -> bool:
    """Update Metro Madrid and Metro Ligero data."""
    source = GTFS_SOURCES['metro_madrid']
    logger.info(f"Updating {source['description']}...")

    if dry_run:
        logger.info("[DRY RUN] Would import Metro Madrid/ML from CRTM ArcGIS")
        return True

    # import_metro.py fetches directly from ArcGIS API
    return run_import_script(source['import_script'])


def update_metro_sevilla(dry_run: bool = False, skip_validation: bool = False) -> bool:
    """Update Metro de Sevilla GTFS data."""
    import zipfile

    source = GTFS_SOURCES['metro_sevilla']
    logger.info(f"Updating {source['description']}...")

    if dry_run:
        logger.info("[DRY RUN] Would download, validate, and import Metro Sevilla")
        return True

    # Download, validate, and extract
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = Path(tmpdir) / 'metro_sevilla.zip'
        extract_path = Path(tmpdir) / 'metro_sevilla_gtfs'

        success, _ = download_and_validate(
            source['url'], zip_path, 'Metro Sevilla',
            skip_validation=skip_validation
        )
        if not success:
            return False

        # Extract zip to folder (script expects folder, not zip)
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(extract_path)
            logger.info(f"Extracted GTFS to {extract_path}")
        except Exception as e:
            logger.error(f"Failed to extract zip: {e}")
            return False

        # Run import with extracted folder
        return run_import_script(source['import_script'], str(extract_path))


def update_tussam(dry_run: bool = False, skip_validation: bool = False) -> bool:
    """Update TUSSAM (Bus y Tranvía de Sevilla) from NAP API."""
    import zipfile

    source = GTFS_SOURCES['tussam']
    logger.info(f"Updating {source['description']}...")

    # Check for API key
    api_key = os.environ.get('NAP_API_KEY')
    if not api_key:
        logger.warning("NAP_API_KEY not set - skipping TUSSAM update")
        logger.warning("Set NAP_API_KEY environment variable to enable TUSSAM updates")
        return True  # Not a failure, just skipped

    if dry_run:
        logger.info("[DRY RUN] Would download, validate, and import TUSSAM")
        return True

    # Download, validate with API key header
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = Path(tmpdir) / 'tussam.zip'
        extract_path = Path(tmpdir) / 'tussam_gtfs'

        headers = {'ApiKey': api_key}
        success, _ = download_and_validate(
            source['url'], zip_path, 'TUSSAM',
            skip_validation=skip_validation,
            headers=headers
        )
        if not success:
            return False

        # Extract zip
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(extract_path)
            logger.info(f"Extracted GTFS to {extract_path}")
        except Exception as e:
            logger.error(f"Failed to extract zip: {e}")
            return False

        # Run tranvia import (only imports tranvia route, not buses)
        return run_import_script(source['import_script'], str(extract_path))


def update_renfe_nucleos(dry_run: bool = False) -> bool:
    """Update Renfe núcleos from GeoJSON."""
    logger.info("Updating Renfe núcleos...")

    if dry_run:
        logger.info("[DRY RUN] Would update Renfe núcleos")
        return True

    return run_import_script('import_renfe_nucleos.py')


def update_stop_connections(dry_run: bool = False) -> bool:
    """Update stop correspondences (Metro <-> Cercanías)."""
    logger.info("Updating stop correspondences...")

    if dry_run:
        logger.info("[DRY RUN] Would update stop correspondences")
        return True

    return run_import_script('populate_stop_connections.py')


def main():
    """Run the GTFS auto-update."""
    parser = argparse.ArgumentParser(
        description='Automatic GTFS data updater with validation'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    parser.add_argument(
        '--nucleo',
        help='Update only this Renfe núcleo (ID or name). Examples: 10, madrid, sevilla'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List available GTFS sources and Renfe núcleos'
    )
    parser.add_argument(
        '--skip-validation',
        action='store_true',
        help='Skip GTFS validation before import (not recommended)'
    )

    args = parser.parse_args()

    # Handle --list
    if args.list:
        list_sources_and_nucleos()
        return 0

    # Parse nucleo filter
    nucleo_filter = None
    if args.nucleo:
        nucleo_filter = parse_nucleo_arg(args.nucleo)
        if nucleo_filter is None:
            return 1

    logger.info("=" * 60)
    logger.info(f"GTFS AUTO-UPDATE STARTING - {datetime.now().isoformat()}")
    logger.info("=" * 60)

    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
    if args.skip_validation:
        logger.warning("VALIDATION DISABLED - Importing without validation")
    if nucleo_filter:
        logger.info(f"NUCLEO FILTER: Only updating núcleo {nucleo_filter} ({NUCLEO_NAMES.get(nucleo_filter, 'Unknown')})")

    results = {}

    # If nucleo filter is set, only update that specific nucleo
    if nucleo_filter:
        results['renfe_nucleo'] = update_renfe_nucleo(
            nucleo_filter, args.dry_run, args.skip_validation
        )
    else:
        # Full update

        # 1. Update Renfe núcleos first (base data)
        results['renfe_nucleos'] = update_renfe_nucleos(args.dry_run)

        # 2. Update Renfe Cercanías
        results['renfe_cercanias'] = update_renfe_cercanias(
            args.dry_run, args.skip_validation
        )

        # 3. Update Metro Madrid/ML
        results['metro_madrid'] = update_metro_madrid(args.dry_run)

        # 4. Update Metro Sevilla
        results['metro_sevilla'] = update_metro_sevilla(
            args.dry_run, args.skip_validation
        )

        # 5. Update TUSSAM (Tranvía Sevilla)
        results['tussam'] = update_tussam(args.dry_run, args.skip_validation)

        # 6. Update stop correspondences
        results['stop_connections'] = update_stop_connections(args.dry_run)

    # Summary
    logger.info("=" * 60)
    logger.info("UPDATE SUMMARY")
    logger.info("=" * 60)

    all_success = True
    for name, success in results.items():
        status = "OK" if success else "FAILED"
        logger.info(f"  {name}: {status}")
        if not success:
            all_success = False

    logger.info("=" * 60)

    if all_success:
        logger.info("All updates completed successfully!")
    else:
        logger.warning("Some updates failed - check logs for details")

    # Note about API key (only for full updates)
    if not nucleo_filter and not os.environ.get('NAP_API_KEY'):
        logger.info("\nNOTE: Set NAP_API_KEY env var to enable automatic TUSSAM updates.")
        logger.info("Get API key from: https://nap.transportes.gob.es")

    return 0 if all_success else 1


if __name__ == "__main__":
    sys.exit(main())
