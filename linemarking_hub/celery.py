import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "linemarking_hub.settings")

app = Celery("linemarking_hub")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Periodic tasks - sync emails every minute
app.conf.beat_schedule = {
    "sync-all-accounts": {
        "task": "mail.tasks.sync_all_accounts",
        "schedule": crontab(minute="*"),  # Every minute
    },
}
