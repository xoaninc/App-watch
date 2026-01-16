#!/usr/bin/env python3
"""Populate province to nucleo mapping.

This script creates the mapping between Spanish provinces and Renfe regional
networks (núcleos). Most provinces map to a single núcleo, except:
- Murcia/Alicante (id 41): covers Murcia and Alicante provinces
- Rodalies de Catalunya (id 50): covers Barcelona, Tarragona, Lleida, Girona
"""

import sys
import logging
from sqlalchemy import text

from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Province to Nucleo mapping
PROVINCE_NUCLEO_MAPPING = {
    # Núcleo 10: Madrid
    'Madrid': (10, 'Madrid'),

    # Núcleo 20: Asturias
    'Asturias': (20, 'Asturias'),

    # Núcleo 30: Sevilla
    'Sevilla': (30, 'Sevilla'),

    # Núcleo 31: Cádiz
    'Cádiz': (31, 'Cádiz'),

    # Núcleo 32: Málaga
    'Málaga': (32, 'Málaga'),

    # Núcleo 40: Valencia
    'Valencia': (40, 'Valencia'),

    # Núcleo 41: Murcia/Alicante (covers 2 provinces)
    'Murcia': (41, 'Murcia/Alicante'),
    'Alicante': (41, 'Murcia/Alicante'),

    # Núcleo 50: Rodalies de Catalunya (covers 4 provinces)
    'Barcelona': (50, 'Rodalies de Catalunya'),
    'Tarragona': (50, 'Rodalies de Catalunya'),
    'Lleida': (50, 'Rodalies de Catalunya'),
    'Girona': (50, 'Rodalies de Catalunya'),

    # Núcleo 60: Bilbao
    'Vizcaya': (60, 'Bilbao'),

    # Núcleo 61: San Sebastián
    'Guipúzcoa': (61, 'San Sebastián'),

    # Núcleo 62: Cantabria
    'Cantabria': (62, 'Cantabria'),

    # Núcleo 70: Zaragoza
    'Zaragoza': (70, 'Zaragoza'),
}


def populate_province_nucleo_mapping(db) -> dict:
    """Populate nucleo mapping for all provinces.

    Args:
        db: Database session

    Returns:
        Dictionary with statistics
    """
    stats = {
        'total_provinces': 0,
        'mapped': 0,
        'not_mapped': 0,
        'errors': 0,
    }

    # Get all provinces
    provinces = db.execute(
        text("SELECT id, code, name FROM spanish_provinces ORDER BY name")
    ).fetchall()

    logger.info(f"Found {len(provinces)} provinces in database")

    for province in provinces:
        province_id, province_code, province_name = province
        stats['total_provinces'] += 1

        # Check if province has a mapping
        if province_name in PROVINCE_NUCLEO_MAPPING:
            nucleo_id, nucleo_name = PROVINCE_NUCLEO_MAPPING[province_name]

            try:
                # Update province with nucleo mapping
                db.execute(
                    text("""
                        UPDATE spanish_provinces
                        SET nucleo_id = :nucleo_id, nucleo_name = :nucleo_name
                        WHERE id = :province_id
                    """),
                    {
                        'nucleo_id': nucleo_id,
                        'nucleo_name': nucleo_name,
                        'province_id': province_id
                    }
                )
                stats['mapped'] += 1
                logger.debug(f"Mapped {province_name} → {nucleo_name} (id: {nucleo_id})")

            except Exception as e:
                logger.error(f"Error mapping {province_name}: {e}")
                stats['errors'] += 1

        else:
            stats['not_mapped'] += 1
            logger.debug(f"No nucleo mapping for {province_name}")

    db.commit()
    return stats


def validate_mapping(db) -> None:
    """Validate the province-nucleo mapping."""
    logger.info("\nProvince to Nucleo Mapping:")
    logger.info("-" * 50)

    results = db.execute(
        text("""
            SELECT nucleo_name, COUNT(*) as count, STRING_AGG(name, ', ') as provinces
            FROM spanish_provinces
            WHERE nucleo_id IS NOT NULL
            GROUP BY nucleo_name
            ORDER BY nucleo_name
        """)
    ).fetchall()

    for row in results:
        logger.info(f"{row.nucleo_name}:")
        logger.info(f"  Provinces: {row.provinces}")
        logger.info(f"  Count: {row.count}")

    # Show unmapped provinces
    unmapped = db.execute(
        text("""
            SELECT name
            FROM spanish_provinces
            WHERE nucleo_id IS NULL
            ORDER BY name
        """)
    ).fetchall()

    if unmapped:
        logger.info("\nUnmapped provinces (no Renfe service):")
        unmapped_names = [row.name for row in unmapped]
        for name in unmapped_names:
            logger.info(f"  - {name}")


def main():
    """Main entry point."""
    db = SessionLocal()
    try:
        logger.info("Starting province-nucleo mapping population...")
        stats = populate_province_nucleo_mapping(db)

        # Print summary
        logger.info("\n" + "="*50)
        logger.info("Province Mapping Summary")
        logger.info("="*50)
        logger.info(f"Total provinces: {stats['total_provinces']}")
        logger.info(f"Mapped: {stats['mapped']}")
        logger.info(f"Not mapped: {stats['not_mapped']}")
        logger.info(f"Errors: {stats['errors']}")
        logger.info("="*50)

        # Show validation
        validate_mapping(db)

        logger.info("\nProvince-nucleo mapping completed successfully")
        sys.exit(0)

    except Exception as e:
        logger.error(f"Error: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
