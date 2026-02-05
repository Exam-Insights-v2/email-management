from celery import shared_task
from django.db import transaction
from django.utils import timezone
from datetime import datetime
import logging

from automation.models import Action, EmailLabel, Label, LabelAction
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

    with transaction.atomic():
        # ALWAYS create task with AI-generated data
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

        # Apply labels from AI response
        labels_to_apply = []
        for label_name in classification.get("labels", []):
            # Find matching label (case-insensitive)
            label = next(
                (
                    l
                    for l in available_labels
                    if l.name.lower() == label_name.lower()
                ),
                None,
            )
            if label:
                labels_to_apply.append(label)
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
def trigger_label_actions(label_id: int, email_message_id: int):
    """
    Trigger actions for a label. Supports both MCP (dynamic) and sequential (legacy) modes.
    """
    client = OpenAIClient()
    try:
        label = Label.objects.get(pk=label_id)
        email = EmailMessage.objects.select_related("account").get(pk=email_message_id)
    except (Label.DoesNotExist, EmailMessage.DoesNotExist):
        logger.warning(
            f"Label {label_id} or email {email_message_id} not found"
        )
        return

    # Check if label uses MCP orchestration
    if label.use_mcp:
        # New MCP-based dynamic orchestration
        from automation.mcp_orchestrator import orchestrate_label_actions
        result = orchestrate_label_actions(label, email, client)
        logger.info(
            f"MCP orchestration for label {label.name} (email {email_message_id}): "
            f"{result.get('message', 'completed')}"
        )
    else:
        # Legacy sequential execution (backward compatible)
        from automation.action_executors import execute_action
        
        label_actions = LabelAction.objects.filter(
            label=label
        ).select_related("action").order_by("order")
        
        execution_context = {}  # Context passed between actions
        
        for label_action in label_actions:
            action = label_action.action
            logger.info(
                f"Executing action '{action.name}' ({action.function}) "
                f"for email {email_message_id} in legacy mode"
            )
            
            # Use the same action executor as MCP mode for consistency
            result = execute_action(action, email, client, execution_context)
            
            # Update context for next actions
            if result.get("success") and result.get("data"):
                execution_context.update(result["data"])
            
            logger.info(
                f"Action '{action.name}' result: {result.get('message', 'completed')}"
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
