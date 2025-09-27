"""
Scheduled tasks configuration for Celery Beat
"""

from celery.schedules import crontab
from app.celery_app import celery
from app.tasks.match_status import update_match_statuses_task

# Configure periodic tasks
celery.conf.beat_schedule = {
    'update-match-statuses': {
        'task': 'app.tasks.match_status.update_match_statuses_task',
        'schedule': crontab(minute='*/5'),  # Run every 5 minutes
    },
}

# Optional: Configure timezone
celery.conf.timezone = 'Asia/Kolkata'
