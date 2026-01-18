#!/usr/bin/env python3
"""Automatic GTFS data updater.

Downloads and imports GTFS data from all sources every 15 days.

Usage:
    python scripts/auto_update_gtfs.py [--dry-run]

Sources:
    - Renfe Cercanías: https://ssl.renfe.com/ftransit/Fichero_CER_FOMENTO/fomento_transit.zip
    - Metro Madrid: CRTM ArcGIS (manual import from local data)
    - Metro Ligero: CRTM ArcGIS (manual import from local data)
    - Metro Sevilla: Manual GTFS download
    - Tranvía Sevilla: TUSSAM GTFS (manual import from local data)
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
    },
    # Metro Madrid and Metro Ligero use ArcGIS Feature Service (import_metro.py)
    # They don't have a simple ZIP download - use the existing import_metro.py script
    'metro_madrid': {
        'url': None,  # Uses ArcGIS API directly
        'import_script': 'import_metro.py',
        'description': 'Metro Madrid y Metro Ligero (CRTM)',
    },
}

# Additional manual sources (require local files)
MANUAL_SOURCES = {
    'metro_sevilla': {
        'import_script': 'import_metro_sevilla.py',
        'description': 'Metro de Sevilla',
        'data_folder': 'data/metro_sevilla_gtfs',
    },
    'tranvia_sevilla': {
        'import_script': 'import_tranvia_sevilla.py',
        'description': 'Tranvía de Sevilla (TUSSAM)',
        'data_folder': 'data/tussam_gtfs',
    },
}


def download_file(url: str, dest_path: Path) -> bool:
    """Download a file from URL."""
    try:
        logger.info(f"Downloading {url}...")
        with httpx.Client(timeout=120.0, follow_redirects=True) as client:
            response = client.get(url)
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

    try:
        result = subprocess.run(
            cmd,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=600  # 10 minutes max
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

    # 4. Update stop correspondences
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

    # Note about manual sources
    logger.info("\nNOTE: Metro Sevilla and Tranvía Sevilla require manual GTFS updates.")
    logger.info("When new GTFS files are available, run:")
    logger.info("  python scripts/import_metro_sevilla.py <gtfs_folder>")
    logger.info("  python scripts/import_tranvia_sevilla.py <gtfs_folder>")

    return 0 if all_success else 1


if __name__ == "__main__":
    sys.exit(main())
