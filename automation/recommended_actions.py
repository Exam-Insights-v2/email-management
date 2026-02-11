"""
Recommended actions that should be created for new accounts.
These provide essential actions for email automation.
"""

RECOMMENDED_ACTIONS = [
    {
        "name": "Draft Reply",
        "function": "draft_reply",
        "instructions": "Draft a professional email reply addressing the sender's questions or requests. Use the account's writing style if available.",
        "mcp_tool_name": "",
        "tool_description": "Create a draft email reply for review before sending",
    },
    {
        "name": "Send Reply",
        "function": "send_reply",
        "instructions": "Send an automated/templated email reply immediately. Only use for standardised responses like confirmations, receipts, or automated acknowledgements. NOT for custom business communications that need human review.",
        "mcp_tool_name": "",
        "tool_description": "Send an automated/templated email reply immediately (for standardised responses only)",
    },
    {
        "name": "Create Job",
        "function": "create_job",
        "instructions": "Create a job record for line-marking work. Extract job details: location, service type, customer info, dates.",
        "mcp_tool_name": "",
        "tool_description": "Create a job record from email inquiry",
    },
    {
        "name": "Schedule",
        "function": "schedule",
        "instructions": "Schedule a meeting, appointment, or follow-up. Extract date, time, and location from email.",
        "mcp_tool_name": "",
        "tool_description": "Schedule a meeting or appointment",
    },
    {
        "name": "Archive Email",
        "function": "archive_email",
        "instructions": "Archive the email (remove from inbox). Use for emails that are informational or completed.",
        "mcp_tool_name": "",
        "tool_description": "Archive email from inbox",
    },
    {
        "name": "Mark as Spam",
        "function": "mark_as_spam",
        "instructions": "Mark the email as spam. Use for unwanted or junk emails.",
        "mcp_tool_name": "",
        "tool_description": "Mark email as spam",
    },
    {
        "name": "Delete Email",
        "function": "delete_email",
        "instructions": "Delete the email. Use for spam or unwanted emails that should be permanently removed.",
        "mcp_tool_name": "",
        "tool_description": "Delete email permanently",
    },
    {
        "name": "Forward Email",
        "function": "forward_email",
        "instructions": "Forward the email to specified recipients. Parse recipient email addresses from instructions (format: 'to: email1@example.com, email2@example.com').",
        "mcp_tool_name": "",
        "tool_description": "Forward email to recipients",
    },
]
