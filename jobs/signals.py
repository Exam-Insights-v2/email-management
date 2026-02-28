import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from jobs.models import Task
from linemarking_hub.push_notifications import send_task_created_push

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Task)
def notify_on_task_created(sender, instance: Task, created: bool, **kwargs):
    if not created:
        return
    try:
        send_task_created_push(instance)
    except Exception:
        logger.exception("Failed to send task created push notification for task %s", instance.pk)
