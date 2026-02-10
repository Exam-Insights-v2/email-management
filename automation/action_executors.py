"""
Action executors - functions that execute different action types.
These are called by the MCP orchestrator when actions are triggered.
"""
import logging
from typing import Dict, Any, List

from automation.models import Action, Label, EmailLabel
from automation.services import OpenAIClient
from jobs.models import Task, TaskStatus
from mail.models import Draft, EmailMessage
from mail.services import GmailService

logger = logging.getLogger(__name__)


def execute_action(
    action: Action,
    email: EmailMessage,
    client: OpenAIClient,
    context: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Execute an action based on its function type.
    
    Args:
        action: The Action to execute
        email: The EmailMessage context
        client: OpenAI client for AI operations
        context: Additional context from previous actions
        
    Returns:
        Dict with execution result: {"success": bool, "message": str, "data": Any}
    """
    context = context or {}
    function = action.function
    
    try:
        if function == "draft_reply":
            return execute_draft_reply(action, email, client, context)
        elif function == "send_reply":
            return execute_send_reply(action, email, client, context)
        elif function == "create_task":
            return execute_create_task(action, email, client, context)
        elif function == "notify":
            return execute_notify(action, email, client, context)
        elif function == "schedule":
            return execute_schedule(action, email, client, context)
        elif function == "forward_email":
            return execute_forward_email(action, email, client, context)
        elif function == "archive_email":
            return execute_archive_email(action, email, client, context)
        elif function == "mark_as_spam":
            return execute_mark_as_spam(action, email, client, context)
        elif function == "delete_email":
            return execute_delete_email(action, email, client, context)
        elif function == "add_label":
            return execute_add_label(action, email, client, context)
        elif function == "remove_label":
            return execute_remove_label(action, email, client, context)
        else:
            logger.warning(f"Unknown action function: {function}")
            return {
                "success": False,
                "message": f"Unknown action function: {function}",
                "data": None
            }
    except Exception as e:
        logger.error(f"Error executing action {action.name}: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Error: {str(e)}",
            "data": None
        }


def execute_draft_reply(
    action: Action,
    email: EmailMessage,
    client: OpenAIClient,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """Create a draft email reply"""
    instructions = action.instructions or action.name
    email_context = f"Subject: {email.subject}\nFrom: {email.from_address}\nBody:\n{email.body_html}"
    
    # Include account writing style if available
    if email.account.writing_style:
        instructions = f"{instructions}\n\nWriting style: {email.account.writing_style}"
    
    html_body = client.draft_reply(instructions, email_context)
    
    draft = Draft.objects.create(
        account=email.account,
        email_message=email,
        subject=f"Re: {email.subject or 'your message'}",
        body_html=html_body,
    )
    
    return {
        "success": True,
        "message": f"Draft reply created (ID: {draft.pk})",
        "data": {"draft_id": draft.pk}
    }


def execute_create_task(
    action: Action,
    email: EmailMessage,
    client: OpenAIClient,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """Create a task from the email"""
    # Use instructions to guide task creation, or use defaults
    instructions = action.instructions or "Create a task for this email"
    
    # Check if task already exists for this email (with atomic operation to prevent race conditions)
    from django.db import transaction
    
    with transaction.atomic():
        # Use select_for_update to prevent race conditions
        existing_task = Task.objects.select_for_update().filter(
            account=email.account,
            email_message=email
        ).first()
        
        if existing_task:
            return {
                "success": True,
                "message": f"Task already exists (ID: {existing_task.pk})",
                "data": {"task_id": existing_task.pk, "existing": True}
            }
    
        # Extract task details from instructions or use email subject
        title = email.subject or f"Task for email from {email.from_address}"
        description = f"Email from {email.from_name or email.from_address}: {email.subject}"
        
        # Parse priority from instructions if mentioned
        priority = 1
        if "priority" in instructions.lower() or "urgent" in instructions.lower():
            priority = 5
        elif "high" in instructions.lower():
            priority = 4
        elif "medium" in instructions.lower():
            priority = 3
        
        task = Task.objects.create(
            account=email.account,
            email_message=email,
            thread=email.thread,
            title=title[:255],
            description=description,
            priority=priority,
            status=TaskStatus.PENDING,
        )
        
        return {
            "success": True,
            "message": f"Task created (ID: {task.pk})",
            "data": {"task_id": task.pk, "title": task.title}
        }


def execute_notify(
    action: Action,
    email: EmailMessage,
    client: OpenAIClient,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """Send a notification (placeholder - implement based on your notification system)"""
    # TODO: Implement actual notification system
    # For now, just log it
    logger.info(
        f"Notification action '{action.name}' triggered for email {email.pk}: "
        f"{action.instructions}"
    )
    
    return {
        "success": True,
        "message": "Notification logged (implementation pending)",
        "data": {"action": action.name}
    }


def execute_schedule(
    action: Action,
    email: EmailMessage,
    client: OpenAIClient,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """Schedule a follow-up (placeholder - implement based on your scheduling system)"""
    # TODO: Implement actual scheduling system
    logger.info(
        f"Schedule action '{action.name}' triggered for email {email.pk}: "
        f"{action.instructions}"
    )
    
    return {
        "success": True,
        "message": "Schedule logged (implementation pending)",
        "data": {"action": action.name}
    }


def execute_send_reply(
    action: Action,
    email: EmailMessage,
    client: OpenAIClient,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """Send an immediate email reply (not just a draft)"""
    if not email.account.is_connected:
        return {
            "success": False,
            "message": "Account is not connected to Gmail",
            "data": None
        }
    
    instructions = action.instructions or action.name
    email_context = f"Subject: {email.subject}\nFrom: {email.from_address}\nBody:\n{email.body_html}"
    
    # Include account writing style if available
    if email.account.writing_style:
        instructions = f"{instructions}\n\nWriting style: {email.account.writing_style}"
    
    # Generate reply body using AI
    html_body = client.draft_reply(instructions, email_context)
    
    # Send immediately via Gmail API
    try:
        gmail_service = GmailService()
        result = gmail_service.send_message(
            account=email.account,
            to_addresses=[email.from_address],
            subject=f"Re: {email.subject or 'your message'}",
            body_html=html_body,
            reply_to_message_id=email.external_message_id,
        )
        
        return {
            "success": True,
            "message": f"Reply sent successfully (Message ID: {result.get('id')})",
            "data": {"message_id": result.get("id"), "thread_id": result.get("threadId")}
        }
    except Exception as e:
        logger.error(f"Error sending reply: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Error sending reply: {str(e)}",
            "data": None
        }


def execute_forward_email(
    action: Action,
    email: EmailMessage,
    client: OpenAIClient,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """Forward email to specified recipients"""
    if not email.account.is_connected:
        return {
            "success": False,
            "message": "Account is not connected to Gmail",
            "data": None
        }
    
    # Parse instructions for forward recipients
    # Format: "to: email1@example.com, email2@example.com" or just email addresses
    instructions = action.instructions or ""
    to_addresses = []
    
    # Try to extract email addresses from instructions
    if "to:" in instructions.lower():
        to_part = instructions.lower().split("to:")[1].strip()
        to_addresses = [addr.strip() for addr in to_part.split(",")]
    else:
        # Assume instructions contain email addresses
        to_addresses = [addr.strip() for addr in instructions.split(",") if "@" in addr]
    
    if not to_addresses:
        return {
            "success": False,
            "message": "No recipient email addresses found in action instructions",
            "data": None
        }
    
    try:
        gmail_service = GmailService()
        result = gmail_service.forward_message(
            account=email.account,
            external_message_id=email.external_message_id,
            to_addresses=to_addresses,
        )
        
        return {
            "success": True,
            "message": f"Email forwarded successfully (Message ID: {result.get('id')})",
            "data": {"message_id": result.get("id"), "to_addresses": to_addresses}
        }
    except Exception as e:
        logger.error(f"Error forwarding email: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Error forwarding email: {str(e)}",
            "data": None
        }


def execute_archive_email(
    action: Action,
    email: EmailMessage,
    client: OpenAIClient,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """Archive email (remove from inbox)"""
    if not email.account.is_connected:
        return {
            "success": False,
            "message": "Account is not connected to Gmail",
            "data": None
        }
    
    try:
        gmail_service = GmailService()
        gmail_service.archive_message(email.account, email.external_message_id)
        
        return {
            "success": True,
            "message": "Email archived successfully",
            "data": {"email_id": email.pk}
        }
    except Exception as e:
        logger.error(f"Error archiving email: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Error archiving email: {str(e)}",
            "data": None
        }


def execute_mark_as_spam(
    action: Action,
    email: EmailMessage,
    client: OpenAIClient,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """Mark email as spam"""
    if not email.account.is_connected:
        return {
            "success": False,
            "message": "Account is not connected to Gmail",
            "data": None
        }
    
    try:
        gmail_service = GmailService()
        gmail_service.mark_as_spam(email.account, email.external_message_id)
        
        return {
            "success": True,
            "message": "Email marked as spam successfully",
            "data": {"email_id": email.pk}
        }
    except Exception as e:
        logger.error(f"Error marking email as spam: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Error marking email as spam: {str(e)}",
            "data": None
        }


def execute_delete_email(
    action: Action,
    email: EmailMessage,
    client: OpenAIClient,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """Delete email (trash in Gmail)"""
    if not email.account.is_connected:
        return {
            "success": False,
            "message": "Account is not connected to Gmail",
            "data": None
        }
    
    try:
        gmail_service = GmailService()
        gmail_service.delete_message(email.account, email.external_message_id)
        
        # Also delete from database
        email.delete()
        
        return {
            "success": True,
            "message": "Email deleted successfully",
            "data": {"email_id": email.pk}
        }
    except Exception as e:
        logger.error(f"Error deleting email: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Error deleting email: {str(e)}",
            "data": None
        }


def execute_add_label(
    action: Action,
    email: EmailMessage,
    client: OpenAIClient,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """Add a label to the email (internal EmailLabel system)"""
    # Parse instructions for label name
    instructions = action.instructions or ""
    label_name = instructions.strip()
    
    if not label_name:
        return {
            "success": False,
            "message": "No label name specified in action instructions",
            "data": None
        }
    
    # Find label by name (case-insensitive)
    label = Label.objects.filter(
        account=email.account,
        name__iexact=label_name
    ).first()
    
    if not label:
        return {
            "success": False,
            "message": f"Label '{label_name}' not found for this account",
            "data": None
        }
    
    # Add label to email
    email_label, created = EmailLabel.objects.get_or_create(
        email_message=email,
        label=label
    )
    
    if created:
        # Trigger actions for the newly added label
        # Pass triggered_by_action=True to prevent circular loops
        from automation.tasks import trigger_label_actions
        trigger_label_actions.delay(label.id, email.id, triggered_by_action=True)
    
    return {
        "success": True,
        "message": f"Label '{label.name}' added to email",
        "data": {"label_id": label.pk, "label_name": label.name, "was_new": created}
    }


def execute_remove_label(
    action: Action,
    email: EmailMessage,
    client: OpenAIClient,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """Remove a label from the email (internal EmailLabel system)"""
    # Parse instructions for label name
    instructions = action.instructions or ""
    label_name = instructions.strip()
    
    if not label_name:
        return {
            "success": False,
            "message": "No label name specified in action instructions",
            "data": None
        }
    
    # Find label by name (case-insensitive)
    label = Label.objects.filter(
        account=email.account,
        name__iexact=label_name
    ).first()
    
    if not label:
        return {
            "success": False,
            "message": f"Label '{label_name}' not found for this account",
            "data": None
        }
    
    # Remove label from email
    removed = EmailLabel.objects.filter(
        email_message=email,
        label=label
    ).delete()
    
    return {
        "success": True,
        "message": f"Label '{label.name}' removed from email",
        "data": {"label_id": label.pk, "label_name": label.name, "removed": removed[0] > 0}
    }
