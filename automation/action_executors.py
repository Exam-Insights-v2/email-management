"""
Action executors - functions that execute different action types.
These are called by the MCP orchestrator when actions are triggered.
"""
import logging
from typing import Dict, Any

from automation.models import Action
from automation.services import OpenAIClient
from jobs.models import Task, TaskStatus
from mail.models import Draft, EmailMessage

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
        elif function == "create_task":
            return execute_create_task(action, email, client, context)
        elif function == "notify":
            return execute_notify(action, email, client, context)
        elif function == "schedule":
            return execute_schedule(action, email, client, context)
        elif function == "forward":
            return execute_forward(action, email, client, context)
        elif function == "archive":
            return execute_archive(action, email, client, context)
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
    
    # Check if task already exists for this email
    existing_task = Task.objects.filter(
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


def execute_forward(
    action: Action,
    email: EmailMessage,
    client: OpenAIClient,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """Forward email (placeholder - implement based on your email system)"""
    # TODO: Implement actual forwarding
    logger.info(
        f"Forward action '{action.name}' triggered for email {email.pk}: "
        f"{action.instructions}"
    )
    
    return {
        "success": True,
        "message": "Forward logged (implementation pending)",
        "data": {"action": action.name}
    }


def execute_archive(
    action: Action,
    email: EmailMessage,
    client: OpenAIClient,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """Archive email (placeholder - implement based on your email system)"""
    # TODO: Implement actual archiving
    logger.info(
        f"Archive action '{action.name}' triggered for email {email.pk}: "
        f"{action.instructions}"
    )
    
    return {
        "success": True,
        "message": "Archive logged (implementation pending)",
        "data": {"action": action.name}
    }
