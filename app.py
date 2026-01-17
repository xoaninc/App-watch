from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy"}

    return app


app = create_app()
