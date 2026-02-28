import json
import logging

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import BrowserPushSubscription, NotificationPreference

logger = logging.getLogger(__name__)


def is_web_push_configured() -> bool:
    return bool(
        getattr(settings, "WEB_PUSH_VAPID_PUBLIC_KEY", "").strip()
        and getattr(settings, "WEB_PUSH_VAPID_PRIVATE_KEY", "").strip()
    )


def _send_web_push(subscription: BrowserPushSubscription, payload: dict) -> bool:
    if not is_web_push_configured():
        return False

    try:
        from pywebpush import WebPushException, webpush
    except Exception:
        logger.warning("pywebpush is not installed; skipping push send.")
        return False

    try:
        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {
                    "p256dh": subscription.p256dh,
                    "auth": subscription.auth,
                },
            },
            data=json.dumps(payload),
            vapid_private_key=settings.WEB_PUSH_VAPID_PRIVATE_KEY,
            vapid_claims={
                "sub": f"mailto:{getattr(settings, 'WEB_PUSH_CONTACT_EMAIL', 'hello@example.com')}",
            },
        )
        subscription.last_active_at = timezone.now()
        subscription.save(update_fields=["last_active_at", "updated_at"])
        return True
    except WebPushException as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        if status_code in (404, 410):
            subscription.is_active = False
            subscription.save(update_fields=["is_active", "updated_at"])
        logger.warning(
            "Web push failed for subscription %s (status=%s): %s",
            subscription.pk,
            status_code,
            exc,
        )
        return False
    except Exception as exc:
        logger.exception("Unexpected web push error for subscription %s: %s", subscription.pk, exc)
        return False


def send_task_created_push(task) -> int:
    """Send push notifications to account users who have task push enabled."""
    if not is_web_push_configured():
        return 0

    user_ids = list(task.account.users.values_list("id", flat=True))
    if not user_ids:
        return 0

    disabled_user_ids = set(
        NotificationPreference.objects.filter(
            account=task.account,
            user_id__in=user_ids,
            task_push_enabled=False,
        ).values_list("user_id", flat=True)
    )
    target_user_ids = [uid for uid in user_ids if uid not in disabled_user_ids]
    if not target_user_ids:
        return 0

    task_url = f"{reverse('tasks_list')}?task={task.pk}"
    payload = {
        "title": "New task created",
        "body": task.title or f"TASK-{task.account_task_number}",
        "url": task_url,
        "type": "task_created",
        "tag": f"task-{task.pk}",
        "account_id": task.account_id,
    }

    subscriptions = BrowserPushSubscription.objects.filter(
        account=task.account,
        user_id__in=target_user_ids,
        is_active=True,
    )
    sent_count = 0
    for subscription in subscriptions:
        if _send_web_push(subscription, payload):
            sent_count += 1
    return sent_count
