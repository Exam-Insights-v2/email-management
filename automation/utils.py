"""
Utility functions for automation features
"""
from automation.models import Label, Action
from automation.recommended_labels import RECOMMENDED_LABELS
from automation.recommended_actions import RECOMMENDED_ACTIONS
from automation.label_action_mapping import LABEL_ACTION_MAPPING


def create_recommended_actions_for_account(account):
    """
    Create all recommended actions for an account.
    Skips actions that already exist (case-insensitive).
    
    Args:
        account: Account instance to create actions for
        
    Returns:
        tuple: (created_count, skipped_count)
    """
    created_count = 0
    skipped_count = 0
    
    for action_data in RECOMMENDED_ACTIONS:
        # Check if action already exists (case-insensitive, by name and function)
        existing = Action.objects.filter(
            account=account,
            name__iexact=action_data['name']
        ).first()
        
        if existing:
            skipped_count += 1
            continue
        
        # Create the action
        Action.objects.create(
            account=account,
            name=action_data['name'],
            function=action_data['function'],
            instructions=action_data.get('instructions', ''),
            mcp_tool_name=action_data.get('mcp_tool_name', '') or None,
            tool_description=action_data.get('tool_description', '') or None,
        )
        created_count += 1
    
    return created_count, skipped_count


def create_recommended_labels_for_account(account):
    """
    Create all recommended labels for an account and link appropriate actions.
    Skips labels that already exist (case-insensitive).
    
    Args:
        account: Account instance to create labels for
        
    Returns:
        tuple: (created_count, skipped_count)
    """
    created_count = 0
    skipped_count = 0
    
    # Get all actions for this account, indexed by function name for quick lookup
    account_actions = {action.function: action for action in Action.objects.filter(account=account)}
    
    for label_data in RECOMMENDED_LABELS:
        # Check if label already exists (case-insensitive)
        existing = Label.objects.filter(
            account=account,
            name__iexact=label_data['name']
        ).first()
        
        if existing:
            skipped_count += 1
            # Still try to link actions if they're not already linked
            link_actions_to_label(existing, account_actions, label_data['name'])
            continue
        
        # Create the label
        label = Label.objects.create(
            account=account,
            name=label_data['name'],
            prompt=label_data.get('prompt', ''),
            instructions=label_data.get('instructions', ''),
            priority=label_data['priority'],
            is_active=True
        )
        # By default, make the label available to the owner account
        label.accounts.add(account)
        
        # Link appropriate actions to this label
        link_actions_to_label(label, account_actions, label_data['name'])
        
        created_count += 1
    
    return created_count, skipped_count


def link_actions_to_label(label, account_actions, label_name):
    """
    Link actions to a label based on the LABEL_ACTION_MAPPING.
    
    Args:
        label: Label instance to link actions to
        account_actions: Dict mapping action function names to Action instances
        label_name: Name of the label (for lookup in mapping)
    """
    # Get action function names that should be linked to this label
    action_functions = LABEL_ACTION_MAPPING.get(label_name, [])
    
    for function_name in action_functions:
        action = account_actions.get(function_name)
        if action and action not in label.actions.all():
            label.actions.add(action)


def setup_account_automation(account):
    """
    Set up all recommended labels and actions for a new account.
    This is called when a new account is created.
    
    IMPORTANT: Actions must be created before labels so they can be linked.
    
    Args:
        account: Account instance to set up
        
    Returns:
        dict: {
            'labels': {'created': int, 'skipped': int},
            'actions': {'created': int, 'skipped': int}
        }
    """
    # Create actions FIRST so they can be linked to labels
    actions_created, actions_skipped = create_recommended_actions_for_account(account)
    
    # Then create labels and link actions to them
    labels_created, labels_skipped = create_recommended_labels_for_account(account)
    
    return {
        'labels': {'created': labels_created, 'skipped': labels_skipped},
        'actions': {'created': actions_created, 'skipped': actions_skipped}
    }
