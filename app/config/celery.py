"""Celery configuration."""
from celery import Celery
import os

# Initialize Sentry early for Celery workers
from app.config.sentry import init_sentry

init_sentry()

from app.utils.logger import get_logger

logger = get_logger(__name__)

# Celery configuration
broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

celery_app = Celery(
    "marb_risk_engine",
    broker=broker_url,
    backend=result_backend,
    include=["app.services.queue.tasks"],
)

# Celery settings
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

