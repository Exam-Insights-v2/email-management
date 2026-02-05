from celery import shared_task
from django.db import transaction

from accounts.models import Account
from automation.tasks import process_email
from mail.models import EmailMessage
from mail.services import EmailSyncService


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

    try:
        sync_service = EmailSyncService()
        result = sync_service.sync_account(account, max_results=50)

        # Trigger processing for newly created emails
        if result["created"] > 0:
            # Get newly created emails (those created in this sync)
            new_emails = EmailMessage.objects.filter(
                account=account, created_at__gte=account.last_synced_at
            )[:result["created"]]

            for email_msg in new_emails:
                # Process email asynchronously
                process_email.delay(email_msg.pk)

        return result
    except Exception as e:
        return {"error": str(e)}


@shared_task
def sync_all_accounts():
    """Sync all connected accounts"""
    accounts = Account.objects.filter(is_connected=True, sync_enabled=True)
    results = []

    for account in accounts:
        task_result = sync_account_emails.delay(account.pk)
        results.append({"account_id": account.pk, "task_id": task_result.id})

    return results
