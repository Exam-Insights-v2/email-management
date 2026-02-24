"""
Sync service for ensuring exactly one task exists for an email/thread (with consolidation),
and for querying which emails need processing.
Used by process_email (Celery), action executors, sync_account_emails, and create_tasks_for_emails.
"""
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from django.db import transaction
from django.db.models import Count, QuerySet
from django.utils import timezone

from accounts.models import Account
from jobs.models import Task, TaskStatus
from mail.models import EmailMessage

logger = logging.getLogger(__name__)


def get_emails_to_process(
    account: Account,
    *,
    limit: Optional[int] = None,
    exclude_threads_with_tasks: bool = True,
) -> QuerySet:
    """
    Return emails that have no task and (optionally) whose thread has no task.
    Single source of truth for "who to process" used by sync task and management command.
    Callers can .filter(pk__in=synced_ids) or .exclude(pk__in=synced_ids)[:n] for prioritisation.

    limit: optional cap on returned count.
    exclude_threads_with_tasks: if True, exclude emails whose thread already has any task.
    """
    qs = (
        EmailMessage.objects.filter(account=account)
        .annotate(task_count=Count("tasks"))
        .filter(task_count=0)
    )
    if exclude_threads_with_tasks:
        threads_with_tasks = Task.objects.filter(
            account=account,
            thread__isnull=False,
        ).values_list("thread_id", flat=True).distinct()
        qs = qs.exclude(thread_id__in=threads_with_tasks)
    qs = qs.select_related("account", "thread").order_by("-created_at")
    if limit is not None:
        qs = qs[:limit]
    return qs


