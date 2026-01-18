#!/usr/bin/env python3
"""Automatic GTFS data updater.

Downloads and imports GTFS data from all sources every 15 days.

Usage:
    python scripts/auto_update_gtfs.py [--dry-run]

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
import logging
import tempfile
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional

import httpx

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/var/log/renfeserver/gtfs_update.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

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


def update_renfe_cercanias(dry_run: bool = False) -> bool:
    """Update Renfe Cercanías GTFS data."""
    source = GTFS_SOURCES['renfe_cercanias']
    logger.info(f"Updating {source['description']}...")

    if dry_run:
        logger.info("[DRY RUN] Would download and import Renfe Cercanías")
        return True

    # Download to temp file
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = Path(tmpdir) / 'fomento_transit.zip'

        if not download_file(source['url'], zip_path):
            return False

        # Run import
        return run_import_script(source['import_script'], str(zip_path))


def update_metro_madrid(dry_run: bool = False) -> bool:
    """Update Metro Madrid and Metro Ligero data."""
    source = GTFS_SOURCES['metro_madrid']
    logger.info(f"Updating {source['description']}...")

    if dry_run:
        logger.info("[DRY RUN] Would import Metro Madrid/ML from CRTM ArcGIS")
        return True

    # import_metro.py fetches directly from ArcGIS API
    return run_import_script(source['import_script'])


def update_metro_sevilla(dry_run: bool = False) -> bool:
    """Update Metro de Sevilla GTFS data."""
    import zipfile

    source = GTFS_SOURCES['metro_sevilla']
    logger.info(f"Updating {source['description']}...")

    if dry_run:
        logger.info("[DRY RUN] Would download and import Metro Sevilla")
        return True

    # Download and extract to temp folder
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = Path(tmpdir) / 'metro_sevilla.zip'
        extract_path = Path(tmpdir) / 'metro_sevilla_gtfs'

        if not download_file(source['url'], zip_path):
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


def update_tussam(dry_run: bool = False) -> bool:
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
        logger.info("[DRY RUN] Would download and import TUSSAM")
        return True

    # Download with API key header
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = Path(tmpdir) / 'tussam.zip'
        extract_path = Path(tmpdir) / 'tussam_gtfs'

        headers = {'apikey': api_key}
        if not download_file(source['url'], zip_path, headers=headers):
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
    dry_run = '--dry-run' in sys.argv

    logger.info("=" * 60)
    logger.info(f"GTFS AUTO-UPDATE STARTING - {datetime.now().isoformat()}")
    logger.info("=" * 60)

    if dry_run:
        logger.info("DRY RUN MODE - No changes will be made")

    results = {}

    # 1. Update Renfe núcleos first (base data)
    results['renfe_nucleos'] = update_renfe_nucleos(dry_run)

    # 2. Update Renfe Cercanías
    results['renfe_cercanias'] = update_renfe_cercanias(dry_run)

    # 3. Update Metro Madrid/ML
    results['metro_madrid'] = update_metro_madrid(dry_run)

    # 4. Update Metro Sevilla
    results['metro_sevilla'] = update_metro_sevilla(dry_run)

    # 5. Update TUSSAM (Tranvía Sevilla)
    results['tussam'] = update_tussam(dry_run)

    # 6. Update stop correspondences
    results['stop_connections'] = update_stop_connections(dry_run)

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

    # Note about API key
    if not os.environ.get('NAP_API_KEY'):
        logger.info("\nNOTE: Set NAP_API_KEY env var to enable automatic TUSSAM updates.")
        logger.info("Get API key from: https://nap.transportes.gob.es")

    return 0 if all_success else 1


if __name__ == "__main__":
    sys.exit(main())
