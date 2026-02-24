"""
AI Action Orchestrator - Uses AI to dynamically decide which actions to execute
and in what order, based on email context and label instructions.
"""
import json
import logging
from typing import Dict, List, Any

from automation.models import Label, Action
from automation.services import OpenAIClient
from automation.context_builder import (
    build_action_context,
    build_ai_system_prompt,
    build_ai_user_prompt
)
from automation.action_executors import execute_action
from mail.models import EmailMessage

logger = logging.getLogger(__name__)


def orchestrate_label_actions(
    label: Label,
    email: EmailMessage,
    client: OpenAIClient
) -> Dict[str, Any]:
    """
    Orchestrate actions for a label using AI decision-making.
    
    The AI analyses the email, reviews the label's instructions, and decides which actions
    to execute and in what order.
    
    IMPORTANT: Only actions linked to labels currently applied to the email can be used.
    This ensures actions are only available when appropriate labels are present.
    
    Args:
        label: The Label that was applied
        email: The EmailMessage to process
        client: OpenAI client
        
    Returns:
        Dict with orchestration results
    """
    try:
        # Get ALL labels currently applied to this email
        from automation.models import EmailLabel
        email_labels = EmailLabel.objects.filter(
            email_message=email
        ).select_related('label').prefetch_related('label__actions')
        
        # Collect all actions from all labels applied to the email
        available_actions_set = set()
        applied_labels = []
        
        for email_label in email_labels:
            applied_label = email_label.label
            applied_labels.append(applied_label)
            # Get all actions linked to this label
            for action in applied_label.actions.all():
                available_actions_set.add(action)
        
        # Convert to list and sort by name for consistency
        available_actions = sorted(list(available_actions_set), key=lambda a: a.name)
        
        if not available_actions:
            return {
                "success": True,
                "message": f"No actions linked to labels applied to this email. Applied labels: {[l.name for l in applied_labels]}",
                "actions_executed": []
            }
        
        # Build context with all available actions from applied labels
        # Note: label_actions here refers to actions from the specific label that triggered this orchestration
        label_actions = list(label.actions.all())
        context = build_action_context(label, email, available_actions, label_actions)
        
        # Build AI prompts
        system_prompt = build_ai_system_prompt(context)
        user_prompt = build_ai_user_prompt(context)
        
        # Get AI decision on which actions to run
        action_plan = get_ai_action_plan(client, system_prompt, user_prompt, available_actions)
        
        if not action_plan or not action_plan.get("actions"):
            return {
                "success": True,
                "message": "AI determined no actions needed",
                "reasoning": action_plan.get("reasoning", "") if action_plan else "",
                "actions_executed": []
            }
        
        # Execute actions in AI-determined order
        execution_results = []
        execution_context = {}  # Context passed between actions
        
        for action_item in action_plan["actions"]:
            tool_name = action_item.get("tool_name")
            reason = action_item.get("reason", "")
            
            # Find the action by tool name
            action = find_action_by_tool_name(available_actions, tool_name)
            
            if not action:
                logger.warning(f"Action with tool name '{tool_name}' not found")
                execution_results.append({
                    "action": tool_name,
                    "success": False,
                    "message": f"Action '{tool_name}' not found"
                })
                continue
            
            
            # Execute the action
            result = execute_action(action, email, client, execution_context)
            
            execution_results.append({
                "action": action.name,
                "tool_name": tool_name,
                "reason": reason,
                **result
            })
            
            # Update context for next actions (e.g., if draft was created, pass draft_id)
            if result.get("success") and result.get("data"):
                execution_context.update(result["data"])
        
        
        return {
            "success": True,
            "message": f"Executed {len(execution_results)} actions",
            "reasoning": action_plan.get("reasoning", ""),
            "actions_executed": execution_results
        }
        
    except Exception as e:
        logger.error(
            f"Error in action orchestration for label {label.name} (email {email.pk}): {e}",
            exc_info=True
        )
        # Return detailed error for better debugging
        return {
            "success": False,
            "message": f"Orchestration error: {str(e)}",
            "error_type": type(e).__name__,
            "label_id": label.id,
            "email_id": email.pk,
            "actions_executed": []
        }


def get_ai_action_plan(
    client: OpenAIClient,
    system_prompt: str,
    user_prompt: str,
    available_actions: List[Action]
) -> Dict[str, Any]:
    """
    Get AI's decision on which actions to execute.
    
    Uses OpenAI's function calling API to get structured response.
    """
    if not client.client:
        logger.warning("OpenAI client not available, using fallback")
        return get_fallback_action_plan(available_actions)
    
    try:
        # Build tool definitions for available actions
        tools = build_tool_definitions(available_actions)
        
        # Log what we're sending to OpenAI for debugging
        logger.info(
            f"OpenAI Request - get_ai_action_plan:\n"
            f"Model: gpt-5-mini\n"
            f"System prompt length: {len(system_prompt)} chars\n"
            f"User prompt length: {len(user_prompt)} chars\n"
            f"Available actions: {[a.name for a in available_actions]}\n"
            f"User prompt preview: {user_prompt[:500]}..."
        )
        
        response = client.client.chat.completions.create(
            model="gpt-5-mini",  # Using gpt-5-mini for cost efficiency
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        )
        
        logger.info(f"OpenAI Response - get_ai_action_plan: {len(response.choices[0].message.content) if response.choices else 0} chars")
        
        choices = response.choices or []
        if not choices:
            logger.warning("No choices in OpenAI response")
            return get_fallback_action_plan(available_actions)
        
        content = choices[0].message.content
        if not content:
            logger.warning("Empty content in OpenAI response")
            return get_fallback_action_plan(available_actions)
        
        # Parse JSON response
        plan = json.loads(content)
        
        # Validate structure
        if not isinstance(plan, dict):
            return get_fallback_action_plan(available_actions)
        
        # Ensure actions is a list
        if "actions" not in plan:
            plan["actions"] = []
        elif not isinstance(plan["actions"], list):
            plan["actions"] = []
        
        return plan
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response JSON: {e}")
        return get_fallback_action_plan(available_actions)
    except Exception as e:
        logger.error(f"Error getting AI action plan: {e}", exc_info=True)
        return get_fallback_action_plan(available_actions)


def build_tool_definitions(available_actions: List[Action]) -> List[Dict]:
    """
    Build tool definitions for OpenAI function calling.
    Note: We're using JSON mode instead of function calling for simplicity,
    but this structure could be used if we switch to function calling.
    """
    # For now, we use JSON mode, but this could be extended to use function calling
    return []


def get_fallback_action_plan(available_actions: List[Action]) -> Dict[str, Any]:
    """
    Fallback: execute all actions in their configured order if AI is unavailable.
    This maintains backward compatibility.
    """
    actions = []
    for action in available_actions:
        actions.append({
            "tool_name": action.effective_tool_name,
            "reason": "Fallback: executing all configured actions"
        })
    
    return {
        "reasoning": "AI unavailable, using fallback: executing all actions in order",
        "actions": actions
    }


def find_action_by_tool_name(available_actions: List[Action], tool_name: str) -> Action | None:
    """Find an action by its tool name"""
    for action in available_actions:
        if action.effective_tool_name == tool_name:
            return action
    return None
