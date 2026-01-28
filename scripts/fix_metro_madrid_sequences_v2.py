#!/usr/bin/env python3
"""Fix Metro Madrid stop sequences and route metadata.

This script fixes:
- Stop sequences to match correct order
- long_name values
- is_circular flag for circular lines

Usage:
    python scripts/fix_metro_madrid_sequences_v2.py [--dry-run]
"""

import os
import sys
import argparse
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Expected stop sequences for each line (first station listed is seq 0)
METRO_SEQUENCES = {
    'METRO_1': [
        'Pinar De Chamartin', 'Bambu', 'Chamartin', 'Plaza De Castilla', 'Valdeacederas',
        'Tetuan', 'Estrecho', 'Alvarado', 'Cuatro Caminos', 'Rios Rosas', 'Iglesia',
        'Bilbao', 'Tribunal', 'Gran Via', 'Sol', 'Tirso De Molina', 'Anton Martin',
        'Estacion Del Arte', 'Atocha', 'Menendez Pelayo', 'Pacifico', 'Puente De Vallecas',
        'Nueva Numancia', 'Portazgo', 'Buenos Aires', 'Alto Del Arenal', 'Miguel Hernandez',
        'Sierra De Guadalupe', 'Villa De Vallecas', 'Congosto', 'La Gavia', 'Valdecarros'
    ],
    'METRO_3': [
        'El Casar', 'Villaverde Alto', 'San Cristobal', 'Villaverde Bajo Cruce',
        'Ciudad De Los Angeles', 'San Fermin-Orcasur', 'Hospital 12 De Octubre',
        'Almendrales', 'Legazpi', 'Delicias', 'Palos De La Frontera', 'Embajadores',
        'Lavapies', 'Sol', 'Callao', 'Plaza De España', 'Ventura Rodriguez',
        'Argüelles', 'Moncloa'
    ],
    'METRO_7': [
        'Estadio Metropolitano', 'Las Musas', 'San Blas', 'Simancas', 'Garcia Noblejas',
        'Ascao', 'Pueblo Nuevo', 'Barrio De La Concepcion', 'Parque De Las Avenidas',
        'Cartagena', 'Avenida De America', 'Gregorio Marañon', 'Alonso Cano', 'Canal',
        'Islas Filipinas', 'Guzman El Bueno', 'Francos Rodriguez', 'Valdezarza',
        'Antonio Machado', 'Peñagrande', 'Avenida De La Ilustracion', 'Lacoma',
        'Arroyofresno', 'Pitis'
    ],
    'METRO_9': [
        'Paco De Lucia', 'Herrera Oria', 'Barrio Del Pilar', 'Ventilla',
        'Plaza De Castilla', 'Duque De Pastrana', 'Pio Xii', 'Colombia', 'Concha Espina',
        'Cruz Del Rayo', 'Avenida De America', 'Nuñez De Balboa', 'Principe De Vergara',
        'Ibiza', 'Sainz De Baranda', 'Estrella', 'Vinateros', 'Artilleros', 'Pavones',
        'Valdebernardo', 'Vicalvaro', 'San Cipriano', 'Puerta De Arganda'
    ],
    'METRO_10': [
        'Puerta Del Sur', 'Joaquin Vilumbrales', 'Cuatro Vientos', 'Aviacion Española',
        'Colonia Jardin', 'Casa De Campo', 'Batan', 'Lago', 'Principe Pio',
        'Plaza De España', 'Tribunal', 'Alonso Martinez', 'Gregorio Marañon',
        'Nuevos Ministerios', 'Santiago Bernabeu', 'Cuzco', 'Plaza De Castilla',
        'Chamartin', 'Begoña', 'Fuencarral', 'Tres Olivos'
    ],
    'METRO_10B': [
        'Tres Olivos', 'La Moraleja', 'Marques De La Valdavia', 'Manuel De Falla',
        'Hospital Infanta Sofia'
    ],
}

# Route metadata updates
ROUTE_METADATA = {
    'METRO_7': {'long_name': 'Estadio Metropolitano - Pitis'},
    'METRO_10': {'long_name': 'Puerta del Sur - Tres Olivos'},
    'METRO_10B': {'long_name': 'Tres Olivos - Hospital Infanta Sofía'},
    'METRO_12': {'long_name': 'MetroSur'},
    'METRO_R': {'long_name': 'Ramal'},
}

# Circular lines
CIRCULAR_LINES = ['METRO_6', 'METRO_12']


