from celery import shared_task
from django.db import transaction
from django.utils import timezone
from datetime import datetime
import logging

from automation.models import Action, EmailLabel, Label
from automation.services import OpenAIClient
from jobs.models import Task, TaskStatus
from mail.models import Draft, EmailMessage

logger = logging.getLogger(__name__)


def parse_due_date(date_str: str | None) -> datetime | None:
    """Parse due date string from AI response (YYYY-MM-DD format)"""
    if not date_str or date_str.lower() == "null":
        return None
    try:
        # Parse YYYY-MM-DD format
        parsed_date = datetime.strptime(date_str.strip(), "%Y-%m-%d")
        # Make timezone-aware using Django's timezone
        return timezone.make_aware(parsed_date)
    except (ValueError, AttributeError, TypeError):
        logger.warning(f"Could not parse due_date: {date_str}")
        return None


@shared_task
def process_email(email_message_id: int):
    """
    Process an email message: classify with AI and create task.
    Uses a single AI call to get all classification data.
    """
    logger.info(f"[Process Email] Starting processing for email #{email_message_id}")
    try:
        email = EmailMessage.objects.select_related("thread", "account").get(
            pk=email_message_id
        )
        logger.info(f"[Process Email] Email #{email_message_id}: '{email.subject or '(No subject)'}' from {email.from_address} (account: {email.account.email})")
    except EmailMessage.DoesNotExist:
        logger.warning(f"[Process Email] Email message {email_message_id} not found")
        return
    except Exception as e:
        logger.error(f"[Process Email] Error fetching email {email_message_id}: {e}", exc_info=True)
        return
    
    # Early exit: If this email already has a task, skip processing
    # This prevents re-processing when tasks are consolidated
    existing_tasks = email.tasks.all()
    if existing_tasks.exists():
        task_ids = [t.pk for t in existing_tasks]
        logger.info(f"[Process Email] Email {email_message_id} already has {existing_tasks.count()} task(s) (IDs: {task_ids}), skipping processing")
        return

    # Get available labels for this account
    # Labels where the email's account is the owner OR is in the accounts ManyToMany field
    # If accounts ManyToMany is empty, only the owner can use it
    from django.db.models import Q
    available_labels = list(
        Label.objects.filter(
            Q(account=email.account) | 
            (Q(accounts=email.account) & ~Q(accounts=None))
        ).distinct()
    )

    # SINGLE AI CALL - Get all classification data
    client = OpenAIClient()
    classification = client.classify_email(email, available_labels)

    # Parse due date if provided
    due_at = parse_due_date(classification.get("due_date"))

    # Apply labels from AI response first to validate
    # Step 1: Validate and filter labels using validation rules
    from automation.label_validator import validate_and_filter_labels
    
    raw_label_names = classification.get("labels", [])
    validated_label_names = validate_and_filter_labels(raw_label_names, max_labels=3)
    
    if len(raw_label_names) != len(validated_label_names):
        removed = set(raw_label_names) - set(validated_label_names)
        logger.info(
            f"Label validation filtered {len(raw_label_names)} labels to {len(validated_label_names)}. "
            f"Removed: {removed}"
        )
    
    # Step 2: Match validated labels to actual Label objects
    labels_to_apply = []
    for label_name in validated_label_names:
        # Find matching label (case-insensitive) - improved validation
        if not isinstance(label_name, str) or not label_name.strip():
            logger.warning(f"Invalid label name in classification: {label_name}")
            continue
            
        label = next(
            (
                l
                for l in available_labels
                if l.name.lower() == label_name.lower().strip()
            ),
            None,
        )
        if label:
            labels_to_apply.append(label)
        else:
            logger.warning(
                f"Label '{label_name}' from validated classification not found in available labels. "
                f"Available: {[l.name for l in available_labels]}"
            )

    # Check if we should consolidate with existing tasks in the same thread
    try:
        with transaction.atomic():
            # Check if we've replied to this thread (sent any emails from our account)
            has_replied = email.thread.messages.filter(
                from_address=email.account.email
            ).exists()
            
            # Find ALL existing tasks for this thread (including this email's task if it exists)
            all_thread_tasks = Task.objects.filter(
                account=email.account,
                thread=email.thread
            ).select_related('email_message').order_by('-created_at')
            
            # Find existing active tasks for this thread that are still active
            existing_tasks = all_thread_tasks.filter(
                status__in=[TaskStatus.PENDING, TaskStatus.IN_PROGRESS]
            )
            
            # Only consolidate if:
            # 1. We haven't replied yet
            # 2. There are existing active tasks for this thread
            should_consolidate = not has_replied and existing_tasks.exists()
            
            if should_consolidate:
                existing_task_count = existing_tasks.count()
                logger.info(f"[Process Email] Consolidating tasks: Found {existing_task_count} existing active task(s) in thread {email.thread.pk} (has_replied: {has_replied})")
                # Get the "best" existing task to keep (prefer in_progress, then most recent)
                task_to_keep = existing_tasks.filter(status=TaskStatus.IN_PROGRESS).first()
                if not task_to_keep:
                    task_to_keep = existing_tasks.first()
                logger.info(f"[Process Email] Keeping task #{task_to_keep.pk} for consolidation")
                
                # Use only the latest classification description (emails are linked via thread, no need to duplicate)
                # Check if this is part of a multi-email thread
                all_emails_in_thread = email.thread.messages.filter(
                    account=email.account
                )
                thread_count = all_emails_in_thread.count()
                
                # Merge priorities (keep highest)
                all_priorities = [t.priority for t in existing_tasks] + [classification["priority"]]
                merged_priority = max(all_priorities)
                
                # Merge due dates (keep earliest if any exist)
                all_due_dates = [t.due_at for t in existing_tasks if t.due_at] + ([due_at] if due_at else [])
                merged_due_at = min(all_due_dates) if all_due_dates else due_at
                
                # Preserve status (if in_progress, keep it; otherwise use pending)
                merged_status = task_to_keep.status if task_to_keep.status == TaskStatus.IN_PROGRESS else TaskStatus.PENDING
                
                # Collect task IDs that will be deleted for logging
                all_tasks_to_delete = all_thread_tasks.exclude(pk=task_to_keep.pk)
                task_ids_to_delete = list(all_tasks_to_delete.values_list('pk', flat=True))
                delete_count = len(task_ids_to_delete)
                
                # Build description with just the latest classification
                merged_description = classification['task_description']
                
                # Add consolidation note to description (without task IDs for account portability)
                if delete_count > 0:
                    if thread_count > 1:
                        merged_description += f"\n\n[Part of conversation thread with {thread_count} message(s). Consolidated from {delete_count} previous task(s).]"
                    else:
                        merged_description += f"\n\n[Consolidated from {delete_count} previous task(s).]"
                
                # Update the task to keep with merged information
                task_to_keep.email_message = email  # Update to latest email
                task_to_keep.title = classification["task_title"]
                task_to_keep.description = merged_description[:5000]  # Limit length
                task_to_keep.priority = merged_priority
                task_to_keep.due_at = merged_due_at
                task_to_keep.status = merged_status
                task_to_keep.save()
                
                # Delete other tasks for this thread (including any that might be done/cancelled)
                # We want to clean up ALL tasks for this thread except the one we're keeping
                if delete_count > 0:
                    all_tasks_to_delete.delete()
                
                task = task_to_keep
                created = False
            else:
                # No consolidation needed - create or update task normally
                # Check if a task already exists for this specific email_message
                # If it does and there are other tasks in the thread, we should still consolidate
                existing_task_for_email = Task.objects.filter(
                    account=email.account,
                    email_message=email
                ).first()
                
                if existing_task_for_email and existing_tasks.exists() and not has_replied:
                    # There's a task for this email AND other tasks in the thread
                    # We should consolidate, but we missed it - let's handle it now
                    # Re-run consolidation logic
                    should_consolidate = True
                    # This will be handled by re-entering the consolidation block
                    # But we can't easily do that here, so let's just update the existing task
                    # and delete others
                    task_to_keep = existing_tasks.filter(status=TaskStatus.IN_PROGRESS).first() or existing_tasks.first() or existing_task_for_email
                    
                    # If the task to keep is not the one for this email, update it
                    if task_to_keep.pk != existing_task_for_email.pk:
                        # Delete the task for this email and update the one to keep
                        existing_task_for_email.delete()
                        task_to_keep.email_message = email
                        task_to_keep.title = classification["task_title"]
                        task_to_keep.description = classification["task_description"]
                        task_to_keep.priority = max(task_to_keep.priority, classification["priority"])
                        if due_at and (not task_to_keep.due_at or due_at < task_to_keep.due_at):
                            task_to_keep.due_at = due_at
                        task_to_keep.save()
                        
                        # Delete other tasks
                        all_thread_tasks.exclude(pk=task_to_keep.pk).delete()
                        task = task_to_keep
                        created = False
                    else:
                        # The task for this email is the one to keep, just update it
                        task_to_keep.title = classification["task_title"]
                        task_to_keep.description = classification["task_description"]
                        task_to_keep.priority = max(task_to_keep.priority, classification["priority"])
                        if due_at and (not task_to_keep.due_at or due_at < task_to_keep.due_at):
                            task_to_keep.due_at = due_at
                        task_to_keep.save()
                        
                        # Delete other tasks
                        deleted_count = all_thread_tasks.exclude(pk=task_to_keep.pk).count()
                        all_thread_tasks.exclude(pk=task_to_keep.pk).delete()
                        logger.info(f"[Process Email] Consolidated tasks: kept task #{task_to_keep.pk}, deleted {deleted_count} other task(s) in thread")
                        task = task_to_keep
                        created = False
                else:
                    # Normal create/update path
                    logger.info(f"[Process Email] No consolidation needed - creating/updating task for email #{email_message_id}")
                    task, created = Task.objects.get_or_create(
                        account=email.account,
                        email_message=email,
                        thread=email.thread,
                        defaults={
                            "title": classification["task_title"],
                            "description": classification["task_description"],
                            "priority": classification["priority"],
                            "due_at": due_at,
                            "status": TaskStatus.PENDING,
                        },
                    )

                    if created:
                        logger.info(f"[Process Email] ✅ Created task #{task.pk} for email #{email_message_id}: '{task.title}' (priority: {task.priority})")
                    else:
                        logger.info(f"[Process Email] Updated existing task #{task.pk} for email #{email_message_id}")

                    # Update task if it already existed
                    if not created:
                        task.title = classification["task_title"]
                        task.description = classification["task_description"]
                        task.priority = classification["priority"]
                        if due_at:
                            task.due_at = due_at
                        task.save()
                    
                    # After creating/updating, check again if we should consolidate
                    # This handles the case where tasks were created in parallel
                    if not has_replied:
                        # Re-check for other tasks in the thread
                        other_tasks = Task.objects.filter(
                            account=email.account,
                            thread=email.thread,
                            status__in=[TaskStatus.PENDING, TaskStatus.IN_PROGRESS]
                        ).exclude(pk=task.pk)
                        
                        if other_tasks.exists():
                            other_count = other_tasks.count()
                            logger.info(f"[Process Email] Post-creation consolidation: Found {other_count} other task(s) in thread, merging into task #{task.pk}")
                            
                            # Use the current task as the one to keep (it's the latest)
                            task_to_keep = task
                            
                            # Merge information from other tasks
                            all_priorities = [t.priority for t in other_tasks] + [task.priority]
                            task.priority = max(all_priorities)
                            
                            all_due_dates = [t.due_at for t in other_tasks if t.due_at] + ([task.due_at] if task.due_at else [])
                            if all_due_dates:
                                task.due_at = min(all_due_dates)
                            
                            # Preserve status if task is in_progress
                            if task.status != TaskStatus.IN_PROGRESS:
                                task.status = TaskStatus.PENDING
                            
                            # Use only the latest classification description (emails are linked via thread, no need to duplicate)
                            all_emails_in_thread = email.thread.messages.filter(
                                account=email.account
                            )
                            thread_count = all_emails_in_thread.count()
                            
                            # Build description with just the latest classification
                            other_task_ids = list(other_tasks.values_list('pk', flat=True))
                            merged_description = classification['task_description']
                            
                            # Add consolidation note if needed
                            if other_task_ids:
                                if thread_count > 1:
                                    merged_description += f"\n\n[Part of conversation thread with {thread_count} message(s). Consolidated from {len(other_task_ids)} previous task(s).]"
                                else:
                                    merged_description += f"\n\n[Consolidated from {len(other_task_ids)} previous task(s).]"
                            
                            task.description = merged_description[:5000]
                            task.email_message = email  # Update to latest email
                            task.save()
                            
                            # Delete other tasks
                            if other_task_ids:
                                deleted_count = other_tasks.count()
                                other_tasks.delete()
                                logger.info(f"[Process Email] Post-creation consolidation: Deleted {deleted_count} other task(s) (IDs: {other_task_ids})")

            # Apply labels to email if any matched
            for label in labels_to_apply:
                EmailLabel.objects.get_or_create(
                    email_message=email, label=label
                )
                # Trigger label actions
                trigger_label_actions.delay(label.id, email.id)
            
            # Automatically mark email as read after processing
            # This is done by default for all processed emails
            if email.account.is_connected:
                try:
                    from mail.services import GmailService
                    gmail_service = GmailService()
                    service = gmail_service._get_service(email.account)
                    service.users().messages().modify(
                        userId="me",
                        id=email.external_message_id,
                        body={"removeLabelIds": ["UNREAD"]}
                    ).execute()
                    logger.debug(f"Email {email_message_id} automatically marked as read")
                except Exception as e:
                    # Log but don't fail - marking as read is not critical
                    logger.warning(f"Could not automatically mark email {email_message_id} as read: {e}")
    except Exception as e:
        logger.error(
            f"Error creating task for email {email_message_id}: {e}", 
            exc_info=True
        )
        raise  # Re-raise so Celery can track the failure


