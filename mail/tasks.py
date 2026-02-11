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
        # Capture timestamp before sync to identify emails synced in this batch
        from django.utils import timezone
        from django.db.models import Q, Count
        sync_start_time = timezone.now()
        
        sync_service = EmailSyncService()
        result = sync_service.sync_account(account, max_results=50)

        # Process emails that were synced in this batch and don't have tasks yet
        # Use the synced_email_ids from the result to accurately track which emails were synced
        synced_email_ids = result.get("synced_email_ids", [])
        
        # Import Task model to check for existing tasks
        from jobs.models import Task
        
        # Find threads that already have tasks (to avoid re-processing emails whose tasks were consolidated)
        threads_with_tasks = Task.objects.filter(
            account=account,
            thread__isnull=False
        ).values_list('thread_id', flat=True).distinct()
        
        # Always check for emails without tasks and process them
        # This ensures we don't miss any emails, even if synced_email_ids is empty or incorrect
        # Exclude emails whose threads already have tasks (to prevent re-processing after consolidation)
        emails_without_tasks = EmailMessage.objects.filter(
            account=account
        ).annotate(
            task_count=Count('tasks')
        ).filter(
            task_count=0
        ).exclude(
            thread_id__in=threads_with_tasks
        ).order_by("-created_at")
        
        # If we have synced emails, prioritize those
        if synced_email_ids:
            # First, process synced emails that don't have tasks
            synced_emails_to_process = emails_without_tasks.filter(
                pk__in=synced_email_ids
            )
            
            for email_msg in synced_emails_to_process:
                try:
                    process_email.delay(email_msg.pk)
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to queue process_email task for email {email_msg.pk}: {e}", exc_info=True)
        
        # Also process any other emails without tasks (limit to 20 to avoid overload)
        # This catches emails that might have been missed in previous syncs
        all_emails_to_process = emails_without_tasks.exclude(
            pk__in=synced_email_ids
        )[:20]  # Limit to 20 to avoid processing too many at once
        
        for email_msg in all_emails_to_process:
            try:
                process_email.delay(email_msg.pk)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to queue process_email task for email {email_msg.pk}: {e}", exc_info=True)
        
        # Check status of emails that have tasks (reverse sync)
        # Limit to recent emails to avoid checking too many at once
        emails_with_tasks = EmailMessage.objects.filter(
            account=account
        ).annotate(
            task_count=Count('tasks')
        ).filter(
            task_count__gt=0
        ).order_by("-updated_at")[:50]  # Check up to 50 most recently updated emails with tasks
        
        if emails_with_tasks.exists():
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"[Email Sync] Starting reverse sync - checking status of {emails_with_tasks.count()} emails with tasks")
            
            status_result = sync_service.sync_email_status(account, list(emails_with_tasks))
            result["status_checked"] = status_result.get("checked", 0)
            result["status_updated"] = status_result.get("updated", 0)
            result["status_errors"] = status_result.get("errors", 0)
            
            logger.info(f"[Email Sync] Reverse sync complete - Checked: {result['status_checked']}, Updated: {result['status_updated']}, Errors: {result['status_errors']}")
        else:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"[Email Sync] No emails with tasks found to check status for")

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
