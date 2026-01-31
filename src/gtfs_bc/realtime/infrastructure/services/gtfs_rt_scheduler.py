"""GTFS-RT automatic fetcher scheduler.

This module provides a background scheduler that automatically fetches
GTFS-RT data at regular intervals.
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from sqlalchemy.orm import Session

from core.database import SessionLocal
from src.gtfs_bc.realtime.infrastructure.services.gtfs_rt_fetcher import GTFSRealtimeFetcher
from src.gtfs_bc.realtime.infrastructure.services.multi_operator_fetcher import MultiOperatorFetcher

logger = logging.getLogger(__name__)


class GTFSRTScheduler:
    """Background scheduler for GTFS-RT data fetching."""

    # Fetch interval in seconds (30 seconds for real-time accuracy)
    FETCH_INTERVAL = 30
    # Maximum time allowed for a single fetch (60 seconds since operators have 45s individual timeouts)
    FETCH_TIMEOUT = 60

    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_fetch: Optional[datetime] = None
        self._fetch_count = 0
        self._error_count = 0

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def status(self) -> dict:
        """Get scheduler status."""
        return {
            "running": self._running,
            "last_fetch": self._last_fetch.isoformat() if self._last_fetch else None,
            "fetch_count": self._fetch_count,
            "error_count": self._error_count,
            "interval_seconds": self.FETCH_INTERVAL,
        }

    async def start(self):
        """Start the background fetch task."""
        if self._running:
            logger.warning("GTFS-RT scheduler already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._fetch_loop())
        logger.info(f"GTFS-RT scheduler started (interval: {self.FETCH_INTERVAL}s)")

    async def stop(self):
        """Stop the background fetch task."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("GTFS-RT scheduler stopped")

    async def _fetch_loop(self):
        """Main fetch loop that runs in background."""
        # Initial delay to let the app fully start
        await asyncio.sleep(5)

        while self._running:
            try:
                await self._do_fetch()
            except asyncio.CancelledError:
                # Task was cancelled (shutdown) - re-raise to exit cleanly
                logger.info("GTFS-RT scheduler task cancelled")
                raise
            except asyncio.TimeoutError:
                self._error_count += 1
                logger.error(f"GTFS-RT fetch timeout after {self.FETCH_TIMEOUT}s - will retry in {self.FETCH_INTERVAL}s")
            except Exception as e:
                self._error_count += 1
                logger.error(f"GTFS-RT fetch error: {e} - will retry in {self.FETCH_INTERVAL}s")
            except BaseException as e:
                # Catch absolutely everything else (except CancelledError which we re-raised)
                self._error_count += 1
                logger.error(f"GTFS-RT unexpected error: {type(e).__name__}: {e} - will retry in {self.FETCH_INTERVAL}s")

            # Wait for next interval
            await asyncio.sleep(self.FETCH_INTERVAL)

    async def _do_fetch(self):
        """Perform a single GTFS-RT fetch with timeout."""
        # Run the synchronous fetch in a thread pool with timeout
        loop = asyncio.get_event_loop()

        # Wrap the fetch in a timeout
        result = await asyncio.wait_for(
            loop.run_in_executor(None, self._fetch_sync),
            timeout=self.FETCH_TIMEOUT
        )

        self._last_fetch = datetime.utcnow()
        self._fetch_count += 1

        if result:
            logger.info(
                f"GTFS-RT auto-fetch #{self._fetch_count}: "
                f"{result.get('vehicle_positions', 0)} positions, "
                f"{result.get('trip_updates', 0)} updates, "
                f"{result.get('alerts', 0)} alerts"
            )

    def _fetch_sync(self) -> dict:
        """Synchronous fetch operation for all operators.

        Each fetcher runs independently - if one fails, the others still run.
        This ensures that a single operator failure doesn't stop all data collection.
        """
        db = SessionLocal()
        try:
            # Initialize results
            renfe_result = {'vehicle_positions': 0, 'trip_updates': 0, 'alerts': 0}
            multi_results = []

            # Fetch Renfe GTFS-RT (wrapped in try/except to not block others)
            try:
                renfe_fetcher = GTFSRealtimeFetcher(db)
                renfe_result = renfe_fetcher.fetch_all_sync()
            except Exception as e:
                logger.error(f"Renfe GTFS-RT fetch failed: {e}")
                renfe_result['error'] = str(e)

            # Fetch other operators (TMB, FGC, Metro Bilbao, Euskotren)
            # Each operator is fetched independently within fetch_all_operators_sync
            try:
                multi_fetcher = MultiOperatorFetcher(db)
                multi_results = multi_fetcher.fetch_all_operators_sync()
            except Exception as e:
                logger.error(f"Multi-operator GTFS-RT fetch failed: {e}")
                multi_results = [{'error': str(e)}]

            # Aggregate results
            total_positions = renfe_result.get('vehicle_positions', 0)
            total_updates = renfe_result.get('trip_updates', 0)
            total_alerts = renfe_result.get('alerts', 0)

            for op_result in multi_results:
                total_positions += op_result.get('vehicle_positions', 0)
                total_updates += op_result.get('trip_updates', 0)
                total_alerts += op_result.get('alerts', 0)

            return {
                'vehicle_positions': total_positions,
                'trip_updates': total_updates,
                'alerts': total_alerts,
                'renfe': renfe_result,
                'operators': multi_results,
            }
        finally:
            db.close()


# Global scheduler instance
gtfs_rt_scheduler = GTFSRTScheduler()


def _load_gtfs_store():
    """Load GTFS data into memory store (synchronous)."""
    from src.gtfs_bc.routing.gtfs_store import GTFSStore

    db = SessionLocal()
    try:
        store = GTFSStore.get_instance()
        store.load_data(db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan_with_scheduler(app):
    """FastAPI lifespan context manager that starts/stops the scheduler.

    Also loads GTFS data into memory for fast RAPTOR routing.
    """
    # Startup: Load GTFS data into memory first
    logger.info("Loading GTFS data into memory for RAPTOR...")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _load_gtfs_store)
    logger.info("GTFS data loaded successfully")

    # Start GTFS-RT scheduler
    await gtfs_rt_scheduler.start()

    yield

    # Shutdown
    await gtfs_rt_scheduler.stop()
