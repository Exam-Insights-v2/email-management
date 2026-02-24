"""
Helpers for post-connect onboarding: queue full sync.
Used by account OAuth callbacks (Settings and login) to avoid duplicating logic.
"""
import logging

from accounts.models import Account
from mail.tasks import sync_account_emails

logger = logging.getLogger(__name__)
sync_audit = logging.getLogger("mail.sync_audit")


def trigger_sync_after_connect(account: Account) -> tuple[bool, str | None]:
    """
    Queue full sync for the account (runs in Celery worker).
    Returns (success, error_message). success is True if the task was queued.
    """
    try:
        logger.info(
            "Onboarding: queuing full sync for account_id=%s (sync runs in Celery worker; check worker logs for audit)",
            account.pk,
        )
        sync_audit.info(
            "Onboarding: queuing full sync; audit logs will appear in Celery worker output",
            extra={"account_id": account.pk},
        )
        sync_account_emails.delay(account.pk)
        return True, None
    except Exception as e:
        return False, str(e)
