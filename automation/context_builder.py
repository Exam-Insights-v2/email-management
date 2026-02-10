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
        available_actions: ALL actions available for the account (AI can choose from any)
        label_actions: Actions linked to the label (preferred but not required)
    
    Returns:
        Dict with all context needed for AI to make action decisions
    """
    label_actions = label_actions or []
    
    # Get other active labels for the account (for context)
    other_labels = Label.objects.filter(
        account=email.account,
        is_active=True
    ).exclude(pk=label.pk).order_by("-priority", "name")[:5]  # Limit to top 5
    
    # Format other labels for context
    other_labels_text = format_other_labels(other_labels)
    
    # Format ALL available actions as tool descriptions
    actions_text = format_actions(available_actions)
    
    # Format label-linked actions separately (for preference context)
    label_actions_text = format_actions(label_actions) if label_actions else "None (AI can choose from all available actions)"
    
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

WHEN THIS LABEL APPLIES:
{context['label_prompt'] if context['label_prompt'] else 'No specific criteria defined'}

WHAT TO DO (Business Logic - Use as Guidance):
{context['label_instructions'] if context['label_instructions'] else 'No specific instructions defined'}

OTHER ACTIVE LABELS (for context):
{context['other_labels']}

LABEL-LINKED ACTIONS (Preferred but not required):
{context['label_actions']}

ALL AVAILABLE ACTIONS (You can choose from ANY of these):
{context['all_actions']}

ACCOUNT SETTINGS:
Writing Style: {context['account_settings']['writing_style'] if context['account_settings']['writing_style'] else 'Not specified'}

CRITICAL INSTRUCTIONS:
1. **You have access to ALL available actions** - you are NOT limited to label-linked actions
2. **Analyse the email content first** - understand what the email actually needs (job inquiry? spam? scheduling request? urgent reply?)
3. **Use label instructions as guidance**, not rigid constraints - be flexible and intelligent
4. **Make smart decisions** based on email content:
   - Email mentions scheduling/meeting → consider schedule action
   - Email is clearly spam → use mark_as_spam
   - Email is job inquiry → use create_job (even if not linked to label)
   - Email needs immediate reply → use send_reply vs draft_reply based on urgency
   - Email mentions specific dates → extract and schedule
5. **Prefer label-linked actions when appropriate**, but don't be constrained by them
6. **Consider time of day, urgency, and other contextual factors**
7. **Skip unnecessary actions** - only execute what makes sense
8. **Determine optimal execution order** - some actions may depend on others
9. **Use Australian English spelling**
10. **Be context-aware and intelligent** - the goal is to handle emails appropriately, not just follow a rigid script

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
