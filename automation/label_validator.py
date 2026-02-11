"""
Label validation utilities to prevent contradictory and redundant labels.
"""
import logging
from typing import List, Set

logger = logging.getLogger(__name__)


# Define mutually exclusive label groups
MUTUALLY_EXCLUSIVE_GROUPS = [
    # Content Type - can only be one
    {"Spam", "Personal", "Marketing", "Cold Email", "Newsletter", "Notification", "Receipt", "Calendar"},
    # Action Status - mutually exclusive states
    {"To Reply", "Awaiting Reply", "Actioned", "FYI"},
    # Priority - choose one
    {"Urgent", "Important"},
]

# Define label categories for hierarchy
LABEL_CATEGORIES = {
    "content_type": {"Spam", "Personal", "Marketing", "Cold Email", "Newsletter", "Notification", "Receipt", "Calendar"},
    "action_status": {"To Reply", "Awaiting Reply", "Actioned", "FYI"},
    "business_type": {"Quotes", "Job Inquiry", "Scheduling", "Follow-up", "Complaint", "Invoice", "Documents", "Support Ticket"},
    "priority": {"Urgent", "Important"},
    "relationship": {"Investor", "Supplier", "Networking"},
    "organizational": {"Archive"},
}

# Define label priorities (higher priority = more specific, should be kept if conflict)
LABEL_PRIORITIES = {
    "Spam": 10,  # Highest - spam takes precedence
    "Urgent": 9,  # Urgent is more specific than Important
    "Important": 8,
    "Complaint": 7,  # Complaints are urgent business
    "To Reply": 6,
    "Job Inquiry": 6,
    "Quotes": 6,
    "Follow-up": 5,
    "Awaiting Reply": 4,
    "Scheduling": 4,
    "Personal": 3,
    "Marketing": 2,
    "Cold Email": 2,
    "FYI": 2,
    "Actioned": 1,
    "Archive": 1,
    "Newsletter": 1,
    "Notification": 1,
    "Receipt": 1,
    "Calendar": 1,
    "Invoice": 1,
    "Documents": 4,
    "Support Ticket": 3,
    "Investor": 4,
    "Supplier": 3,
    "Networking": 2,
}


def validate_and_filter_labels(label_names: List[str], max_labels: int = 3) -> List[str]:
    """
    Validate and filter labels to remove contradictions and enforce limits.
    
    Args:
        label_names: List of label names from AI classification
        max_labels: Maximum number of labels to return (default: 3)
        
    Returns:
        Filtered list of label names with contradictions removed
    """
    if not label_names:
        return []
    
    # Normalize label names (case-insensitive)
    normalized_labels = {name.strip() for name in label_names if name and name.strip()}
    
    if not normalized_labels:
        return []
    
    # Step 1: Remove labels from mutually exclusive groups
    filtered_labels = set()
    
    for label in normalized_labels:
        # Check if this label conflicts with already selected labels
        conflicts = False
        
        for group in MUTUALLY_EXCLUSIVE_GROUPS:
            # Check if label is in this group
            if label in group:
                # Check if any already selected label is also in this group
                if any(selected in group for selected in filtered_labels):
                    # Conflict! Keep the one with higher priority
                    conflicting = [l for l in filtered_labels if l in group]
                    if conflicting:
                        conflicting_label = conflicting[0]
                        if LABEL_PRIORITIES.get(label, 0) > LABEL_PRIORITIES.get(conflicting_label, 0):
                            # New label has higher priority, remove conflicting
                            filtered_labels.remove(conflicting_label)
                            filtered_labels.add(label)
                            logger.info(f"Replaced {conflicting_label} with {label} (higher priority)")
                        else:
                            # Existing label has higher priority, skip new label
                            logger.info(f"Skipped {label} (conflicts with {conflicting_label})")
                            conflicts = True
                            break
        
        if not conflicts:
            filtered_labels.add(label)
    
    # Step 2: Enforce category limits (max 1 per category)
    category_selections = {}
    final_labels = []
    
    # Sort by priority (highest first)
    sorted_labels = sorted(filtered_labels, key=lambda x: LABEL_PRIORITIES.get(x, 0), reverse=True)
    
    for label in sorted_labels:
        # Find which category this label belongs to
        label_category = None
        for category, labels in LABEL_CATEGORIES.items():
            if label in labels:
                label_category = category
                break
        
        # If category already has a label, skip this one (unless it's higher priority)
        if label_category and label_category in category_selections:
            existing = category_selections[label_category]
            if LABEL_PRIORITIES.get(label, 0) > LABEL_PRIORITIES.get(existing, 0):
                # Replace with higher priority label
                final_labels.remove(existing)
                final_labels.append(label)
                category_selections[label_category] = label
                logger.info(f"Replaced {existing} with {label} in category {label_category}")
            else:
                logger.info(f"Skipped {label} (category {label_category} already has {existing})")
        else:
            final_labels.append(label)
            if label_category:
                category_selections[label_category] = label
    
    # Step 3: Limit to max_labels
    if len(final_labels) > max_labels:
        # Keep top priority labels
        final_labels = sorted(final_labels, key=lambda x: LABEL_PRIORITIES.get(x, 0), reverse=True)[:max_labels]
        logger.info(f"Limited labels to {max_labels}: {final_labels}")
    
    return final_labels


def get_label_category(label_name: str) -> str:
    """Get the category for a label name"""
    for category, labels in LABEL_CATEGORIES.items():
        if label_name in labels:
            return category
    return "other"
