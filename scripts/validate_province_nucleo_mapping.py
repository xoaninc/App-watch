#!/usr/bin/env python3
"""Validate province to nucleo mapping.

This script verifies that the province-nucleo mapping is correct and complete.
"""

import sys
import logging
from sqlalchemy import text

from core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ProvinceNucleoValidator:
    """Validates the province-nucleo mapping."""

    def __init__(self, db):
        """Initialize validator."""
        self.db = db
        self.results = {
            'total_checks': 0,
            'passed': 0,
            'failed': 0,
            'warnings': 0,
        }

    def _log_result(self, check_name: str, passed: bool, message: str = ""):
        """Log a check result."""
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

    def check_mapping_columns(self) -> bool:
        """Verify mapping columns exist."""
        try:
            result = self.db.execute(
                text("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'spanish_provinces'
                    AND column_name IN ('nucleo_id', 'nucleo_name')
                """)
            ).fetchall()

            passed = len(result) == 2
            message = f"Found {len(result)}/2 mapping columns"
            self._log_result("Mapping columns exist", passed, message)
            return passed
        except Exception as e:
            self._log_result("Mapping columns exist", False, str(e))
            return False

    def check_mapping_count(self) -> bool:
        """Check that provinces are mapped."""
        try:
            mapped = self.db.execute(
                text("SELECT COUNT(*) FROM spanish_provinces WHERE nucleo_id IS NOT NULL")
            ).scalar()

            total = self.db.execute(
                text("SELECT COUNT(*) FROM spanish_provinces")
            ).scalar()

            message = f"{mapped}/{total} provinces mapped"
            self._log_result("Provinces mapped", mapped > 0, message)
            return mapped > 0
        except Exception as e:
            self._log_result("Provinces mapped", False, str(e))
            return False

    def check_expected_mappings(self) -> bool:
        """Verify expected mappings are correct."""
        expected = {
            'Madrid': ('Madrid', 10),
            'Barcelona': ('Rodalies de Catalunya', 50),
            'Murcia': ('Murcia/Alicante', 41),
            'Alicante': ('Murcia/Alicante', 41),
            'Vizcaya': ('Bilbao', 60),
        }

        all_correct = True
        for province, (expected_nucleo, expected_id) in expected.items():
            try:
                result = self.db.execute(
                    text("""
                        SELECT nucleo_name, nucleo_id
                        FROM spanish_provinces
                        WHERE name = :province
                    """),
                    {'province': province}
                ).fetchone()

                if result:
                    nucleo_name, nucleo_id = result
                    correct = (nucleo_name == expected_nucleo and nucleo_id == expected_id)
                    self._log_result(
                        f"Mapping for {province}",
                        correct,
                        f"{nucleo_name} (id: {nucleo_id})"
                    )
                    if not correct:
                        all_correct = False
                else:
                    self._log_result(f"Mapping for {province}", False, "Province not found")
                    all_correct = False

            except Exception as e:
                self._log_result(f"Mapping for {province}", False, str(e))
                all_correct = False

        return all_correct

    def check_foreign_keys(self) -> bool:
        """Verify foreign key relationships."""
        try:
            invalid = self.db.execute(
                text("""
                    SELECT COUNT(*) FROM spanish_provinces sp
                    WHERE sp.nucleo_id IS NOT NULL
                    AND NOT EXISTS (
                        SELECT 1 FROM gtfs_nucleos n WHERE n.id = sp.nucleo_id
                    )
                """)
            ).scalar()

            passed = invalid == 0
            message = f"Invalid foreign keys: {invalid}"
            self._log_result("Foreign key integrity", passed, message)
            return passed
        except Exception as e:
            self._log_result("Foreign key integrity", False, str(e))
            return False

    def check_special_cases(self) -> bool:
        """Verify special cases (Murcia/Alicante, Rodalies)."""
        try:
            # Check Murcia/Alicante covers both provinces
            murcia_alicante = self.db.execute(
                text("""
                    SELECT COUNT(*) FROM spanish_provinces
                    WHERE nucleo_id = 41
                    AND name IN ('Murcia', 'Alicante')
                """)
            ).scalar()

            murcia_alicante_ok = murcia_alicante == 2

            # Check Rodalies de Catalunya covers 4 provinces
            rodalies = self.db.execute(
                text("""
                    SELECT COUNT(*) FROM spanish_provinces
                    WHERE nucleo_id = 50
                    AND name IN ('Barcelona', 'Tarragona', 'Lleida', 'Girona')
                """)
            ).scalar()

            rodalies_ok = rodalies == 4

            self._log_result(
                "Murcia/Alicante coverage",
                murcia_alicante_ok,
                f"Covers {murcia_alicante}/2 provinces"
            )
            self._log_result(
                "Rodalies de Catalunya coverage",
                rodalies_ok,
                f"Covers {rodalies}/4 provinces"
            )

            return murcia_alicante_ok and rodalies_ok
        except Exception as e:
            self._log_result("Special cases", False, str(e))
            return False

    def show_mapping_details(self) -> None:
        """Show detailed mapping information."""
        logger.info("\nProvince to Nucleo Mapping Details:")
        logger.info("-" * 60)

        results = self.db.execute(
            text("""
                SELECT nucleo_name, nucleo_id, STRING_AGG(name, ', ') as provinces, COUNT(*) as count
                FROM spanish_provinces
                WHERE nucleo_id IS NOT NULL
                GROUP BY nucleo_id, nucleo_name
                ORDER BY nucleo_id
            """)
        ).fetchall()

        for row in results:
            logger.info(f"\nNúcleo {row.nucleo_id}: {row.nucleo_name}")
            logger.info(f"  Provinces ({row.count}): {row.provinces}")

        # Show unmapped
        unmapped_count = self.db.execute(
            text("SELECT COUNT(*) FROM spanish_provinces WHERE nucleo_id IS NULL")
        ).scalar()

        if unmapped_count > 0:
            logger.info(f"\nUnmapped provinces ({unmapped_count}):")
            unmapped = self.db.execute(
                text("SELECT name FROM spanish_provinces WHERE nucleo_id IS NULL ORDER BY name")
            ).fetchall()
            for row in unmapped:
                logger.info(f"  - {row.name}")

    def run_all_checks(self) -> bool:
        """Run all validation checks."""
        logger.info("\n" + "="*60)
        logger.info("Province-Nucleo Mapping Validation")
        logger.info("="*60 + "\n")

        logger.info("1. Schema Verification")
        logger.info("-" * 40)
        self.check_mapping_columns()
        self.check_mapping_count()

        logger.info("\n2. Mapping Verification")
        logger.info("-" * 40)
        self.check_expected_mappings()
        self.check_special_cases()

        logger.info("\n3. Integrity Checks")
        logger.info("-" * 40)
        self.check_foreign_keys()

        logger.info("\n4. Mapping Details")
        logger.info("-" * 40)
        self.show_mapping_details()

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
            logger.info("\n✓ Province-nucleo mapping is valid!")
        else:
            logger.error(f"\n✗ {self.results['failed']} validation checks failed!")

        return success


def main():
    """Main entry point."""
    db = SessionLocal()
    try:
        validator = ProvinceNucleoValidator(db)
        success = validator.run_all_checks()
        sys.exit(0 if success else 1)

    except Exception as e:
        logger.error(f"Validation error: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
