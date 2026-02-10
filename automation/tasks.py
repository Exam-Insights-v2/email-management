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
    try:
        email = EmailMessage.objects.select_related("thread", "account").get(
            pk=email_message_id
        )
    except EmailMessage.DoesNotExist:
        logger.warning(f"Email message {email_message_id} not found")
        return

    # Get available labels for this account
    available_labels = list(Label.objects.filter(account=email.account))

    # SINGLE AI CALL - Get all classification data
    client = OpenAIClient()
    classification = client.classify_email(email, available_labels)

    logger.info(
        f"Classified email {email_message_id}: "
        f"title={classification['task_title']}, "
        f"priority={classification['priority']}, "
        f"labels={classification['labels']}"
    )

    # Parse due date if provided
    due_at = parse_due_date(classification.get("due_date"))

    # Apply labels from AI response first to validate
    labels_to_apply = []
    for label_name in classification.get("labels", []):
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
                f"Label '{label_name}' from AI classification not found in available labels. "
                f"Available: {[l.name for l in available_labels]}"
            )

    # Only create task if at least one valid label was matched
    if not labels_to_apply:
        logger.info(
            f"No valid labels matched for email {email_message_id}, skipping task creation"
        )
        return

    with transaction.atomic():
        # Create or update task with AI-generated data (only if labels matched)
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

        # Update task if it already existed
        if not created:
            task.title = classification["task_title"]
            task.description = classification["task_description"]
            task.priority = classification["priority"]
            if due_at:
                task.due_at = due_at
            task.save()

        # Apply labels to email
        for label in labels_to_apply:
            EmailLabel.objects.get_or_create(
                email_message=email, label=label
            )
            # Trigger label actions
            trigger_label_actions.delay(label.id, email.id)

        logger.info(
            f"Created/updated task {task.pk} for email {email_message_id} "
            f"with {len(labels_to_apply)} labels"
        )


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
        logger.info(f"Label {label.name} is inactive, skipping action execution")
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
    
    if result.get("success"):
        logger.info(
            f"AI orchestration for label {label.name} (email {email_message_id}): "
            f"{result.get('message', 'completed')}"
        )
    else:
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
