"""Rate limiting configuration for the API.

Uses SlowAPI with in-memory storage (suitable for single-instance deployments).
For multi-instance deployments, configure Redis backend.

Rate limits are defined per endpoint type:
- Critical: Computationally expensive endpoints (route-planner, realtime fetch)
- High: Database-heavy endpoints (departures, correspondences)
- Medium: Standard endpoints (routes, stops, networks)
- Low: Lightweight endpoints (health, static data)
"""

import os
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse


def get_client_identifier(request: Request) -> str:
    """Get client identifier for rate limiting.

    Uses X-Forwarded-For header if behind a proxy, otherwise remote address.
    For authenticated requests, could use token/user_id instead.
    """
    # Check for proxy headers (nginx, cloudflare, etc.)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take the first IP (original client)
        return forwarded.split(",")[0].strip()

    # Check for Cloudflare header
    cf_connecting_ip = request.headers.get("CF-Connecting-IP")
    if cf_connecting_ip:
        return cf_connecting_ip

    return get_remote_address(request)


# Initialize limiter with custom key function
# Uses in-memory storage by default (suitable for single instance)
# For Redis: Set RATE_LIMIT_STORAGE_URI=redis://localhost:6379
# Note: REDIS_URL is used by Celery, separate env var for rate limiting
rate_limit_storage = os.getenv("RATE_LIMIT_STORAGE_URI", "memory://")
limiter = Limiter(
    key_func=get_client_identifier,
    default_limits=["200/minute"],  # Default limit for unlabeled endpoints
    storage_uri=rate_limit_storage,
    strategy="fixed-window",  # or "moving-window" for smoother limiting
)


# Rate limit definitions by endpoint category
class RateLimits:
    """Centralized rate limit definitions."""

    # Critical - computationally expensive
    ROUTE_PLANNER = "30/minute"      # RAPTOR algorithm
    REALTIME_FETCH = "5/minute"      # External API calls
    ADMIN_RELOAD = "2/minute"        # Heavy operation

    # High - database heavy
    DEPARTURES = "120/minute"        # Multiple JOINs, RT lookups
    CORRESPONDENCES = "60/minute"    # May call BRouter
    COORDINATES = "60/minute"        # Geo queries

    # Medium - standard queries
    ROUTES = "200/minute"
    STOPS = "200/minute"
    NETWORKS = "200/minute"
    SHAPES = "100/minute"

    # Low - lightweight
    HEALTH = "1000/minute"           # Health checks
    DEFAULT = "200/minute"


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Custom handler for rate limit exceeded errors.

    Returns a JSON response with details about the limit.
    """
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": f"Rate limit exceeded: {exc.detail}",
            "retry_after": getattr(exc, "retry_after", 60),
        },
        headers={
            "Retry-After": str(getattr(exc, "retry_after", 60)),
            "X-RateLimit-Limit": str(exc.detail) if exc.detail else "unknown",
        }
    )
