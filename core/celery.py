from celery import Celery

from core.config import settings

celery_app = Celery(
    "renfeserver",
    broker=settings.celery.CELERY_BROKER_URL,
    backend=settings.celery.CELERY_RESULT_BACKEND,
)

# Configure Celery
celery_app.conf.update(
    # Task settings
    task_time_limit=settings.celery.CELERY_TASK_TIME_LIMIT,
    task_soft_time_limit=settings.celery.CELERY_TASK_SOFT_TIME_LIMIT,

    # Result settings
    result_expires=3600,  # Results expire after 1 hour

    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # Serialization settings
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Timezone
    timezone="Europe/Madrid",
    enable_utc=True,

    # Task routes
    task_routes={
        "src.gtfs_bc.realtime.infrastructure.tasks.*": {"queue": "gtfs_realtime"},
    },

    # Beat schedule for periodic tasks
    beat_schedule={
        "fetch-gtfs-realtime-every-30-seconds": {
            "task": "src.gtfs_bc.realtime.infrastructure.tasks.fetch_gtfs_realtime",
            "schedule": 30.0,  # Every 30 seconds
            "options": {"queue": "gtfs_realtime"},
        },
    },
)

# Autodiscover tasks
celery_app.autodiscover_tasks([
    "src.gtfs_bc.realtime.infrastructure.tasks",
])
