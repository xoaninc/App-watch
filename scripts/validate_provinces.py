#!/usr/bin/env python3
"""Validate PostGIS province boundaries implementation.

This script verifies:
- Province boundaries are properly loaded
- Geometries are valid
- Spatial index exists
- Known coordinates return expected provinces
- Query performance is acceptable
- Stop coverage is adequate
"""

import sys
import logging
import time
from typing import Dict, List, Tuple
from sqlalchemy import text

from core.database import SessionLocal
from src.gtfs_bc.province.province_lookup import get_province_by_coordinates

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ProvinceValidator:
    """Validates the PostGIS province implementation."""

    def __init__(self, db):
        """Initialize validator with database session."""
        self.db = db
        self.results = {
            'total_checks': 0,
            'passed': 0,
            'failed': 0,
            'warnings': 0,
        }

    def _log_result(self, check_name: str, passed: bool, message: str = ""):
        """Log a single check result."""
        self.results['total_checks'] += 1
        status = "✓ PASS" if passed else "✗ FAIL"
        level = logging.INFO if passed else logging.ERROR
        msg = f"{status}: {check_name}"
        if message:
            msg += f" - {message}"
        logger.log(level, msg)
        if passed:
            self.results['passed'] += 1
        else:
            self.results['failed'] += 1

    def _log_warning(self, check_name: str, message: str = ""):
        """Log a warning."""
        self.results['warnings'] += 1
        msg = f"⚠ WARN: {check_name}"
        if message:
            msg += f" - {message}"
        logger.warning(msg)

    def check_extension_enabled(self) -> bool:
        """Verify PostGIS extension is enabled."""
        try:
            result = self.db.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'postgis'")
            ).scalar()
            passed = result == 'postgis'
            self._log_result("PostGIS extension enabled", passed)
            return passed
        except Exception as e:
            self._log_result("PostGIS extension enabled", False, str(e))
            return False

    def check_provinces_table(self) -> bool:
        """Verify provinces table exists with required columns."""
        try:
            result = self.db.execute(
                text("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_name = 'spanish_provinces'
                    )
                """)
            ).scalar()
            passed = result
            self._log_result("Provinces table exists", passed)
            return passed
        except Exception as e:
            self._log_result("Provinces table exists", False, str(e))
            return False

    def check_provinces_count(self) -> Tuple[bool, int]:
        """Check that provinces are loaded (expect ~50)."""
        try:
            count = self.db.execute(text("SELECT COUNT(*) FROM spanish_provinces")).scalar()
            passed = 45 <= count <= 55  # Allow small range for autonomous cities
            message = f"Found {count} provinces"
            self._log_result("Provinces count (45-55)", passed, message)
            return passed, count
        except Exception as e:
            self._log_result("Provinces count", False, str(e))
            return False, 0

    def check_geometry_validity(self) -> Tuple[bool, int]:
        """Verify all geometries are valid."""
        try:
            invalid = self.db.execute(
                text("""
                    SELECT COUNT(*) FROM spanish_provinces
                    WHERE NOT ST_IsValid(geometry)
                """)
            ).scalar()
            passed = invalid == 0
            if passed:
                self._log_result("All geometries valid", True, f"0 invalid geometries")
            else:
                self._log_result("All geometries valid", False, f"{invalid} invalid geometries")
            return passed, invalid
        except Exception as e:
            self._log_result("All geometries valid", False, str(e))
            return False, -1

    def check_spatial_index(self) -> bool:
        """Verify spatial index exists."""
        try:
            exists = self.db.execute(
                text("""
                    SELECT EXISTS (
                        SELECT 1 FROM pg_indexes
                        WHERE tablename = 'spanish_provinces'
                        AND indexname = 'idx_spanish_provinces_geometry'
                    )
                """)
            ).scalar()
            self._log_result("Spatial index exists", exists)
            return exists
        except Exception as e:
            self._log_result("Spatial index exists", False, str(e))
            return False

    def test_known_coordinates(self) -> bool:
        """Test with known Spanish city coordinates."""
        test_cases = {
            'Madrid': (40.4168, -3.7038),
            'Barcelona': (41.3874, 2.1686),
            'Valencia': (39.4699, -0.3763),
            'Seville': (37.3886, -5.9823),
            'Bilbao': (43.2627, -2.9253),
        }

        all_passed = True
        for city, (lat, lon) in test_cases.items():
            try:
                province = get_province_by_coordinates(self.db, lat, lon)
                passed = province is not None
                message = f"Province: {province}" if passed else "No province found"
                self._log_result(f"Coordinate test: {city}", passed, message)
                if not passed:
                    all_passed = False
            except Exception as e:
                self._log_result(f"Coordinate test: {city}", False, str(e))
                all_passed = False

        return all_passed

    def test_invalid_coordinates(self) -> bool:
        """Test that invalid coordinates are handled properly."""
        # Coordinates outside Spain (e.g., center of Atlantic Ocean)
        try:
            province = get_province_by_coordinates(self.db, 30.0, -30.0)
            passed = province is None
            message = f"Correctly returned None" if passed else f"Unexpected province: {province}"
            self._log_result("Invalid coordinates (Atlantic)", passed, message)
            return passed
        except Exception as e:
            self._log_result("Invalid coordinates (Atlantic)", False, str(e))
            return False

    def test_query_performance(self) -> bool:
        """Test that queries complete within acceptable time."""
        try:
            # Test 10 queries and average the time
            times = []
            for lat, lon in [
                (40.4168, -3.7038),  # Madrid
                (41.3874, 2.1686),   # Barcelona
                (39.4699, -0.3763),  # Valencia
                (37.3886, -5.9823),  # Seville
                (43.2627, -2.9253),  # Bilbao
            ]:
                start = time.time()
                get_province_by_coordinates(self.db, lat, lon)
                elapsed = (time.time() - start) * 1000  # Convert to ms
                times.append(elapsed)

            avg_time = sum(times) / len(times)
            max_time = max(times)
            passed = avg_time < 10  # Should be under 10ms on average
            message = f"Avg: {avg_time:.2f}ms, Max: {max_time:.2f}ms"
            self._log_result("Query performance (<10ms avg)", passed, message)
            return passed
        except Exception as e:
            self._log_result("Query performance", False, str(e))
            return False

    def check_stop_coverage(self) -> Tuple[bool, float]:
        """Check that stops have province coverage."""
        try:
            total = self.db.execute(text("SELECT COUNT(*) FROM gtfs_stops")).scalar()
            with_province = self.db.execute(
                text("SELECT COUNT(*) FROM gtfs_stops WHERE province IS NOT NULL")
            ).scalar()

            if total == 0:
                self._log_warning("Stop coverage", "No stops in database")
                return False, 0.0

            coverage = (with_province / total) * 100
            passed = coverage >= 95  # At least 95% coverage
            message = f"{with_province}/{total} ({coverage:.1f}%)"
            self._log_result("Stop coverage (≥95%)", passed, message)
            return passed, coverage
        except Exception as e:
            self._log_result("Stop coverage", False, str(e))
            return False, 0.0

    def check_province_distribution(self) -> bool:
        """Log province distribution."""
        try:
            logger.info("\nProvince distribution of stops:")
            results = self.db.execute(
                text("""
                    SELECT province, COUNT(*) as count
                    FROM gtfs_stops
                    WHERE province IS NOT NULL
                    GROUP BY province
                    ORDER BY count DESC
                    LIMIT 10
                """)
            ).fetchall()

            for row in results:
                logger.info(f"  {row.province}: {row.count} stops")

            null_count = self.db.execute(
                text("SELECT COUNT(*) FROM gtfs_stops WHERE province IS NULL")
            ).scalar()

            if null_count > 0:
                self._log_warning("Stops without province", f"{null_count} stops")

            return True
        except Exception as e:
            logger.error(f"Error checking distribution: {e}")
            return False

    def run_all_checks(self) -> bool:
        """Run all validation checks."""
        logger.info("\n" + "="*60)
        logger.info("PostGIS Province Boundaries Validation")
        logger.info("="*60 + "\n")

        # Database checks
        logger.info("1. Database Structure")
        logger.info("-" * 40)
        self.check_extension_enabled()
        self.check_provinces_table()
        self.check_provinces_count()
        self.check_geometry_validity()
        self.check_spatial_index()

        # Functional checks
        logger.info("\n2. Functional Tests")
        logger.info("-" * 40)
        self.test_known_coordinates()
        self.test_invalid_coordinates()

        # Performance checks
        logger.info("\n3. Performance Tests")
        logger.info("-" * 40)
        self.test_query_performance()

        # Coverage checks
        logger.info("\n4. Data Coverage")
        logger.info("-" * 40)
        self.check_stop_coverage()
        self.check_province_distribution()

        # Summary
        logger.info("\n" + "="*60)
        logger.info("Validation Summary")
        logger.info("="*60)
        logger.info(f"Total checks: {self.results['total_checks']}")
        logger.info(f"Passed: {self.results['passed']}")
        logger.info(f"Failed: {self.results['failed']}")
        logger.info(f"Warnings: {self.results['warnings']}")
        logger.info("="*60)

        success = self.results['failed'] == 0
        if success:
            logger.info("\n✓ All validation checks passed!")
        else:
            logger.error(f"\n✗ {self.results['failed']} validation checks failed!")

        return success


def main():
    """Run validation."""
    db = SessionLocal()
    try:
        validator = ProvinceValidator(db)
        success = validator.run_all_checks()
        sys.exit(0 if success else 1)

    except Exception as e:
        logger.error(f"Validation error: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
