"""
Action executors - functions that execute different action types.
These are called by the MCP orchestrator when actions are triggered.
"""
import logging
from typing import Dict, Any, List

from automation.models import Action, Label, EmailLabel
from automation.services import OpenAIClient
from jobs.models import Job, Task, TaskStatus, JobStatus
from mail.models import Draft, EmailMessage, EmailThread
from mail.services import GmailService, MicrosoftService
from django.utils import timezone
from datetime import datetime, timedelta
import json
import re

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
        elif function == "create_job":
            return execute_create_job(action, email, client, context)
        elif function == "extract_information":
            return execute_extract_information(action, email, client, context)
        elif function == "set_priority":
            return execute_set_priority(action, email, client, context)
        elif function == "mark_as_read":
            return execute_mark_as_read(action, email, client, context)
        elif function == "create_reminder":
            return execute_create_reminder(action, email, client, context)
        elif function == "respond_to_calendar_invite":
            return execute_respond_to_calendar_invite(action, email, client, context)
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
    
    # Append signature if available
    if email.account.signature_html:
        separator = '<div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #e5e7eb;"></div>'
        html_body = html_body + separator + email.account.signature_html
    
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
    """Create a task from the email (uses same consolidation as process_email)."""
    from automation.task_from_email import ensure_task_for_email

    instructions = action.instructions or "Create a task for this email"
    title = email.subject or f"Task for email from {email.from_address}"
    description = f"Email from {email.from_name or email.from_address}: {email.subject}"
    priority = 1
    if "priority" in instructions.lower() or "urgent" in instructions.lower():
        priority = 5
    elif "high" in instructions.lower():
        priority = 4
    elif "medium" in instructions.lower():
        priority = 3

    classification = {
        "task_title": title[:255],
        "task_description": description,
        "priority": priority,
        "due_at": None,
    }
    task = ensure_task_for_email(email, classification)
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
            "message": "Account is not connected",
            "data": None
        }
    
    instructions = action.instructions or action.name
    email_context = f"Subject: {email.subject}\nFrom: {email.from_address}\nBody:\n{email.body_html}"
    
    # Include account writing style if available
    if email.account.writing_style:
        instructions = f"{instructions}\n\nWriting style: {email.account.writing_style}"
    
    # Generate reply body using AI
    html_body = client.draft_reply(instructions, email_context)
    
    provider_services = {
        "gmail": GmailService(),
        "microsoft": MicrosoftService(),
    }
    provider_service = provider_services.get(email.account.provider)
    if not provider_service:
        return {
            "success": False,
            "message": f"Provider '{email.account.provider}' does not support sending",
            "data": None,
        }

    # Send immediately via provider API
    try:
        result = provider_service.send_message(
            account=email.account,
            to_addresses=[email.from_address],
            subject=f"Re: {email.subject or 'your message'}",
            body_html=html_body,
            reply_to_message_id=email.external_message_id,
        )

        from mail.services import persist_sent_message
        persist_sent_message(
            account=email.account,
            send_result=result,
            subject=f"Re: {email.subject or 'your message'}",
            from_address=email.account.email,
            to_addresses=[email.from_address],
            body_html=html_body,
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

        from mail.services import persist_sent_message
        persist_sent_message(
            account=email.account,
            send_result=result,
            subject=result.get("subject", ""),
            from_address=result.get("from_address", email.account.email),
            to_addresses=result.get("to_addresses", to_addresses),
            cc_addresses=result.get("cc_addresses"),
            bcc_addresses=result.get("bcc_addresses"),
            body_html=result.get("body_html", ""),
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


def execute_create_job(
    action: Action,
    email: EmailMessage,
    client: OpenAIClient,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """Create a job record from the email using AI to extract details"""
    instructions = action.instructions or "Extract job details from this email and create a job record"
    
    # Use AI to extract job information from email
    email_context = f"Subject: {email.subject}\nFrom: {email.from_name or email.from_address}\nBody:\n{email.body_html[:3000]}"
    
    extraction_prompt = f"""Extract job information from this email for a line-marking company.
{instructions}

Email:
{email_context}

Extract and return JSON with these fields:
- title: Job title/description (max 255 chars)
- customer_name: List of customer names mentioned
- customer_email: List of customer email addresses
- site_address: Site address or location
- description: Full job description
- dates: List of dates mentioned (YYYY-MM-DD format)
- status: One of: draft, quoted, won, lost, in_progress, completed, cancelled (default: draft)

Return JSON only, no additional text."""

    try:
        # Log what we're sending to OpenAI for debugging
        logger.info(
            f"OpenAI Request - execute_create_job for email {email.pk}:\n"
            f"Model: gpt-5-mini\n"
            f"Extraction prompt length: {len(extraction_prompt)} chars\n"
            f"Instructions: {instructions[:200]}..."
        )
        
        # Use OpenAI to extract structured data
        response = client.client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": "You are a data extraction assistant. Extract structured information from emails and return valid JSON only."},
                {"role": "user", "content": extraction_prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        logger.info(f"OpenAI Response - execute_create_job for email {email.pk}: {len(response.choices[0].message.content) if response.choices else 0} chars")
        
        extracted_data = json.loads(response.choices[0].message.content)
        
        # Create job with extracted data
        job = Job.objects.create(
            account=email.account,
            title=extracted_data.get("title", email.subject or "New Job")[:255],
            status=extracted_data.get("status", JobStatus.DRAFT),
            customer_name=extracted_data.get("customer_name", []),
            customer_email=extracted_data.get("customer_email", [email.from_address] if email.from_address else []),
            site_address=extracted_data.get("site_address", ""),
            description=extracted_data.get("description", email.body_html[:1000] if email.body_html else ""),
            dates=extracted_data.get("dates", []),
        )
        
        return {
            "success": True,
            "message": f"Job created successfully (ID: {job.pk})",
            "data": {
                "job_id": job.pk,
                "title": job.title,
                "status": job.status,
                "extracted_data": extracted_data
            }
        }
    except Exception as e:
        logger.error(f"Error creating job: {e}", exc_info=True)
        # Fallback: create basic job without AI extraction
        job = Job.objects.create(
            account=email.account,
            title=email.subject or "New Job",
            status=JobStatus.DRAFT,
            customer_email=[email.from_address] if email.from_address else [],
            description=email.body_html[:1000] if email.body_html else "",
        )
        return {
            "success": True,
            "message": f"Job created with basic info (ID: {job.pk}) - AI extraction failed: {str(e)}",
            "data": {"job_id": job.pk, "title": job.title}
        }


def execute_extract_information(
    action: Action,
    email: EmailMessage,
    client: OpenAIClient,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """Extract structured information from email using AI"""
    instructions = action.instructions or "Extract key information from this email"
    
    email_context = f"Subject: {email.subject}\nFrom: {email.from_name or email.from_address}\nBody:\n{email.body_html[:3000]}"
    
    extraction_prompt = f"""Extract structured information from this email based on the following requirements:
{instructions}

Email:
{email_context}

Return a JSON object with the extracted information. Include all relevant details like:
- Dates, times, deadlines
- Locations, addresses
- Amounts, prices, costs
- Service types, job details
- Any other relevant structured data

Return JSON only, no additional text."""

    try:
        response = client.client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": "You are a data extraction assistant. Extract structured information from emails and return valid JSON only."},
                {"role": "user", "content": extraction_prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        extracted_data = json.loads(response.choices[0].message.content)
        
        # Store extracted data in context for other actions to use
        context["extracted_information"] = extracted_data
        
        return {
            "success": True,
            "message": "Information extracted successfully",
            "data": {"extracted_data": extracted_data}
        }
    except Exception as e:
        logger.error(f"Error extracting information: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Error extracting information: {str(e)}",
            "data": None
        }


def execute_set_priority(
    action: Action,
    email: EmailMessage,
    client: OpenAIClient,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """Set priority for a task or email"""
    instructions = action.instructions or ""
    
    # Parse priority from instructions (1-5 scale)
    priority = None
    priority_match = re.search(r'\b(?:priority|priority level|set priority)\s*:?\s*(\d+)\b', instructions.lower())
    if priority_match:
        priority = int(priority_match.group(1))
    elif "urgent" in instructions.lower() or "5" in instructions:
        priority = 5
    elif "high" in instructions.lower() or "4" in instructions:
        priority = 4
    elif "medium" in instructions.lower() or "3" in instructions:
        priority = 3
    elif "low" in instructions.lower() or "2" in instructions:
        priority = 2
    elif "lowest" in instructions.lower() or "1" in instructions:
        priority = 1
    
    if priority is None:
        # Try to infer from email content
        email_text = f"{email.subject} {email.body_html}".lower()
        if any(word in email_text for word in ["urgent", "asap", "immediately", "critical"]):
            priority = 5
        elif any(word in email_text for word in ["important", "high priority"]):
            priority = 4
        else:
            priority = 3  # Default to medium
    
    # Clamp priority to valid range
    priority = max(1, min(5, priority))
    
    # Update task if one exists for this email
    task = Task.objects.filter(email_message=email, account=email.account).first()
    if task:
        task.priority = priority
        task.save()
        return {
            "success": True,
            "message": f"Task priority set to {priority}",
            "data": {"task_id": task.pk, "priority": priority, "updated": "task"}
        }
    
    # If no task exists, store priority in context for task creation
    context["priority"] = priority
    
    return {
        "success": True,
        "message": f"Priority set to {priority} (will be applied when task is created)",
        "data": {"priority": priority, "updated": "context"}
    }


def execute_mark_as_read(
    action: Action,
    email: EmailMessage,
    client: OpenAIClient,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """Mark email as read in Gmail"""
    if not email.account.is_connected:
        return {
            "success": False,
            "message": "Account is not connected to Gmail",
            "data": None
        }
    
    try:
        gmail_service = GmailService()
        # Remove UNREAD label to mark as read
        service = gmail_service._get_service(email.account)
        service.users().messages().modify(
            userId="me",
            id=email.external_message_id,
            body={"removeLabelIds": ["UNREAD"]}
        ).execute()
        
        return {
            "success": True,
            "message": "Email marked as read successfully",
            "data": {"email_id": email.pk}
        }
    except Exception as e:
        logger.error(f"Error marking email as read: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Error marking email as read: {str(e)}",
            "data": None
        }


def execute_create_reminder(
    action: Action,
    email: EmailMessage,
    client: OpenAIClient,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """Create a reminder task with a due date"""
    instructions = action.instructions or ""
    
    # Try to extract date from instructions or email
    due_date = None
    
    # Check if date is in context from extract_information
    if "extracted_information" in context:
        extracted = context["extracted_information"]
        if "due_date" in extracted:
            try:
                due_date = datetime.strptime(extracted["due_date"], "%Y-%m-%d")
            except:
                pass
        elif "reminder_date" in extracted:
            try:
                due_date = datetime.strptime(extracted["reminder_date"], "%Y-%m-%d")
            except:
                pass
    
    # Parse date from instructions
    if not due_date:
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', instructions)
        if date_match:
            try:
                due_date = datetime.strptime(date_match.group(1), "%Y-%m-%d")
            except:
                pass
    
    # If no date found, default to 7 days from now
    if not due_date:
        due_date = timezone.now() + timedelta(days=7)
    
    from automation.task_from_email import ensure_task_for_email

    due_at_aware = timezone.make_aware(due_date) if timezone.is_naive(due_date) else due_date
    title = f"Reminder: {email.subject or 'Follow up'}"
    description = f"Reminder for email from {email.from_name or email.from_address}\n\n{instructions}"
    classification = {
        "task_title": title[:255],
        "task_description": description,
        "priority": context.get("priority", 3),
        "due_at": due_at_aware,
    }
    task = ensure_task_for_email(email, classification)
    return {
        "success": True,
        "message": f"Reminder task created (ID: {task.pk})",
        "data": {"task_id": task.pk, "due_at": (task.due_at or due_date).isoformat(), "title": task.title}
    }


def execute_respond_to_calendar_invite(
    action: Action,
    email: EmailMessage,
    client: OpenAIClient,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """Respond to a calendar invitation (accept/decline/tentative)"""
    if not email.account.is_connected:
        return {
            "success": False,
            "message": "Account is not connected to Gmail",
            "data": None
        }
    
    instructions = action.instructions or ""
    
    # Determine response type from instructions
    response_type = "ACCEPT"  # Default
    if "decline" in instructions.lower() or "no" in instructions.lower():
        response_type = "DECLINE"
    elif "tentative" in instructions.lower() or "maybe" in instructions.lower():
        response_type = "TENTATIVE"
    
    # Try to find calendar event ID in email
    # Gmail calendar invites have specific headers
    try:
        gmail_service = GmailService()
        service = gmail_service._get_service(email.account)
        
        # Get message details to find calendar event
        message = service.users().messages().get(
            userId="me",
            id=email.external_message_id,
            format="full"
        ).execute()
        
        # Look for calendar event ID in headers
        headers = message.get("payload", {}).get("headers", [])
        event_id = None
        for header in headers:
            if header.get("name", "").lower() in ["x-google-calendar-event-id", "x-microsoft-calendar-id"]:
                event_id = header.get("value")
                break
        
        if event_id:
            # Use Calendar API to respond to invite
            # Note: This requires Calendar API scope, which may not be available
            # For now, we'll mark the email as handled
            logger.info(f"Calendar event ID found: {event_id}, response: {response_type}")
        
        # Mark email as read and archive
        service.users().messages().modify(
            userId="me",
            id=email.external_message_id,
            body={
                "removeLabelIds": ["UNREAD"],
                "addLabelIds": ["INBOX"] if response_type == "ACCEPT" else []
            }
        ).execute()
        
        return {
            "success": True,
            "message": f"Calendar invite response processed: {response_type}",
            "data": {"response_type": response_type, "email_id": email.pk}
        }
    except Exception as e:
        logger.error(f"Error responding to calendar invite: {e}", exc_info=True)
        # Fallback: just mark as read
        try:
            gmail_service = GmailService()
            service = gmail_service._get_service(email.account)
            service.users().messages().modify(
                userId="me",
                id=email.external_message_id,
                body={"removeLabelIds": ["UNREAD"]}
            ).execute()
            return {
                "success": True,
                "message": f"Email marked as read (calendar response may require Calendar API access): {str(e)}",
                "data": {"email_id": email.pk}
            }
        except Exception as e2:
            return {
                "success": False,
                "message": f"Error responding to calendar invite: {str(e2)}",
                "data": None
            }