@shared_task
def trigger_label_actions(label_id: int, email_message_id: int, triggered_by_action: bool = False):
    """
    Trigger actions for a label using AI-driven orchestration.
    
    Args:
        label_id: The label to trigger actions for
        email_message_id: The email message
        triggered_by_action: If True, this was triggered by an add_label action (prevents circular loops)
    """
    client = OpenAIClient()
    try:
        label = Label.objects.prefetch_related("actions").get(pk=label_id)
        email = EmailMessage.objects.select_related("account").get(pk=email_message_id)
    except (Label.DoesNotExist, EmailMessage.DoesNotExist):
        logger.warning(
            f"Label {label_id} or email {email_message_id} not found"
        )
        return
    
    # Check if label is active
    if not label.is_active:
        return
    
    # Prevent circular triggering: if this was triggered by an action adding a label,
    # check if this label was already processed for this email
    if triggered_by_action:
        # Check if this label was already applied to this email (to prevent loops)
        existing_email_label = EmailLabel.objects.filter(
            email_message=email,
            label=label
        ).first()
        
        if not existing_email_label:
            logger.warning(
                f"Label {label.name} triggered by action but not yet applied to email {email_message_id}, "
                f"skipping to prevent circular trigger"
            )
            return
    
    # AI-driven orchestration
    from automation.mcp_orchestrator import orchestrate_label_actions
    result = orchestrate_label_actions(label, email, client)
    
    if not result.get("success"):
        logger.error(
            f"AI orchestration failed for label {label.name} (email {email_message_id}): "
            f"{result.get('message', 'unknown error')}"
        )


def run_draft_action(email: EmailMessage, action: Action, client: OpenAIClient):
    instructions = action.instructions or action.name
    context = f"Subject: {email.subject}\nFrom: {email.from_address}\nBody:\n{email.body_html}"
    html_body = client.draft_reply(instructions, context)
    Draft.objects.create(
        account=email.account,
        email_message=email,
        subject=f"Re: {email.subject or 'your message'}",
        body_html=html_body,
    )
