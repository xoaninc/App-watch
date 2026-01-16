#!/usr/bin/env python3
"""Import Spanish province boundaries from GADM GeoJSON into PostGIS.

Usage:
    python scripts/import_province_boundaries.py path/to/gadm41_ESP_2.json

Download GADM data from:
    https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_ESP_2.json

This script:
1. Reads GADM GeoJSON file
2. Transforms geometries to PostGIS format
3. Inserts province boundaries into spanish_provinces table
4. Validates all provinces have valid geometries
"""

import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from sqlalchemy import text

from core.database import SessionLocal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Province name mapping from GADM to our standardized names
PROVINCE_NAME_MAPPING = {
    "A Coruña": "A Coruña",
    "Álava": "Álava",
    "Albacete": "Albacete",
    "Alicante": "Alicante",
    "Almería": "Almería",
    "Asturias": "Asturias",
    "Ávila": "Ávila",
    "Badajoz": "Badajoz",
    "Barcelona": "Barcelona",
    "Bizkaia": "Vizcaya",
    "Burgos": "Burgos",
    "Cáceres": "Cáceres",
    "Cádiz": "Cádiz",
    "Cantabria": "Cantabria",
    "Castellón": "Castellón",
    "Ceuta": "Ceuta",
    "Ciudad Real": "Ciudad Real",
    "Córdoba": "Córdoba",
    "Cuenca": "Cuenca",
    "Gipuzkoa": "Guipúzcoa",
    "Girona": "Girona",
    "Granada": "Granada",
    "Guadalajara": "Guadalajara",
    "Huelva": "Huelva",
    "Huesca": "Huesca",
    "Illes Balears": "Baleares",
    "Jaén": "Jaén",
    "La Rioja": "La Rioja",
    "Las Palmas": "Las Palmas",
    "León": "León",
    "Lleida": "Lleida",
    "Lugo": "Lugo",
    "Madrid": "Madrid",
    "Málaga": "Málaga",
    "Melilla": "Melilla",
    "Murcia": "Murcia",
    "Navarra": "Navarra",
    "Ourense": "Ourense",
    "Palencia": "Palencia",
    "Pontevedra": "Pontevedra",
    "Salamanca": "Salamanca",
    "Santa Cruz de Tenerife": "Santa Cruz de Tenerife",
    "Segovia": "Segovia",
    "Sevilla": "Sevilla",
    "Soria": "Soria",
    "Tarragona": "Tarragona",
    "Teruel": "Teruel",
    "Toledo": "Toledo",
    "Valencia": "Valencia",
    "Valladolid": "Valladolid",
    "Zamora": "Zamora",
    "Zaragoza": "Zaragoza",
}


def load_geojson(file_path: str) -> Dict[str, Any]:
    """Load and parse GeoJSON file."""
    logger.info(f"Loading GeoJSON from {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    logger.info(f"Loaded {len(data.get('features', []))} features")
    return data


def import_provinces(db_session, geojson_data: Dict[str, Any]) -> None:
    """Import province boundaries from GeoJSON into database."""

    features = geojson_data.get('features', [])
    if not features:
        raise ValueError("No features found in GeoJSON")

    inserted_count = 0
    skipped_count = 0

    for feature in features:
        properties = feature.get('properties', {})
        geometry = feature.get('geometry')

        if not geometry:
            logger.warning(f"Skipping feature without geometry")
            skipped_count += 1
            continue

        # Extract province information
        gadm_name = properties.get('NAME_2')  # Level 2 = Province
        autonomous_community = properties.get('NAME_1')  # Level 1
        iso_code = properties.get('HASC_2')

        if not gadm_name:
            logger.warning(f"Skipping feature without NAME_2")
            skipped_count += 1
            continue

        # Map GADM name to our standardized name
        province_name = PROVINCE_NAME_MAPPING.get(gadm_name, gadm_name)

        # Generate province code (first 3 letters of name)
        province_code = province_name[:3].upper().replace(' ', '')

        # Convert GeoJSON geometry to PostGIS format
        geometry_json = json.dumps(geometry)

        try:
            # Insert province with geometry
            db_session.execute(
                text("""
                    INSERT INTO spanish_provinces
                    (code, name, name_official, autonomous_community, iso_code, geometry)
                    VALUES (
                        :code,
                        :name,
                        :name_official,
                        :community,
                        :iso_code,
                        ST_GeomFromGeoJSON(:geometry)
                    )
                    ON CONFLICT (code) DO UPDATE SET
                        name = EXCLUDED.name,
                        geometry = EXCLUDED.geometry
                """),
                {
                    'code': province_code,
                    'name': province_name,
                    'name_official': gadm_name,
                    'community': autonomous_community,
                    'iso_code': iso_code,
                    'geometry': geometry_json
                }
            )
            inserted_count += 1
            logger.info(f"Imported: {province_name}")

        except Exception as e:
            logger.error(f"Error importing {province_name}: {e}")
            skipped_count += 1

    db_session.commit()
    logger.info(f"Import complete: {inserted_count} inserted, {skipped_count} skipped")


def validate_geometries(db_session) -> None:
    """Validate all province geometries are valid and properly indexed."""
    logger.info("Validating geometries...")

    # Check for invalid geometries
    result = db_session.execute(
        text("""
            SELECT code, name, ST_IsValid(geometry) as is_valid
            FROM spanish_provinces
            WHERE NOT ST_IsValid(geometry)
        """)
    ).fetchall()

    if result:
        logger.warning(f"Found {len(result)} invalid geometries:")
        for row in result:
            logger.warning(f"  - {row.name} ({row.code})")
    else:
        logger.info("All geometries are valid")

    # Check total count
    count = db_session.execute(text("SELECT COUNT(*) FROM spanish_provinces")).scalar()
    logger.info(f"Total provinces in database: {count}")

    # Check spatial index exists
    index_exists = db_session.execute(
        text("""
            SELECT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE indexname = 'idx_spanish_provinces_geometry'
            )
        """)
    ).scalar()

    if index_exists:
        logger.info("Spatial index exists and is ready")
    else:
        logger.warning("Spatial index not found!")


def main():
    if len(sys.argv) < 2:
        print("Usage: python import_province_boundaries.py <path_to_geojson>")
        print("\nDownload GeoJSON from:")
        print("https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_ESP_2.json")
        sys.exit(1)

    geojson_path = sys.argv[1]

    if not Path(geojson_path).exists():
        logger.error(f"File not found: {geojson_path}")
        sys.exit(1)

    db = SessionLocal()
    try:
        # Load and import data
        geojson_data = load_geojson(geojson_path)
        import_provinces(db, geojson_data)

        # Validate
        validate_geometries(db)

        logger.info("Province boundary import completed successfully")

    except Exception as e:
        logger.error(f"Import failed: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
