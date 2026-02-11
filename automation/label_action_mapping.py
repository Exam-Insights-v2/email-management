"""
Mapping of recommended actions to labels.
This defines which actions should be automatically linked to which labels
when setting up account automation.
"""

# Map label names to lists of action function names that should be linked
# NOTE: draft_reply is included for ALL labels as the primary goal is to draft replies to emails
LABEL_ACTION_MAPPING = {
    # Business Communication Labels
    "Quotes": ["draft_reply", "create_job"],
    "Job Inquiry": ["draft_reply", "create_job"],
    "Scheduling": ["draft_reply", "schedule"],
    "Complaint": ["draft_reply"],
    "Invoice": ["draft_reply", "archive_email"],
    "Documents": ["draft_reply"],
    "Support Ticket": ["draft_reply"],
    
    # Automated & System Labels
    "Newsletter": ["draft_reply", "archive_email"],
    "Marketing": ["draft_reply", "archive_email", "mark_as_spam"],
    "Notification": ["draft_reply", "archive_email"],
    "Receipt": ["draft_reply", "archive_email"],
    "Calendar": ["draft_reply", "schedule"],
    
    # Relationship & Networking Labels
    "Investor": ["draft_reply", "schedule"],
    "Supplier": ["draft_reply", "archive_email"],
    "Cold Email": ["draft_reply", "mark_as_spam", "delete_email", "archive_email"],
    "Networking": ["draft_reply", "schedule"],
    
    # Organisational Labels
    "Spam": ["draft_reply", "mark_as_spam", "delete_email"],
    "Personal": ["draft_reply", "archive_email"],
}
