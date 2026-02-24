from celery import shared_task
from django.utils import timezone
from datetime import datetime
import logging

from automation.models import Action, EmailLabel, Label
from automation.services import OpenAIClient
from automation.task_from_email import ensure_task_for_email
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
    classification["due_at"] = due_at

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

    try:
        task = ensure_task_for_email(email, classification)
        logger.info(
            f"[Process Email] Task #{task.pk} for email #{email_message_id}: '{task.title}' (priority: {task.priority})"
        )

        for label in labels_to_apply:
            EmailLabel.objects.get_or_create(
                email_message=email, label=label
            )
            trigger_label_actions.delay(label.id, email.id)

        if not Draft.objects.filter(account=email.account, email_message=email).exists():
            instructions = "Draft a brief, professional reply to this email. Be concise and helpful."
            if email.account.writing_style:
                instructions = f"{instructions}\n\nWriting style: {email.account.writing_style}"
            email_context = (
                f"Subject: {email.subject}\nFrom: {email.from_address}\nBody:\n{email.body_html or ''}"
            )
            try:
                html_body = client.draft_reply(instructions, email_context)
            except Exception as e:
                logger.warning(f"Email {email_message_id}: AI draft_reply failed, using empty body: {e}")
                html_body = ""
            if email.account.signature_html:
                separator = (
                    '<div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #e5e7eb;"></div>'
                )
                html_body = html_body + separator + email.account.signature_html
            Draft.objects.create(
                account=email.account,
                email_message=email,
                to_addresses=[email.from_address],
                subject=f"Re: {email.subject or 'No subject'}",
                body_html=html_body or "",
            )
            logger.debug(f"Email {email_message_id}: created AI reply draft")

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
                logger.warning(f"Could not automatically mark email {email_message_id} as read: {e}")
    except Exception as e:
        logger.error(
            f"Error creating task for email {email_message_id}: {e}",
            exc_info=True
        )
        raise

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
