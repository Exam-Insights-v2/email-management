"""
Context builder for MCP action orchestration.
Builds the context that will be provided to the AI for decision-making.
"""
from typing import Dict, List
from automation.models import Label, Action, StandardOperatingProcedure
from mail.models import EmailMessage


def build_action_context(
    label: Label,
    email: EmailMessage,
    available_actions: List[Action]
) -> Dict:
    """
    Build comprehensive context for AI action orchestration.
    
    Returns:
        Dict with all context needed for AI to make action decisions
    """
    # Get account SOPs (active, ordered by priority)
    account_sops = StandardOperatingProcedure.objects.filter(
        account=email.account,
        is_active=True
    ).order_by("-priority", "name")
    
    # Format SOPs for prompt
    sop_text = format_sops(account_sops)
    
    # Format label-specific SOP context
    label_sop_context = label.sop_context or ""
    
    # Format available actions as tool descriptions
    actions_text = format_actions(available_actions)
    
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
        "sops": sop_text,
        "label_sop_context": label_sop_context,
        "label_prompt": label.prompt or "",
        "actions": actions_text,
        "email": email_context,
        "account_settings": account_settings,
    }


def format_sops(sops) -> str:
    """Format SOPs for inclusion in AI prompt"""
    if not sops:
        return "No Standard Operating Procedures defined."
    
    lines = []
    for sop in sops:
        lines.append(f"**{sop.name}** (Priority: {sop.priority})")
        lines.append(f"  When: {sop.description}")
        lines.append(f"  Instructions: {sop.instructions}")
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

Your role is to analyse emails and decide which actions to execute, and in what order, based on:
1. The email content and context
2. Standard Operating Procedures (SOPs)
3. Label-specific instructions
4. Account settings

STANDARD OPERATING PROCEDURES:
{context['sops']}

LABEL-SPECIFIC CONTEXT:
{context['label_sop_context'] if context['label_sop_context'] else 'None'}

LABEL PROMPT:
{context['label_prompt'] if context['label_prompt'] else 'None'}

AVAILABLE ACTIONS:
{context['actions']}

ACCOUNT SETTINGS:
Writing Style: {context['account_settings']['writing_style'] if context['account_settings']['writing_style'] else 'Not specified'}

INSTRUCTIONS:
1. Analyse the email content carefully
2. Review relevant SOPs and determine which apply
3. Decide which actions to execute based on context
4. Determine the optimal execution order (actions may need to run out of sequential order)
5. Skip unnecessary actions if they don't apply
6. Adapt based on email content - be smart about conditional execution
7. Use Australian English spelling
8. Consider time of day, urgency, and other contextual factors

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
