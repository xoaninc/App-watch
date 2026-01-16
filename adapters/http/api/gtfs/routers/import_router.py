from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional

from core.database import get_db
# GTFSImporter has been deprecated in favor of RenfeGeoJSONImporter
# Only using official Renfe GeoJSON sources now
from src.gtfs_bc.feed.infrastructure.models import FeedImportModel
from adapters.http.api.gtfs.schemas.import_schemas import (
    ImportRequest,
    ImportResponse,
    ImportStatusResponse,
)

router = APIRouter(prefix="/gtfs", tags=["GTFS"])

# GTFS ZIP import endpoints have been deprecated
# Use scripts/import_renfe_nucleos.py instead to import from official Renfe GeoJSON sources
# @router.post("/import", response_model=ImportResponse)
# def import_gtfs_feed(...):


@router.get("/import/{import_id}", response_model=ImportStatusResponse)
def get_import_status(import_id: str, db: Session = Depends(get_db)):
    """Get status of a GTFS import."""
    feed_import = db.query(FeedImportModel).filter(FeedImportModel.id == import_id).first()
    if not feed_import:
        raise HTTPException(status_code=404, detail="Import not found")

    return ImportStatusResponse(
        id=feed_import.id,
        source_url=feed_import.source_url,
        status=feed_import.status,
        started_at=feed_import.started_at,
        completed_at=feed_import.completed_at,
        error_message=feed_import.error_message,
        agencies_count=feed_import.agencies_count,
        routes_count=feed_import.routes_count,
        stops_count=feed_import.stops_count,
        trips_count=feed_import.trips_count,
        stop_times_count=feed_import.stop_times_count,
    )


@router.get("/imports", response_model=list[ImportStatusResponse])
def list_imports(db: Session = Depends(get_db), limit: int = 10):
    """List recent GTFS imports."""
    imports = (
        db.query(FeedImportModel)
        .order_by(FeedImportModel.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        ImportStatusResponse(
            id=imp.id,
            source_url=imp.source_url,
            status=imp.status,
            started_at=imp.started_at,
            completed_at=imp.completed_at,
            error_message=imp.error_message,
            agencies_count=imp.agencies_count,
            routes_count=imp.routes_count,
            stops_count=imp.stops_count,
            trips_count=imp.trips_count,
            stop_times_count=imp.stop_times_count,
        )
        for imp in imports
    ]