def add_is_circular_column(db, dry_run):
    """Add is_circular column if it doesn't exist."""
    logger.info("Checking is_circular column...")

    if dry_run:
        logger.info("  Would add is_circular column")
        return

    db.execute(text('ALTER TABLE gtfs_routes ADD COLUMN IF NOT EXISTS is_circular BOOLEAN DEFAULT false'))
    db.commit()
    logger.info("  ✓ is_circular column ready")


def set_circular_lines(db, dry_run):
    """Set is_circular = true for circular lines."""
    logger.info("Setting circular lines...")

    for route_id in CIRCULAR_LINES:
        if dry_run:
            logger.info(f"  Would set {route_id} as circular")
        else:
            db.execute(text('''
                UPDATE gtfs_routes SET is_circular = true WHERE id = :route_id
            '''), {'route_id': route_id})
            logger.info(f"  ✓ {route_id} marked as circular")

    if not dry_run:
        db.commit()


def update_route_metadata(db, dry_run):
    """Update long_name and other metadata for routes."""
    logger.info("Updating route metadata...")

    for route_id, metadata in ROUTE_METADATA.items():
        if 'long_name' in metadata:
            if dry_run:
                logger.info(f"  Would update {route_id} long_name to '{metadata['long_name']}'")
            else:
                db.execute(text('''
                    UPDATE gtfs_routes SET long_name = :long_name WHERE id = :route_id
                '''), {'route_id': route_id, 'long_name': metadata['long_name']})
                logger.info(f"  ✓ {route_id} long_name = '{metadata['long_name']}'")

    if not dry_run:
        db.commit()


def fix_stop_sequence(db, route_id, expected_stops, dry_run):
    """Fix stop sequence for a route to match expected order."""
    logger.info(f"Fixing {route_id}...")

    # Get current stops
    current = db.execute(text('''
        SELECT srs.id, s.name, srs.sequence
        FROM gtfs_stop_route_sequence srs
        JOIN gtfs_stops s ON srs.stop_id = s.id
        WHERE srs.route_id = :route_id
        ORDER BY srs.sequence
    '''), {'route_id': route_id}).fetchall()

    current_names = [row[1] for row in current]

    # Check if already correct
    if current_names == expected_stops:
        logger.info(f"  ✓ Already correct")
        return

    # Delete current sequence
    if not dry_run:
        db.execute(text('''
            DELETE FROM gtfs_stop_route_sequence WHERE route_id = :route_id
        '''), {'route_id': route_id})

    # Reset sequence
    if not dry_run:
        max_id = db.execute(text('SELECT MAX(id) FROM gtfs_stop_route_sequence')).scalar() or 0
        db.execute(text("SELECT setval('gtfs_stop_route_sequence_id_seq', :next_id, false)"),
                   {'next_id': max_id + 1})

    # Insert in correct order
    for seq, stop_name in enumerate(expected_stops):
        # Find stop_id by name
        stop = db.execute(text('''
            SELECT id FROM gtfs_stops
            WHERE name ILIKE :name AND id LIKE 'METRO_%'
            LIMIT 1
        '''), {'name': stop_name}).fetchone()

        if stop:
            if not dry_run:
                db.execute(text('''
                    INSERT INTO gtfs_stop_route_sequence (route_id, stop_id, sequence)
                    VALUES (:route_id, :stop_id, :seq)
                '''), {'route_id': route_id, 'stop_id': stop[0], 'seq': seq})
        else:
            logger.warning(f"  Stop not found: {stop_name}")

    if not dry_run:
        db.commit()

    logger.info(f"  ✓ Fixed: {expected_stops[0]} → {expected_stops[-1]} ({len(expected_stops)} stops)")


def main():
    parser = argparse.ArgumentParser(description='Fix Metro Madrid stop sequences')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    args = parser.parse_args()

    db = SessionLocal()

    try:
        if args.dry_run:
            logger.info("DRY RUN - No changes will be made\n")

        # Add is_circular column
        add_is_circular_column(db, args.dry_run)

        # Set circular lines
        set_circular_lines(db, args.dry_run)

        # Update route metadata
        update_route_metadata(db, args.dry_run)

        # Fix stop sequences
        logger.info("\nFixing stop sequences...")
        for route_id, expected_stops in METRO_SEQUENCES.items():
            fix_stop_sequence(db, route_id, expected_stops, args.dry_run)

        logger.info("\n" + "=" * 60)
        logger.info("COMPLETE")
        if args.dry_run:
            logger.info("[DRY RUN - no changes made]")
        logger.info("=" * 60)

    except Exception as e:
        db.rollback()
        logger.error(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