def ensure_task_for_email(
    email: EmailMessage,
    classification: Dict[str, Any],
) -> Task:
    """
    Ensure exactly one task exists for this email (and its thread), applying consolidation
    rules: if we haven't replied and there are existing active tasks in the thread,
    merge into one task; otherwise get_or_create for this email.

    classification must have: task_title, task_description, priority.
    classification may have: due_at (datetime | None).

    Does not apply labels or trigger side effects; caller does that.
    """
    due_at = classification.get("due_at")
    if due_at is not None and not isinstance(due_at, datetime):
        due_at = None

    with transaction.atomic():
        email.refresh_from_db()
        if not email.thread_id:
            # Should not happen for normal flows
            task = Task.objects.create(
                account=email.account,
                email_message=email,
                thread=None,
                title=(classification.get("task_title") or email.subject or "")[:255],
                description=classification.get("task_description") or "",
                priority=classification.get("priority", 1),
                due_at=due_at,
                status=TaskStatus.PENDING,
            )
            return task

        has_replied = email.thread.messages.filter(
            from_address=email.account.email
        ).exists()

        all_thread_tasks = Task.objects.filter(
            account=email.account,
            thread=email.thread,
        ).select_related("email_message").order_by("-created_at")

        existing_tasks = all_thread_tasks.filter(
            status__in=[TaskStatus.PENDING, TaskStatus.IN_PROGRESS]
        )
        should_consolidate = not has_replied and existing_tasks.exists()

        if should_consolidate:
            task_to_keep = existing_tasks.filter(status=TaskStatus.IN_PROGRESS).first()
            if not task_to_keep:
                task_to_keep = existing_tasks.first()

            all_emails_in_thread = email.thread.messages.filter(account=email.account)
            thread_count = all_emails_in_thread.count()

            all_priorities = [t.priority for t in existing_tasks] + [
                classification.get("priority", 1)
            ]
            merged_priority = max(all_priorities)

            all_due_dates = [t.due_at for t in existing_tasks if t.due_at] + (
                [due_at] if due_at else []
            )
            merged_due_at = min(all_due_dates) if all_due_dates else due_at

            merged_status = (
                task_to_keep.status
                if task_to_keep.status == TaskStatus.IN_PROGRESS
                else TaskStatus.PENDING
            )

            all_tasks_to_delete = all_thread_tasks.exclude(pk=task_to_keep.pk)
            delete_count = all_tasks_to_delete.count()

            merged_description = classification.get("task_description") or ""
            if delete_count > 0:
                if thread_count > 1:
                    merged_description += (
                        f"\n\n[Part of conversation thread with {thread_count} message(s). "
                        f"Consolidated from {delete_count} previous task(s).]"
                    )
                else:
                    merged_description += (
                        f"\n\n[Consolidated from {delete_count} previous task(s).]"
                    )

            task_to_keep.email_message = email
            task_to_keep.title = (classification.get("task_title") or "")[:255]
            task_to_keep.description = merged_description[:5000]
            task_to_keep.priority = merged_priority
            task_to_keep.due_at = merged_due_at
            task_to_keep.status = merged_status
            task_to_keep.save()

            if delete_count > 0:
                all_tasks_to_delete.delete()

            return task_to_keep

        existing_task_for_email = Task.objects.filter(
            account=email.account,
            email_message=email,
        ).first()

        if (
            existing_task_for_email
            and existing_tasks.exists()
            and not has_replied
        ):
            task_to_keep = (
                existing_tasks.filter(status=TaskStatus.IN_PROGRESS).first()
                or existing_tasks.first()
                or existing_task_for_email
            )
            if task_to_keep.pk != existing_task_for_email.pk:
                existing_task_for_email.delete()
                task_to_keep.email_message = email
                task_to_keep.title = (classification.get("task_title") or "")[:255]
                task_to_keep.description = classification.get("task_description") or ""
                task_to_keep.priority = max(
                    task_to_keep.priority, classification.get("priority", 1)
                )
                if due_at and (
                    not task_to_keep.due_at or due_at < task_to_keep.due_at
                ):
                    task_to_keep.due_at = due_at
                task_to_keep.save()
                all_thread_tasks.exclude(pk=task_to_keep.pk).delete()
                return task_to_keep
            else:
                task_to_keep.title = (classification.get("task_title") or "")[:255]
                task_to_keep.description = classification.get("task_description") or ""
                task_to_keep.priority = max(
                    task_to_keep.priority, classification.get("priority", 1)
                )
                if due_at and (
                    not task_to_keep.due_at or due_at < task_to_keep.due_at
                ):
                    task_to_keep.due_at = due_at
                task_to_keep.save()
                all_thread_tasks.exclude(pk=task_to_keep.pk).delete()
                return task_to_keep

        task, created = Task.objects.get_or_create(
            account=email.account,
            email_message=email,
            thread=email.thread,
            defaults={
                "title": (classification.get("task_title") or "")[:255],
                "description": classification.get("task_description") or "",
                "priority": classification.get("priority", 1),
                "due_at": due_at,
                "status": TaskStatus.PENDING,
            },
        )
        if not created:
            task.title = (classification.get("task_title") or "")[:255]
            task.description = classification.get("task_description") or ""
            task.priority = classification.get("priority", 1)
            if due_at:
                task.due_at = due_at
            task.save()

        if not has_replied:
            other_tasks = Task.objects.filter(
                account=email.account,
                thread=email.thread,
                status__in=[TaskStatus.PENDING, TaskStatus.IN_PROGRESS],
            ).exclude(pk=task.pk)
            if other_tasks.exists():
                all_priorities = [t.priority for t in other_tasks] + [task.priority]
                task.priority = max(all_priorities)
                all_due_dates = [t.due_at for t in other_tasks if t.due_at] + (
                    [task.due_at] if task.due_at else []
                )
                if all_due_dates:
                    task.due_at = min(all_due_dates)
                if task.status != TaskStatus.IN_PROGRESS:
                    task.status = TaskStatus.PENDING
                all_emails_in_thread = email.thread.messages.filter(
                    account=email.account
                )
                thread_count = all_emails_in_thread.count()
                merged_description = classification.get("task_description") or ""
                other_count = other_tasks.count()
                if thread_count > 1:
                    merged_description += (
                        f"\n\n[Part of conversation thread with {thread_count} message(s). "
                        f"Consolidated from {other_count} previous task(s).]"
                    )
                else:
                    merged_description += (
                        f"\n\n[Consolidated from {other_count} previous task(s).]"
                    )
                task.description = merged_description[:5000]
                task.email_message = email
                task.save()
                other_tasks.delete()

        return task
