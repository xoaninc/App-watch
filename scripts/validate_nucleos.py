#!/usr/bin/env python3
"""Validate Renfe nucleo implementation.

This script verifies:
- All 12 nucleos are loaded
- Nucleo fields populated in stops and routes
- Geographic boundaries calculated correctly
- Foreign key relationships valid
- Stop and route coverage per nucleo
- Geographic distribution analysis
"""

import sys
import logging
import time
from sqlalchemy import text

from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class NucleoValidator:
    """Validates the Renfe nucleo implementation."""

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

    def check_nucleos_table(self) -> bool:
        """Verify nucleos table exists."""
        try:
            result = self.db.execute(
                text("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_name = 'gtfs_nucleos'
                    )
                """)
            ).scalar()
            self._log_result("Nucleos table exists", result)
            return result
        except Exception as e:
            self._log_result("Nucleos table exists", False, str(e))
            return False

    def check_nucleos_count(self):
        """Check that all 12 nucleos are loaded."""
        try:
            count = self.db.execute(text("SELECT COUNT(*) FROM gtfs_nucleos")).scalar()
            passed = count == 12
            message = f"Found {count} nucleos (expected 12)"
            self._log_result("Nucleos count (should be 12)", passed, message)
            return passed, count
        except Exception as e:
            self._log_result("Nucleos count", False, str(e))
            return False, 0

    def check_nucleos_data(self) -> bool:
        """Verify nucleos have required data."""
        try:
            results = self.db.execute(
                text("""
                    SELECT id, name,
                           CASE WHEN bounding_box_min_lat IS NOT NULL THEN 1 ELSE 0 END as has_bbox,
                           CASE WHEN center_lat IS NOT NULL THEN 1 ELSE 0 END as has_center
                    FROM gtfs_nucleos
                    ORDER BY id
                """)
            ).fetchall()

            all_good = True
            for row in results:
                if not row.has_bbox or not row.has_center:
                    self._log_warning(f"Incomplete data for nucleo {row.id} ({row.name})",
                                    f"has_bbox={row.has_bbox}, has_center={row.has_center}")
                    all_good = False

            self._log_result("Nucleos have complete data", all_good)
            return all_good
        except Exception as e:
            self._log_result("Nucleos data check", False, str(e))
            return False

    def check_stops_coverage(self) -> bool:
        """Check that stops have nucleo coverage."""
        try:
            total = self.db.execute(text("SELECT COUNT(*) FROM gtfs_stops")).scalar()
            with_nucleo = self.db.execute(
                text("SELECT COUNT(*) FROM gtfs_stops WHERE nucleo_id IS NOT NULL")
            ).scalar()

            if total == 0:
                self._log_warning("Stop coverage", "No stops in database")
                return False

            coverage = (with_nucleo / total) * 100
            passed = coverage >= 95  # At least 95% coverage
            message = f"{with_nucleo}/{total} ({coverage:.1f}%)"
            self._log_result("Stop coverage (≥95%)", passed, message)
            return passed
        except Exception as e:
            self._log_result("Stop coverage", False, str(e))
            return False

    def check_routes_coverage(self) -> bool:
        """Check that routes have nucleo coverage."""
        try:
            total = self.db.execute(text("SELECT COUNT(*) FROM gtfs_routes")).scalar()
            with_nucleo = self.db.execute(
                text("SELECT COUNT(*) FROM gtfs_routes WHERE nucleo_id IS NOT NULL")
            ).scalar()

            if total == 0:
                self._log_warning("Route coverage", "No routes in database")
                return False

            coverage = (with_nucleo / total) * 100
            passed = coverage >= 90  # At least 90% coverage for routes
            message = f"{with_nucleo}/{total} ({coverage:.1f}%)"
            self._log_result("Route coverage (≥90%)", passed, message)
            return passed
        except Exception as e:
            self._log_result("Route coverage", False, str(e))
            return False

    def check_foreign_keys(self) -> bool:
        """Verify foreign key relationships are valid."""
        try:
            # Check stops with invalid nucleo_ids
            invalid_stops = self.db.execute(
                text("""
                    SELECT COUNT(*) FROM gtfs_stops s
                    WHERE s.nucleo_id IS NOT NULL
                    AND NOT EXISTS (
                        SELECT 1 FROM gtfs_nucleos n WHERE n.id = s.nucleo_id
                    )
                """)
            ).scalar()

            # Check routes with invalid nucleo_ids
            invalid_routes = self.db.execute(
                text("""
                    SELECT COUNT(*) FROM gtfs_routes r
                    WHERE r.nucleo_id IS NOT NULL
                    AND NOT EXISTS (
                        SELECT 1 FROM gtfs_nucleos n WHERE n.id = r.nucleo_id
                    )
                """)
            ).scalar()

            passed = invalid_stops == 0 and invalid_routes == 0
            message = f"Invalid stop FKs: {invalid_stops}, Invalid route FKs: {invalid_routes}"
            self._log_result("Foreign key relationships", passed, message)
            return passed
        except Exception as e:
            self._log_result("Foreign key relationships", False, str(e))
            return False

    def check_nucleo_distribution(self) -> bool:
        """Log nucleo distribution of stops."""
        try:
            logger.info("\nStop distribution by nucleo:")
            results = self.db.execute(
                text("""
                    SELECT nucleo_name, COUNT(*) as count
                    FROM gtfs_stops
                    WHERE nucleo_id IS NOT NULL
                    GROUP BY nucleo_name
                    ORDER BY count DESC
                """)
            ).fetchall()

            for row in results:
                logger.info(f"  {row.nucleo_name}: {row.count} stops")

            null_count = self.db.execute(
                text("SELECT COUNT(*) FROM gtfs_stops WHERE nucleo_id IS NULL")
            ).scalar()

            if null_count > 0:
                self._log_warning("Stops without nucleo", f"{null_count} stops")

            return True
        except Exception as e:
            logger.error(f"Error checking distribution: {e}")
            return False

    def check_route_distribution(self) -> bool:
        """Log nucleo distribution of routes."""
        try:
            logger.info("\nRoute distribution by nucleo:")
            results = self.db.execute(
                text("""
                    SELECT nucleo_name, COUNT(*) as count
                    FROM gtfs_routes
                    WHERE nucleo_id IS NOT NULL
                    GROUP BY nucleo_name
                    ORDER BY count DESC
                """)
            ).fetchall()

            for row in results:
                logger.info(f"  {row.nucleo_name}: {row.count} routes")

            null_count = self.db.execute(
                text("SELECT COUNT(*) FROM gtfs_routes WHERE nucleo_id IS NULL")
            ).scalar()

            if null_count > 0:
                self._log_warning("Routes without nucleo", f"{null_count} routes")

            return True
        except Exception as e:
            logger.error(f"Error checking route distribution: {e}")
            return False

    def check_query_performance(self) -> bool:
        """Test that queries complete within acceptable time."""
        try:
            # Test query performance for nucleo lookups
            start = time.time()
            self.db.execute(
                text("SELECT COUNT(*) FROM gtfs_nucleos")
            ).scalar()
            elapsed = (time.time() - start) * 1000  # Convert to ms

            passed = elapsed < 100  # Should be under 100ms
            message = f"Query time: {elapsed:.2f}ms"
            self._log_result("Query performance", passed, message)
            return passed
        except Exception as e:
            self._log_result("Query performance", False, str(e))
            return False

    def run_all_checks(self) -> bool:
        """Run all validation checks."""
        logger.info("\n" + "="*60)
        logger.info("Renfe Nucleo Implementation Validation")
        logger.info("="*60 + "\n")

        # Database checks
        logger.info("1. Database Structure")
        logger.info("-" * 40)
        self.check_nucleos_table()
        self.check_nucleos_count()
        self.check_nucleos_data()

        # Coverage checks
        logger.info("\n2. Data Coverage")
        logger.info("-" * 40)
        self.check_stops_coverage()
        self.check_routes_coverage()
        self.check_foreign_keys()

        # Distribution checks
        logger.info("\n3. Distribution Analysis")
        logger.info("-" * 40)
        self.check_nucleo_distribution()
        self.check_route_distribution()

        # Performance checks
        logger.info("\n4. Performance Tests")
        logger.info("-" * 40)
        self.check_query_performance()

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
        validator = NucleoValidator(db)
        success = validator.run_all_checks()
        sys.exit(0 if success else 1)

    except Exception as e:
        logger.error(f"Validation error: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
