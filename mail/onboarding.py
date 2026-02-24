"""
Helpers for post-connect onboarding: bootstrap sync + queue full sync.
Used by account OAuth callbacks (Settings and login) to avoid duplicating logic.
"""
import logging

from accounts.models import Account

logger = logging.getLogger(__name__)

BOOTSTRAP_MAX_MESSAGES = 100


def trigger_sync_after_connect(account: Account) -> tuple[bool, str | None]:
    """
    Run a small in-process sync so the user sees some emails immediately, then queue
    full sync. Returns (success, error_message). success is True if at least the
    queue succeeded; error_message is set if queue failed (for user-facing message).
    """
    try:
        from mail.services import EmailSyncService, GmailService

        if account.provider == "gmail":
            GmailService.clear_cache(account.pk)
        EmailSyncService().sync_account(
            account,
            max_total=BOOTSTRAP_MAX_MESSAGES,
            force_initial=True,
        )
    except Exception:
        pass
    try:
        from mail.tasks import sync_account_emails

        sync_account_emails.delay(account.pk)
        return True, None
    except Exception as e:
        return False, str(e)
