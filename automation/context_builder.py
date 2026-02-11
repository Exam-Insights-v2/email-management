"""
Context builder for AI action orchestration.
Builds the context that will be provided to the AI for decision-making.
"""
from typing import Dict, List
from automation.models import Label, Action
from mail.models import EmailMessage


def build_action_context(
    label: Label,
    email: EmailMessage,
    available_actions: List[Action],
    label_actions: List[Action] = None
) -> Dict:
    """
    Build comprehensive context for AI action orchestration.
    
    Args:
        label: The label that was applied
        email: The email message
        available_actions: Actions from ALL labels currently applied to the email (AI can ONLY choose from these)
        label_actions: Actions linked to the specific label that triggered this orchestration (for context)
    
    Returns:
        Dict with all context needed for AI to make action decisions
    """
    label_actions = label_actions or []
    
    # Get all labels currently applied to this email (for context)
    from automation.models import EmailLabel
    email_labels = EmailLabel.objects.filter(
        email_message=email
    ).select_related('label')
    
    applied_label_names = [el.label.name for el in email_labels]
    
    # Get other active labels for the account (for context)
    other_labels = Label.objects.filter(
        account=email.account,
        is_active=True
    ).exclude(pk=label.pk).order_by("-priority", "name")[:5]  # Limit to top 5
    
    # Format other labels for context
    other_labels_text = format_other_labels(other_labels)
    
    # Format ALL available actions as tool descriptions
    actions_text = format_actions(available_actions)
    
    # Format label-linked actions separately (for context - these are from the triggering label)
    label_actions_text = format_actions(label_actions) if label_actions else "None"
    
    # Build email context
    email_context = {
        "subject": email.subject or "(No subject)",
        "from_address": email.from_address,
        "from_name": email.from_name or email.from_address,
        "to_addresses": email.to_addresses,
        "body_preview": (email.body_html or "")[:1000],  # Limit length
    }
    
    # Account settings
    account_settings = {
        "writing_style": email.account.writing_style or "",
        "signature": email.account.signature_html or "",
    }
    
    return {
        "label_name": label.name,
        "label_prompt": label.prompt or "",
        "label_instructions": label.instructions or "",
        "label_priority": label.priority,
        "applied_labels": applied_label_names,
        "other_labels": other_labels_text,
        "all_actions": actions_text,
        "label_actions": label_actions_text,
        "email": email_context,
        "account_settings": account_settings,
    }


def format_other_labels(labels) -> str:
    """Format other active labels for context"""
    if not labels:
        return "No other active labels for context."
    
    lines = []
    for label in labels:
        lines.append(f"**{label.name}** (Priority: {label.priority})")
        if label.prompt:
            lines.append(f"  When: {label.prompt}")
        if label.instructions:
            lines.append(f"  Instructions: {label.instructions}")
        lines.append("")
    
    return "\n".join(lines)


def format_actions(actions: List[Action]) -> str:
    """Format available actions as tool descriptions for AI"""
    if not actions:
        return "No actions available."
    
    lines = []
    for action in actions:
        tool_name = action.effective_tool_name
        description = action.tool_description or action.instructions or action.name
        lines.append(f"- **{tool_name}**: {description}")
        if action.instructions:
            lines.append(f"  Instructions: {action.instructions}")
    
    return "\n".join(lines)


def build_ai_system_prompt(context: Dict) -> str:
    """Build the system prompt for AI action orchestration"""
    return f"""You are an email action orchestrator for a line-marking company in Australia.

Your role is to analyse emails and intelligently decide which actions to execute, and in what order, based on:
1. The email content and context (PRIMARY - understand what the email actually needs)
2. The label's business rules and instructions (GUIDANCE - use as context, not constraints)
3. Other relevant labels for context
4. Account settings

CURRENT LABEL: {context['label_name']} (Priority: {context['label_priority']})

LABELS APPLIED TO THIS EMAIL: {', '.join(context['applied_labels']) if context['applied_labels'] else 'None'}

WHEN THIS LABEL APPLIES:
{context['label_prompt'] if context['label_prompt'] else 'No specific criteria defined'}

WHAT TO DO (Business Logic - Use as Guidance):
{context['label_instructions'] if context['label_instructions'] else 'No specific instructions defined'}

OTHER ACTIVE LABELS (for context):
{context['other_labels']}

ACTIONS FROM CURRENT LABEL (for reference):
{context['label_actions']}

AVAILABLE ACTIONS (You can ONLY choose from these - they come from labels applied to this email):
{context['all_actions'] if context['all_actions'] else 'NO ACTIONS AVAILABLE - No labels with linked actions are applied to this email.'}

ACCOUNT SETTINGS:
Writing Style: {context['account_settings']['writing_style'] if context['account_settings']['writing_style'] else 'Not specified'}

CRITICAL INSTRUCTIONS:
1. **You can ONLY choose from the available actions listed above** - these are actions linked to labels currently applied to this email
2. **If no actions are available**, it means no labels with linked actions are applied - return an empty actions array
3. **Analyse the email content first** - understand what the email actually needs (job inquiry? spam? scheduling request? needs reply?)
4. **Use label instructions as guidance** - be flexible and intelligent in choosing which available actions to execute
5. **Email reply rules** - choose the right action based on reply type:
   - For custom business communications (quotes, job inquiries, complaints, scheduling, etc.) → ALWAYS use draft_reply (user must review)
   - For automated/templated responses (confirmations, receipts, standard acknowledgements) → can use send_reply
   - When in doubt → use draft_reply (safer, allows user review)
   - send_reply should ONLY be used for standardised, templated responses that don't require customisation
6. **Make smart decisions** based on email content and available actions:
   - Email mentions scheduling/meeting → use schedule action (if available)
   - Email is clearly spam → use mark_as_spam or delete_email (if available)
   - Email is job inquiry → use create_job (if available)
   - Email mentions specific dates → extract and schedule (if available)
7. **Consider time of day, urgency, and other contextual factors**
8. **Skip unnecessary actions** - only execute what makes sense from the available actions
9. **Determine optimal execution order** - some actions may depend on others
10. **Use Australian English spelling**
11. **Be context-aware and intelligent** - the goal is to handle emails appropriately using the actions available from the applied labels

Return a JSON object with your action plan:
{{
  "reasoning": "Brief explanation of your analysis and decisions",
  "actions": [
    {{
      "tool_name": "action_function_name",
      "reason": "Why this action should run"
    }}
  ]
}}

Execute actions in the order specified in your plan."""


def build_ai_user_prompt(context: Dict) -> str:
    """Build the user prompt with email details"""
    email = context['email']
    return f"""Email to process:

Subject: {email['subject']}
From: {email['from_name']} ({email['from_address']})
To: {', '.join(email['to_addresses']) if email['to_addresses'] else 'N/A'}

Body:
{email['body_preview']}

Analyse this email and determine which actions to execute and in what order."""
