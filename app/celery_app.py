"""
Celery application configuration
"""

import os
from celery import Celery
from app.core.config import settings

# Use REDIS_URL as fallback for Celery broker
broker_url = os.environ.get('CELERY_BROKER_URL', os.environ.get('REDIS_URL', settings.celery_broker_url))
backend_url = os.environ.get('CELERY_RESULT_BACKEND', os.environ.get('REDIS_URL', settings.celery_result_backend))

# Create Celery instance
celery = Celery(
    "cricalgo",
    broker=broker_url,
    backend=backend_url,
    include=["app.tasks.tasks", "app.tasks.webhook_processing", "app.tasks.deposits"]
)

# Configure Celery
celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=False,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_disable_rate_limits=False,
    task_compression="gzip",
    result_compression="gzip",
    result_expires=3600,  # 1 hour
    worker_concurrency=int(os.getenv("CELERY_WORKER_CONCURRENCY", 4)),  # Default to 4, override with env
    task_routes={
        "app.tasks.deposits.process_deposit": {"queue": "deposits"},
        "app.tasks.tasks.process_withdrawal": {"queue": "withdrawals"},
        "app.tasks.tasks.compute_and_distribute_payouts": {"queue": "payouts"},
    },
    task_default_queue="default",
    task_default_exchange="default",
    task_default_exchange_type="direct",
    task_default_routing_key="default",
)

# For testing, we can run tasks synchronously
if settings.app_env == "testing":
    celery.conf.task_always_eager = True
    celery.conf.task_eager_propagates = True

if __name__ == "__main__":
    celery.start()
