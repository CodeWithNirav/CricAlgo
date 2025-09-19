"""
Celery application configuration
"""

from celery import Celery
from app.core.config import settings

# Create Celery instance
celery = Celery(
    "cricalgo",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.tasks"]
)

# Configure Celery
celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_disable_rate_limits=False,
    task_compression="gzip",
    result_compression="gzip",
    result_expires=3600,  # 1 hour
    task_routes={
        "app.tasks.tasks.process_deposit": {"queue": "deposits"},
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
