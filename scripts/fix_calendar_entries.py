#!/usr/bin/env python3
"""Fix missing calendar entries for FGC, TMB, Metro Bilbao, Metrovalencia, and TRAM.

These networks have trips with service_ids that don't exist in gtfs_calendar,
which prevents RAPTOR from finding active services.

This script creates calendar entries based on:
- FGC, TMB, Metrovalencia, TRAM: All days active (L-D) since we can't infer day type
- Metro Bilbao: Day type inferred from service_id pattern (invl=L-J, invv=V, invs=S, invd=D)

Usage:
    python scripts/fix_calendar_entries.py --analyze  # Show what would be created
    python scripts/fix_calendar_entries.py            # Create calendar entries
"""

import os
import sys
import argparse
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Calendar date range
START_DATE = '2025-01-01'
END_DATE = '2026-12-31'


def get_missing_service_ids(db, route_pattern: str) -> list:
    """Get service_ids that exist in trips but not in calendar."""
    result = db.execute(text("""
        SELECT DISTINCT t.service_id
        FROM gtfs_trips t
        WHERE t.route_id LIKE :pattern
        AND NOT EXISTS (SELECT 1 FROM gtfs_calendar c WHERE c.service_id = t.service_id)
        ORDER BY t.service_id
    """), {'pattern': route_pattern}).fetchall()
    return [r[0] for r in result]


def infer_metro_bilbao_day_type(service_id: str) -> dict:
    """Infer day type from Metro Bilbao service_id pattern.

    Returns dict with day flags: {monday, tuesday, ..., sunday}
    """
    lower = service_id.lower()

    # Laborable (L-J): invl, verl
    if 'invl' in lower or 'verl' in lower:
        return {
            'monday': True, 'tuesday': True, 'wednesday': True, 'thursday': True,
            'friday': False, 'saturday': False, 'sunday': False
        }
    # Viernes: invv, verv, vlargo
    elif 'invv' in lower or 'verv' in lower or 'vlargo' in lower:
        return {
            'monday': False, 'tuesday': False, 'wednesday': False, 'thursday': False,
            'friday': True, 'saturday': False, 'sunday': False
        }
    # Sábado: invs, vers, postvlargo
    elif 'invs' in lower or 'vers' in lower or 'postvlargo' in lower:
        return {
            'monday': False, 'tuesday': False, 'wednesday': False, 'thursday': False,
            'friday': False, 'saturday': True, 'sunday': False
        }
    # Domingo: invd, verd
    elif 'invd' in lower or 'verd' in lower:
        return {
            'monday': False, 'tuesday': False, 'wednesday': False, 'thursday': False,
            'friday': False, 'saturday': False, 'sunday': True
        }
    # Default: all days (for special services like nocturno, navidad, etc.)
    else:
        return {
            'monday': True, 'tuesday': True, 'wednesday': True, 'thursday': True,
            'friday': True, 'saturday': True, 'sunday': True
        }


def create_calendar_entry(db, service_id: str, days: dict, dry_run: bool = False):
    """Create a calendar entry for the given service_id."""
    if dry_run:
        return

    db.execute(text("""
        INSERT INTO gtfs_calendar
        (service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date)
        VALUES (:service_id, :monday, :tuesday, :wednesday, :thursday, :friday, :saturday, :sunday, :start_date, :end_date)
        ON CONFLICT (service_id) DO NOTHING
    """), {
        'service_id': service_id,
        'monday': days['monday'],
        'tuesday': days['tuesday'],
        'wednesday': days['wednesday'],
        'thursday': days['thursday'],
        'friday': days['friday'],
        'saturday': days['saturday'],
        'sunday': days['sunday'],
        'start_date': START_DATE,
        'end_date': END_DATE,
    })


