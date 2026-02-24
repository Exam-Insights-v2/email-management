import logging

from celery import shared_task
from django.db import transaction

from accounts.models import Account

logger = logging.getLogger(__name__)
from automation.tasks import process_email
from mail.models import EmailMessage
from mail.services import EmailSyncService
from mail.sync_status import (
    clear_last_sync_error,
    get_sync_in_progress,
    set_last_sync_error,
    set_sync_in_progress,
)


@shared_task
def sync_account_emails(account_id: int):
    """Sync emails for an account and trigger processing"""
    try:
        account = Account.objects.get(pk=account_id)
    except Account.DoesNotExist:
        return {"error": "Account not found"}

    if not account.is_connected:
        return {"error": "Account is not connected"}

    if not account.sync_enabled:
        return {"error": "Sync is disabled for this account"}

    set_sync_in_progress(account_id, True)
    clear_last_sync_error(account_id)
    try:
        from django.db.models import Count

        from automation.task_from_email import get_emails_to_process

        sync_service = EmailSyncService()
        try:
            result = sync_service.sync_account(account)
        except ValueError as e:
            error_msg = str(e)
            set_last_sync_error(account_id, error_msg)
            set_sync_in_progress(account_id, False)
            if "not connected" in error_msg.lower() or "token is invalid" in error_msg.lower():
                return {"error": "Account token is invalid. Please reconnect your account."}
            raise

        synced_email_ids = result.get("synced_email_ids", [])

        emails_without_tasks = get_emails_to_process(account, exclude_threads_with_tasks=True)

        if synced_email_ids:
            synced_emails_to_process = emails_without_tasks.filter(pk__in=synced_email_ids)
            for email_msg in synced_emails_to_process:
                try:
                    process_email.delay(email_msg.pk)
                except Exception:
                    pass

        other_emails_to_process = emails_without_tasks.exclude(pk__in=synced_email_ids)[:20]
        for email_msg in other_emails_to_process:
            try:
                process_email.delay(email_msg.pk)
            except Exception:
                pass

        emails_with_tasks = EmailMessage.objects.filter(
            account=account
        ).annotate(
            task_count=Count('tasks')
        ).filter(
            task_count__gt=0
        ).order_by("-updated_at")[:50]

        if emails_with_tasks.exists():
            status_result = sync_service.sync_email_status(account, list(emails_with_tasks))
            result["status_checked"] = status_result.get("checked", 0)
            result["status_updated"] = status_result.get("updated", 0)
            result["status_errors"] = status_result.get("errors", 0)

        set_sync_in_progress(account_id, False)
        clear_last_sync_error(account_id)
        return result
    except Exception as e:
        set_sync_in_progress(account_id, False)
        set_last_sync_error(account_id, str(e))
        return {"error": str(e)}


@shared_task
def sync_all_accounts():
    """Sync all connected accounts"""
    accounts = Account.objects.filter(is_connected=True, sync_enabled=True)
    if not accounts.exists():
        return {"message": "No accounts to sync", "accounts": []}

    results = []
    for account in accounts:
        task_result = sync_account_emails.delay(account.pk)
        results.append({"account_id": account.pk, "task_id": task_result.id})
    return results
