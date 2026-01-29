import logging
from datetime import date, timedelta

from celery import shared_task
from sqlalchemy import text

from core.database import SessionLocal
from src.gtfs_bc.realtime.infrastructure.services.gtfs_rt_fetcher import GTFSRealtimeFetcher

logger = logging.getLogger(__name__)

# Platform history retention period in days
PLATFORM_HISTORY_RETENTION_DAYS = 30


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def fetch_gtfs_realtime(self):
    """Fetch GTFS-RT data from Renfe API.

    This task runs periodically to update vehicle positions and trip delays.
    """
    db = SessionLocal()
    try:
        fetcher = GTFSRealtimeFetcher(db)
        result = fetcher.fetch_all_sync()
        logger.info(
            f"GTFS-RT fetch completed: {result['vehicle_positions']} vehicles, "
            f"{result['trip_updates']} trip updates"
        )
        return result
    except Exception as e:
        logger.error(f"GTFS-RT fetch failed: {e}")
        raise self.retry(exc=e)
    finally:
        db.close()


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def fetch_vehicle_positions(self):
    """Fetch only vehicle positions from Renfe API."""
    db = SessionLocal()
    try:
        fetcher = GTFSRealtimeFetcher(db)
        count = fetcher.fetch_and_store_vehicle_positions_sync()
        logger.info(f"Fetched {count} vehicle positions")
        return {"vehicle_positions": count}
    except Exception as e:
        logger.error(f"Vehicle positions fetch failed: {e}")
        raise self.retry(exc=e)
    finally:
        db.close()


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def fetch_trip_updates(self):
    """Fetch only trip updates from Renfe API."""
    db = SessionLocal()
    try:
        fetcher = GTFSRealtimeFetcher(db)
        count = fetcher.fetch_and_store_trip_updates_sync()
        logger.info(f"Fetched {count} trip updates")
        return {"trip_updates": count}
    except Exception as e:
        logger.error(f"Trip updates fetch failed: {e}")
        raise self.retry(exc=e)
    finally:
        db.close()


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def cleanup_platform_history(self):
    """Delete platform history records older than 30 days.

    This task runs daily to keep the platform history table from growing indefinitely.
    Records older than PLATFORM_HISTORY_RETENTION_DAYS are deleted.
    """
    db = SessionLocal()
    try:
        cutoff_date = date.today() - timedelta(days=PLATFORM_HISTORY_RETENTION_DAYS)
        result = db.execute(
            text("DELETE FROM gtfs_rt_platform_history WHERE observation_date < :cutoff"),
            {"cutoff": cutoff_date}
        )
        db.commit()
        deleted_count = result.rowcount
        logger.info(f"Platform history cleanup: deleted {deleted_count} records older than {cutoff_date}")
        return {"deleted_records": deleted_count, "cutoff_date": str(cutoff_date)}
    except Exception as e:
        logger.error(f"Platform history cleanup failed: {e}")
        db.rollback()
        raise self.retry(exc=e)
    finally:
        db.close()