def fix_network(db, name: str, route_pattern: str, infer_days_func=None, dry_run: bool = False):
    """Fix calendar entries for a network.

    Args:
        name: Network name for logging
        route_pattern: SQL LIKE pattern for route_id
        infer_days_func: Optional function to infer day type from service_id
                        If None, all days are set to True
        dry_run: If True, only show what would be done
    """
    missing = get_missing_service_ids(db, route_pattern)

    if not missing:
        logger.info(f"{name}: No missing calendar entries")
        return 0

    logger.info(f"{name}: {len(missing)} service_ids without calendar entry")

    # Default: all days active
    all_days = {
        'monday': True, 'tuesday': True, 'wednesday': True, 'thursday': True,
        'friday': True, 'saturday': True, 'sunday': True
    }

    created = 0
    for service_id in missing:
        if infer_days_func:
            days = infer_days_func(service_id)
        else:
            days = all_days

        day_str = ''.join([
            'L' if days['monday'] else '',
            'M' if days['tuesday'] else '',
            'X' if days['wednesday'] else '',
            'J' if days['thursday'] else '',
            'V' if days['friday'] else '',
            'S' if days['saturday'] else '',
            'D' if days['sunday'] else '',
        ])

        if dry_run:
            logger.info(f"  Would create: {service_id} -> {day_str}")
        else:
            create_calendar_entry(db, service_id, days)

        created += 1

    if not dry_run:
        db.commit()
        logger.info(f"  Created {created} calendar entries")

    return created


def analyze(db):
    """Analyze missing calendar entries without making changes."""
    print("=" * 70)
    print("ANÁLISIS DE CALENDARIOS FALTANTES")
    print("=" * 70)

    networks = [
        ('FGC', 'FGC%'),
        ('TMB Metro', 'TMB_METRO%'),
        ('Metro Bilbao', 'METRO_BIL%'),
        ('Metrovalencia', 'METRO_VAL%'),
        ('TRAM Barcelona', 'TRAM_BARCELONA%'),
    ]

    total_missing = 0
    for name, pattern in networks:
        missing = get_missing_service_ids(db, pattern)

        # Count affected trips
        result = db.execute(text("""
            SELECT COUNT(*) FROM gtfs_trips t
            WHERE t.route_id LIKE :pattern
            AND NOT EXISTS (SELECT 1 FROM gtfs_calendar c WHERE c.service_id = t.service_id)
        """), {'pattern': pattern}).fetchone()
        trips = result[0]

        print(f"\n{name}:")
        print(f"  Service IDs sin calendar: {len(missing)}")
        print(f"  Trips afectados: {trips:,}")

        if missing:
            print(f"  Ejemplos:")
            for sid in missing[:3]:
                if 'METRO_BIL' in pattern:
                    days = infer_metro_bilbao_day_type(sid)
                    day_str = ''.join([
                        'L' if days['monday'] else '',
                        'M' if days['tuesday'] else '',
                        'X' if days['wednesday'] else '',
                        'J' if days['thursday'] else '',
                        'V' if days['friday'] else '',
                        'S' if days['saturday'] else '',
                        'D' if days['sunday'] else '',
                    ])
                    print(f"    {sid} -> {day_str}")
                else:
                    print(f"    {sid} -> LMXJVSD")

        total_missing += len(missing)

    print("\n" + "=" * 70)
    print(f"TOTAL: {total_missing} service_ids sin calendar entry")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description='Fix missing calendar entries for transit networks'
    )
    parser.add_argument(
        '--analyze',
        action='store_true',
        help='Analyze missing entries without making changes'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    parser.add_argument(
        '--network',
        choices=['fgc', 'tmb', 'bilbao', 'valencia', 'tram', 'all'],
        default='all',
        help='Which network to fix (default: all)'
    )

    args = parser.parse_args()

    db = SessionLocal()

    try:
        if args.analyze:
            analyze(db)
            return

        if args.dry_run:
            logger.info("[DRY RUN MODE - no changes will be made]")

        networks = {
            'fgc': ('FGC', 'FGC%', None),
            'tmb': ('TMB Metro', 'TMB_METRO%', None),
            'bilbao': ('Metro Bilbao', 'METRO_BIL%', infer_metro_bilbao_day_type),
            'valencia': ('Metrovalencia', 'METRO_VAL%', None),
            'tram': ('TRAM Barcelona', 'TRAM_BARCELONA%', None),
        }

        if args.network == 'all':
            to_fix = networks.keys()
        else:
            to_fix = [args.network]

        total_created = 0
        for key in to_fix:
            name, pattern, infer_func = networks[key]
            created = fix_network(db, name, pattern, infer_func, args.dry_run)
            total_created += created

        if not args.dry_run:
            logger.info(f"\nTotal calendar entries created: {total_created}")

            # Verify
            logger.info("\nVerificación:")
            for key in to_fix:
                name, pattern, _ = networks[key]
                missing = get_missing_service_ids(db, pattern)
                logger.info(f"  {name}: {len(missing)} service_ids aún sin calendar")

    finally:
        db.close()


if __name__ == '__main__':
    main()
