from celery import shared_task
from django.db import transaction

from accounts.models import Account
from automation.tasks import process_email
from mail.models import EmailMessage
from mail.services import EmailSyncService


@shared_task
def sync_account_emails(account_id: int):
    """Sync emails for an account and trigger processing"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        account = Account.objects.get(pk=account_id)
        logger.info(f"[Email Sync] Starting sync for account {account_id} ({account.email})")
    except Account.DoesNotExist:
        logger.error(f"[Email Sync] Account {account_id} not found")
        return {"error": "Account not found"}

    if not account.is_connected:
        logger.warning(f"[Email Sync] Account {account_id} is not connected")
        return {"error": "Account is not connected"}

    if not account.sync_enabled:
        logger.warning(f"[Email Sync] Sync is disabled for account {account_id}")
        return {"error": "Sync is disabled for this account"}

    try:
        # Capture timestamp before sync to identify emails synced in this batch
        from django.utils import timezone
        from django.db.models import Q, Count
        sync_start_time = timezone.now()
        
        logger.info(f"[Email Sync] Fetching emails from provider (last_synced_at: {account.last_synced_at})")
        sync_service = EmailSyncService()
        try:
            result = sync_service.sync_account(account, max_results=50)
            logger.info(f"[Email Sync] Fetched {result.get('total', 0)} emails - Created: {result.get('created', 0)}, Updated: {result.get('updated', 0)}")
        except ValueError as e:
            error_msg = str(e)
            if "not connected" in error_msg.lower() or "token is invalid" in error_msg.lower():
                logger.error(f"[Email Sync] Token error for account {account_id}: {error_msg}")
                # Mark account as disconnected
                account.is_connected = False
                account.save(update_fields=["is_connected"])
                logger.warning(f"[Email Sync] Marked account {account_id} as disconnected due to token error")
                return {"error": "Account token is invalid. Please reconnect your account.", "disconnected": True}
            raise  # Re-raise if it's a different ValueError

        # Process emails that were synced in this batch and don't have tasks yet
        # Use the synced_email_ids from the result to accurately track which emails were synced
        synced_email_ids = result.get("synced_email_ids", [])
        logger.info(f"[Email Sync] Synced email IDs: {synced_email_ids}")
        
        # Import Task model to check for existing tasks
        from jobs.models import Task
        
        # Find threads that already have tasks (to avoid re-processing emails whose tasks were consolidated)
        threads_with_tasks = Task.objects.filter(
            account=account,
            thread__isnull=False
        ).values_list('thread_id', flat=True).distinct()
        logger.info(f"[Email Sync] Found {threads_with_tasks.count()} threads with existing tasks")
        
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
        
        total_emails_without_tasks = emails_without_tasks.count()
        logger.info(f"[Email Sync] Found {total_emails_without_tasks} emails without tasks (excluding threads with tasks)")
        
        # Log details of emails without tasks
        if total_emails_without_tasks > 0:
            sample_emails = list(emails_without_tasks[:10])
            logger.info(f"[Email Sync] Sample emails without tasks:")
            for email_msg in sample_emails:
                logger.info(f"  - Email #{email_msg.pk}: '{email_msg.subject or '(No subject)'}' from {email_msg.from_address} (created: {email_msg.created_at})")
        
        # If we have synced emails, prioritize those
        if synced_email_ids:
            # First, process synced emails that don't have tasks
            synced_emails_to_process = emails_without_tasks.filter(
                pk__in=synced_email_ids
            )
            synced_count = synced_emails_to_process.count()
            logger.info(f"[Email Sync] Processing {synced_count} newly synced emails without tasks")
            
            for email_msg in synced_emails_to_process:
                try:
                    logger.info(f"[Email Sync] Queuing process_email for email #{email_msg.pk}: '{email_msg.subject or '(No subject)'}'")
                    process_email.delay(email_msg.pk)
                except Exception as e:
                    logger.error(f"[Email Sync] Failed to queue process_email task for email {email_msg.pk}: {e}", exc_info=True)
        else:
            logger.warning(f"[Email Sync] No synced email IDs returned from sync_account")
        
        # Also process any other emails without tasks (limit to 20 to avoid overload)
        # This catches emails that might have been missed in previous syncs
        all_emails_to_process = emails_without_tasks.exclude(
            pk__in=synced_email_ids
        )[:20]  # Limit to 20 to avoid processing too many at once
        
        other_count = all_emails_to_process.count()
        if other_count > 0:
            logger.info(f"[Email Sync] Processing {other_count} other emails without tasks (not in synced batch)")
            for email_msg in all_emails_to_process:
                try:
                    logger.info(f"[Email Sync] Queuing process_email for email #{email_msg.pk}: '{email_msg.subject or '(No subject)'}'")
                    process_email.delay(email_msg.pk)
                except Exception as e:
                    logger.error(f"[Email Sync] Failed to queue process_email task for email {email_msg.pk}: {e}", exc_info=True)
        else:
            logger.info(f"[Email Sync] No other emails to process")
        
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
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info("[Email Sync] ===== sync_all_accounts task triggered =====")
    accounts = Account.objects.filter(is_connected=True, sync_enabled=True)
    account_count = accounts.count()
    logger.info(f"[Email Sync] Found {account_count} connected account(s) with sync enabled")
    
    if account_count == 0:
        logger.warning("[Email Sync] No connected accounts with sync enabled found!")
        return {"message": "No accounts to sync", "accounts": []}
    
    results = []
    for account in accounts:
        logger.info(f"[Email Sync] Queuing sync for account {account.pk} ({account.email})")
        task_result = sync_account_emails.delay(account.pk)
        results.append({"account_id": account.pk, "task_id": task_result.id})
        logger.info(f"[Email Sync] Queued sync task {task_result.id} for account {account.pk}")

    logger.info(f"[Email Sync] ===== Queued {len(results)} sync task(s) =====")
    return results
