import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from accounts.models import Account
from jobs.models import TaskStatus

logger = logging.getLogger(__name__)
sync_audit = logging.getLogger("mail.sync_audit")
from automation.tasks import process_email
from mail.models import EmailMessage, SyncRun
from mail.services import EmailSyncService
from mail.sync_status import (
    acquire_sync_lock,
    clear_last_sync_error,
    release_sync_lock,
    set_last_sync_error,
    set_sync_in_progress,
    should_run_status_sync,
)


@shared_task
def sync_account_emails(account_id: int):
    """Sync emails for an account and trigger processing"""
    logger.info("sync_account_emails starting for account_id=%s", account_id)
    try:
        account = Account.objects.get(pk=account_id)
    except Account.DoesNotExist:
        logger.warning("sync_account_emails: account_id=%s not found", account_id)
        return {"error": "Account not found"}

    if not account.is_connected:
        logger.warning("sync_account_emails: account_id=%s not connected", account_id)
        return {"error": "Account is not connected"}

    if not account.sync_enabled:
        logger.warning("sync_account_emails: account_id=%s sync disabled", account_id)
        return {"error": "Sync is disabled for this account"}

    lock_acquired = acquire_sync_lock(account_id, timeout_seconds=300)
    if not lock_acquired:
        logger.info(
            "sync_account_emails skipped account_id=%s reason=lock-held",
            account_id,
        )
        return {"skipped": "Sync already running for this account"}

    set_sync_in_progress(account_id, True)
    clear_last_sync_error(account_id)
    sync_run_started = timezone.now()
    try:
        from automation.task_from_email import get_emails_to_process

        sync_service = EmailSyncService()
        try:
            result = sync_service.sync_account(account)
        except ValueError as e:
            error_msg = str(e)
            logger.warning("sync_account_emails: sync_account failed account_id=%s error=%s", account_id, error_msg)
            set_last_sync_error(account_id, error_msg)
            set_sync_in_progress(account_id, False)
            if "not connected" in error_msg.lower() or "token is invalid" in error_msg.lower():
                return {"error": "Account token is invalid. Please reconnect your account."}
            raise

        synced_email_ids = result.get("synced_email_ids", [])

        emails_without_tasks = get_emails_to_process(account, exclude_threads_with_tasks=True, log_audit=True)
        emails_without_tasks_count = emails_without_tasks.count()

        to_process_synced = list(emails_without_tasks.filter(pk__in=synced_email_ids))
        other_qs = emails_without_tasks.exclude(pk__in=synced_email_ids)[:20]
        other_emails_to_process = list(other_qs)
        queued_ids = []

        if synced_email_ids:
            for email_msg in to_process_synced:
                try:
                    process_email.delay(email_msg.pk)
                    queued_ids.append(email_msg.pk)
                except Exception:
                    pass

        for email_msg in other_emails_to_process:
            try:
                process_email.delay(email_msg.pk)
                queued_ids.append(email_msg.pk)
            except Exception:
                pass

        sync_audit.info(
            "sync_account_emails processing selection",
            extra={
                "account_id": account_id,
                "synced_email_ids_count": len(synced_email_ids),
                "emails_without_tasks_count": emails_without_tasks_count,
                "synced_eligible_count": len(to_process_synced),
                "other_queued_count": len(other_emails_to_process),
                "queued_for_process_email_count": len(queued_ids),
                "queued_email_ids_sample": queued_ids[:30] if len(queued_ids) > 30 else queued_ids,
            },
        )

        SyncRun.objects.create(
            account=account,
            phase=SyncRun.Phase.FULL,
            started_at=sync_run_started,
            finished_at=timezone.now(),
            params={
                "synced_email_ids_count": len(synced_email_ids),
                "queued_count": len(queued_ids),
            },
            message_ids_from_provider=result.get("message_ids_from_provider", []),
            synced_email_ids=synced_email_ids,
            thread_backfill_stats=result.get("thread_backfill_stats", {}),
            emails_queued_for_processing=queued_ids,
        )

        # Status sync is provider-expensive (one or more API requests per email).
        # Run immediately when sync changed data; otherwise debounce to avoid repeating
        # the same checks every minute.
        created_count = result.get("created", 0)
        updated_count = result.get("updated", 0)
        has_fresh_changes = (created_count + updated_count) > 0
        min_status_sync_interval = int(
            getattr(settings, "EMAIL_STATUS_SYNC_MIN_INTERVAL_SECONDS", 300)
        )
        run_status_sync = has_fresh_changes or should_run_status_sync(
            account_id, min_status_sync_interval
        )

        emails_with_open_tasks = list(
            EmailMessage.objects.filter(
                account=account,
                tasks__status__in=[TaskStatus.PENDING, TaskStatus.IN_PROGRESS],
            )
            .distinct()
            .order_by("-created_at")[:50]
        )

        if emails_with_open_tasks and run_status_sync:
            status_result = sync_service.sync_email_status(account, emails_with_open_tasks)
            result["status_checked"] = status_result.get("checked", 0)
            result["status_updated"] = status_result.get("updated", 0)
            result["status_errors"] = status_result.get("errors", 0)
        elif emails_with_open_tasks and not run_status_sync:
            sync_audit.info(
                "sync_account_emails status sync skipped by debounce",
                extra={
                    "account_id": account_id,
                    "open_task_email_count": len(emails_with_open_tasks),
                    "min_interval_seconds": min_status_sync_interval,
                },
            )

        clear_last_sync_error(account_id)
        logger.info(
            "sync_account_emails completed account_id=%s created=%s updated=%s total=%s",
            account_id,
            result.get("created", 0),
            result.get("updated", 0),
            result.get("total", 0),
        )
        return result
    except Exception as e:
        logger.exception("sync_account_emails failed account_id=%s", account_id)
        set_last_sync_error(account_id, str(e))
        return {"error": str(e)}
    finally:
        set_sync_in_progress(account_id, False)
        release_sync_lock(account_id)


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
