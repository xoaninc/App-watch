from pathlib import Path

import os
from fastapi import FastAPI, BackgroundTasks, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.config import settings
from src.gtfs_bc.realtime.infrastructure.services.gtfs_rt_scheduler import lifespan_with_scheduler


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    # Validate SECRET_KEY is properly configured in production
    settings.auth.validate_secret_key(settings.ENVIRONMENT)

    app = FastAPI(
        title="RenfeServer API",
        description="API de información de transporte ferroviario en España",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan_with_scheduler,
    )

    # CORS middleware - Public API, no credentials needed
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # Register routers
    from adapters.http.api.gtfs.routers import import_router, realtime_router, query_router, eta_router, network_router
    app.include_router(import_router, prefix="/api/v1")
    app.include_router(realtime_router, prefix="/api/v1")
    app.include_router(query_router, prefix="/api/v1")
    app.include_router(eta_router, prefix="/api/v1")
    app.include_router(network_router, prefix="/api/v1")

    # Static files (logos, etc.)
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/health")
    async def health_check():
        """Health check endpoint.

        Returns 503 until GTFS data is loaded into memory.
        This prevents Kubernetes/Docker from routing traffic before the app is ready.
        """
        from fastapi.responses import JSONResponse
        from src.gtfs_bc.routing.gtfs_store import GTFSStore

        store = GTFSStore.get_instance()

        if not store.is_loaded:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "loading",
                    "message": "GTFS data is being loaded into memory"
                }
            )

        return {
            "status": "healthy",
            "gtfs_store": {
                "loaded": True,
                "load_time_seconds": round(store.load_time_seconds, 1),
                "stats": store.stats
            }
        }

    @app.post("/admin/reload-gtfs")
    async def reload_gtfs(
        background_tasks: BackgroundTasks,
        x_admin_token: str = Header(None, alias="X-Admin-Token")
    ):
        """Reload GTFS data into memory without restarting the server.

        This endpoint triggers a background reload of all GTFS data.
        The reload is done in a background task to not block the request.

        Note: During reload, the old data remains available for requests.
        Once the new data is loaded, it atomically replaces the old data.

        Requires X-Admin-Token header for authentication.
        """
        # Verify admin token
        expected_token = os.getenv('ADMIN_TOKEN')
        if not expected_token or x_admin_token != expected_token:
            raise HTTPException(status_code=401, detail="Unauthorized: Invalid or missing X-Admin-Token")

        from src.gtfs_bc.routing.gtfs_store import GTFSStore
        from core.database import SessionLocal

        def do_reload():
            db = SessionLocal()
            try:
                store = GTFSStore.get_instance()
                store.reload_data(db)
            finally:
                db.close()

        background_tasks.add_task(do_reload)

        return {
            "status": "reload_initiated",
            "message": "GTFS data reload started in background"
        }

    return app


app = create_app()
