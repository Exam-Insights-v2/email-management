"""
Recommended labels that users can choose from when setting up their account.
These provide a good starting point for email classification.
"""

RECOMMENDED_LABELS = [
    # ============================================
    # BUSINESS COMMUNICATION LABELS
    # ============================================
    {
        "name": "Quotes",
        "prompt": "Emails where a user is asking for a quote, pricing, or estimate. Includes requests for proposals, bids, or cost estimates.",
        "instructions": "Extract key details: location, service type, scope of work, and any deadlines. Create a job if it's a serious inquiry. Draft a professional quote response with pricing information. Set high priority if there's a deadline mentioned.",
        "priority": 4,
        "category": "Business Communication"
    },
    {
        "name": "Job Inquiry",
        "prompt": "New job inquiries, project requests, or potential work opportunities. Emails from potential clients asking about services.",
        "instructions": "Extract job details: location, service type, timeline, and contact information. Create a job record. Draft a professional response acknowledging the inquiry and requesting any missing details. Set high priority for new business opportunities.",
        "priority": 4,
        "category": "Business Communication"
    },
    {
        "name": "Scheduling",
        "prompt": "Any email related to scheduling, meetings, appointments, site visits, or calendar coordination.",
        "instructions": "Extract date, time, location, and meeting purpose. Use schedule action if available to add to calendar. Draft a confirmation response. If it's a site visit, create a job or task with the scheduled date.",
        "priority": 3,
        "category": "Business Communication"
    },
    {
        "name": "Complaint",
        "prompt": "Customer complaints, issues, problems, or negative feedback that needs to be addressed.",
        "instructions": "This is urgent - requires immediate attention. Extract complaint details: what went wrong, when, who was involved. Draft a professional, empathetic response acknowledging the issue. Create a task to track resolution. Set highest priority (5).",
        "priority": 5,
        "category": "Business Communication"
    },
    {
        "name": "Invoice",
        "prompt": "Invoices, billing, payment requests, or financial documents related to accounts payable or receivable.",
        "instructions": "Extract invoice details: amount, due date, invoice number, and vendor/client. If it's an invoice we're sending, ensure it's properly formatted. If it's one we're receiving, note the due date and create a reminder if needed. Archive for records.",
        "priority": 3,
        "category": "Business Communication"
    },
    {
        "name": "Documents",
        "prompt": "Contract discussions, agreements, terms and conditions, legal documents, formal agreements, or any document-related communications that require review, signature, or action.",
        "instructions": "Extract key document details: parties involved, dates, obligations, deadlines, and document type. Create a task to track document review or execution. Draft a response acknowledging receipt. Set high priority if signature or action is required by a deadline.",
        "priority": 4,
        "category": "Business Communication"
    },
    {
        "name": "Support Ticket",
        "prompt": "Support requests, help requests, technical issues, customer service inquiries, or requests for assistance with products or services.",
        "instructions": "Extract the issue details: what problem they're experiencing, when it started, steps they've tried, and any error messages. Create a task to track resolution. Draft a helpful response acknowledging the issue and providing next steps or requesting more information. Set priority based on urgency (high for critical issues, medium for general support).",
        "priority": 3,
        "category": "Business Communication"
    },
    
    # ============================================
    # AUTOMATED & SYSTEM LABELS
    # ============================================
    {
        "name": "Newsletter",
        "prompt": "Regular content from publications, industry newsletters, or subscription-based content. Usually informational, not requiring action.",
        "instructions": "Archive or mark as read. No action needed - this is informational content. Can be deleted if not relevant.",
        "priority": 1,
        "category": "Automated & System"
    },
    {
        "name": "Marketing",
        "prompt": "Promotional emails about products, services, special offers, sales, or marketing campaigns.",
        "instructions": "Archive or delete. Typically no action needed unless it's a relevant business opportunity. Can be marked as spam if unwanted.",
        "priority": 1,
        "category": "Automated & System"
    },
    {
        "name": "Notification",
        "prompt": "Alerts, status updates, or system notifications from services, apps, or platforms. Automated messages that inform but don't require action.",
        "instructions": "Read and archive. These are informational notifications. Only take action if the notification indicates a problem or requires attention.",
        "priority": 1,
        "category": "Automated & System"
    },
    {
        "name": "Receipt",
        "prompt": "Purchase confirmations, payment receipts, order confirmations, or transaction records.",
        "instructions": "Archive for records. Extract key details: amount, date, transaction ID if needed for accounting. No response required.",
        "priority": 1,
        "category": "Automated & System"
    },
    {
        "name": "Calendar",
        "prompt": "Calendar invitations, meeting requests, event confirmations, or calendar-related automated messages.",
        "instructions": "Extract meeting details: date, time, location, attendees. Use schedule action if available. Respond to calendar invites appropriately (accept/decline/tentative). Create a task if it's a site visit or important meeting.",
        "priority": 2,
        "category": "Automated & System"
    },
    
    # ============================================
    # RELATIONSHIP & NETWORKING LABELS
    # ============================================
    {
        "name": "Supplier",
        "prompt": "Emails from suppliers, vendors, or business partners providing goods or services.",
        "instructions": "Extract order details, delivery dates, pricing, or service information. Respond to inquiries or confirmations. Create tasks for orders or deliveries that need tracking. Archive invoices or receipts.",
        "priority": 3,
        "category": "Relationship & Networking"
    },
    {
        "name": "Cold Email",
        "prompt": "Unsolicited emails trying to sell a product or service, cold outreach, or sales pitches from unknown senders.",
        "instructions": "Archive or delete. No response needed unless it's a relevant business opportunity. Can be marked as spam if unwanted.",
        "priority": 1,
        "category": "Relationship & Networking"
    },
    {
        "name": "Networking",
        "prompt": "Professional networking emails, introductions, referrals, or relationship-building communications that aren't direct business inquiries. Use 'Job Inquiry' or 'Quotes' if it's a business opportunity.",
        "instructions": "Draft a friendly, professional response. Extract contact information and any meeting requests. Create a task to follow up if appropriate. Schedule meetings if requested. If it leads to a business opportunity, create a job record.",
        "priority": 2,
        "category": "Relationship & Networking"
    },
    
    # ============================================
    # ORGANISATIONAL LABELS
    # ============================================
    {
        "name": "Spam",
        "prompt": "Spam, junk mail, or unwanted emails that should be filtered out or deleted. Mutually exclusive with business, personal, and action labels.",
        "instructions": "Delete this email. Use mark_as_spam or delete_email action. No response needed. This helps train spam filters.",
        "priority": 1,
        "category": "Organisational"
    },
    {
        "name": "Personal",
        "prompt": "Personal emails not related to business. Private communications from friends, family, or personal matters. Mutually exclusive with business and spam labels.",
        "instructions": "Archive or leave as-is. Handle personally - no business action needed. Keep separate from business communications.",
        "priority": 2,
        "category": "Organisational"
    },
]

# Group labels by category for easier display
LABELS_BY_CATEGORY = {}
for label in RECOMMENDED_LABELS:
    category = label["category"]
    if category not in LABELS_BY_CATEGORY:
        LABELS_BY_CATEGORY[category] = []
    LABELS_BY_CATEGORY[category].append(label)

# Get all unique categories
CATEGORIES = sorted(LABELS_BY_CATEGORY.keys())
