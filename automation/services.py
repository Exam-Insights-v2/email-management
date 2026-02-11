import os
import json
import logging
import re
from datetime import datetime
from typing import List, Dict, Optional
from html import unescape

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None

from mail.models import EmailMessage
from automation.models import Label

logger = logging.getLogger(__name__)


class OpenAIClient:
    def __init__(self):
        api_key = os.environ.get("OPENAI_API_KEY", "")
        self.client = OpenAI(api_key=api_key) if OpenAI and api_key else None

    def classify_email(
        self, email_message: EmailMessage, available_labels: List[Label]
    ) -> Dict:
        """
        Single AI call to classify email and generate task data.
        
        Returns:
            {
                "task_title": str,
                "task_description": str,
                "priority": int (1-5),
                "labels": List[str],
                "due_date": str | None,
                "reasoning": str
            }
        """
        if not self.client:
            logger.warning("OpenAI client not available, using defaults")
            return self._default_classification(email_message, available_labels)

        try:
            # Prepare email content
            email_subject = email_message.subject or "(No subject)"
            email_body = self._strip_html(email_message.body_html or "")
            email_from = email_message.from_name or email_message.from_address

            # Format available labels
            labels_text = self._format_labels(available_labels)

            # Build prompt
            system_prompt = """You are an email classification assistant.
                    Your role is to analyse incoming emails and create actionable tasks with appropriate labels and priorities.

                    CLASSIFICATION GUIDELINES:

                    1. TASK TITLE (max 255 chars):
                    - Be specific and action-oriented (e.g., "Quote for car park marking - [Location]" not "Email from John")
                    - Include key details: location, service type, or customer name if relevant
                    - Avoid generic titles like "Email" or "Inquiry"
                    - Use Australian English spelling

                    2. TASK DESCRIPTION:
                    - Summarise the email content clearly
                    - Highlight the required action or response needed
                    - Include important details: dates, locations, contact info, specific requests
                    - Use \\n (newline characters) to separate different sections for readability
                    - Structure with line breaks between: summary/context, required actions, important details.
                    - Example format: "Summary text.\\n\\nRequired actions: list actions."
                    - If this is a follow-up email (previous messages shown below), reference what it's following up on
                    - For follow-ups: note if urgency has increased, if new information was provided, or if the situation has changed

                    3. PRIORITY (1-5 scale):
                    - 5 (Urgent): Immediate action required (e.g., urgent deadline, complaint, time-sensitive request)
                    - 4 (High): Important but not immediate (e.g., new job inquiry, quote request with deadline)
                    - 3 (Medium): Standard business communication (e.g., follow-ups, scheduling, standard inquiries)
                    - 2 (Low): Informational or non-urgent (e.g., newsletters, confirmations, routine updates)
                    - 1 (Lowest): Spam, automated messages, or items requiring no action

                    4. LABELS:
                    - Select the MINIMUM number of labels needed to accurately classify this email (1-3 labels maximum)
                    - Prioritize the most specific and relevant label
                    - Avoid redundant or contradictory labels:
                      * If "Spam" applies, don't use business or personal labels
                      * If "Personal" applies, don't use business or spam labels
                      * Focus on WHAT the email is about (content type, business type, relationship), not HOW to handle it (action status, urgency)
                      * Action needs and urgency are determined from email content and reflected in task priority (1-5)
                    - Choose labels that are mutually compatible
                    - Match labels based on their criteria (shown in parentheses after each label name)
                    - Only use labels that are explicitly listed - do not create new label names
                    
                    LABEL SELECTION HIERARCHY (choose maximum 1 per category):
                    1. Content Type (if applicable): Spam, Personal, Marketing, Cold Email, Newsletter, Notification, Receipt, Calendar
                    2. Business Type (if applicable): Quotes, Job Inquiry, Scheduling, Complaint, Invoice, Documents, Support Ticket
                    3. Relationship (if applicable, optional): Investor, Supplier, Networking
                    
                    Note: Action status (needs reply, awaiting reply, etc.) and urgency are determined by the email content itself and reflected in the task priority (1-5), not through labels.
                    
                    Maximum 3 labels total. If multiple labels from the same category apply, choose the most specific one.

                    5. DUE DATE:
                    - Extract dates mentioned in the email (deadlines, meeting dates, follow-up dates)
                    - Format as YYYY-MM-DD
                    - Only include if a specific date is mentioned or implied
                    - Return null if no date is mentioned

                    6. REASONING:
                    - Briefly explain why you chose this classification
                    - Mention which label criteria matched and why
                    - Note any factors that influenced priority

                    Return JSON with these exact fields:
                    - task_title: Clear, actionable task title (max 255 chars)
                    - task_description: Summary of email content and required action
                    - priority: Integer 1-5 (1=low priority, 5=urgent)
                    - labels: Array of applicable label names from the available labels list
                    - due_date: YYYY-MM-DD format if mentioned in email, null otherwise
                    - reasoning: Brief explanation of your classification"""

            # Check if there's conversation history
            thread_context = ""
            if email_message.thread:
                previous_messages = list(
                    email_message.thread.messages
                    .exclude(pk=email_message.pk)
                    .order_by("-date_sent")[:3]  # Last 3 messages for context
                )
                if previous_messages:
                    thread_context = "\n\nPrevious messages in this conversation:\n"
                    for msg in reversed(previous_messages):  # Show in chronological order
                        prev_body = self._strip_html(msg.body_html or "")[:500]
                        thread_context += f"- From {msg.from_name or msg.from_address} ({msg.date_sent.strftime('%Y-%m-%d') if msg.date_sent else 'Unknown date'}): {prev_body}\n"

            user_prompt = f"""Available Labels:
{labels_text}

Email to classify:
Subject: {email_subject}
From: {email_from}
Body:
{email_body[:3000]}{thread_context}

Return JSON only, no additional text."""

            # Log what we're sending to OpenAI for debugging
            logger.info(
                f"OpenAI Request - classify_email for email {email_message.pk}:\n"
                f"Model: gpt-5-mini\n"
                f"System prompt length: {len(system_prompt)} chars\n"
                f"User prompt length: {len(user_prompt)} chars\n"
                f"Email subject: {email_subject[:100]}\n"
                f"Email from: {email_from}\n"
                f"Available labels: {[l.name for l in available_labels]}\n"
                f"User prompt preview: {user_prompt[:500]}..."
            )
            
            response = self.client.chat.completions.create(
                model="gpt-5-mini",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            
            logger.info(f"OpenAI Response - classify_email for email {email_message.pk}: {len(response.choices[0].message.content) if response.choices else 0} chars")

            choices = response.choices or []
            if not choices:
                logger.warning("No choices in OpenAI response")
                return self._default_classification(email_message, available_labels)

            # FIX: Use .content not .get("content")
            content = choices[0].message.content
            if not content:
                logger.warning("Empty content in OpenAI response")
                return self._default_classification(email_message, available_labels)

            # Parse JSON response
            data = json.loads(content)

            # Validate and sanitize response
            return {
                "task_title": str(data.get("task_title", email_subject))[:255],
                "task_description": str(data.get("task_description", "")) or f"Email from {email_from}: {email_subject}",
                "priority": self._validate_priority(data.get("priority", 1)),
                "labels": self._validate_labels(data.get("labels", []), available_labels),
                "due_date": data.get("due_date"),  # Will be parsed later
                "reasoning": str(data.get("reasoning", "")),
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OpenAI JSON response: {e}")
            return self._default_classification(email_message, available_labels)
        except Exception as e:
            logger.error(f"Error in classify_email: {e}", exc_info=True)
            return self._default_classification(email_message, available_labels)

    def _format_labels(self, labels: List[Label]) -> str:
        """Format labels for prompt"""
        if not labels:
            return "No labels available"
        
        lines = []
        for label in labels:
            prompt_text = f" ({label.prompt})" if label.prompt else ""
            lines.append(f"- {label.name}{prompt_text}")
        return "\n".join(lines)

    def _strip_html(self, html: str) -> str:
        """Strip HTML tags and decode entities"""
        if not html:
            return ""
        # Simple HTML tag removal
        text = re.sub(r"<[^>]+>", "", html)
        # Decode HTML entities
        text = unescape(text)
        # Clean up whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _validate_priority(self, priority) -> int:
        """Ensure priority is between 1 and 5"""
        try:
            p = int(priority)
            return max(1, min(5, p))
        except (ValueError, TypeError):
            return 1

    def _validate_labels(self, label_names: List, available_labels: List[Label]) -> List[str]:
        """Validate that label names exist in available labels"""
        if not isinstance(label_names, list):
            return []
        
        available_names = {label.name.lower() for label in available_labels}
        valid_labels = []
        
        for name in label_names:
            if isinstance(name, str) and name.lower() in available_names:
                # Find the actual label name (preserve case)
                matching_label = next(
                    (l for l in available_labels if l.name.lower() == name.lower()),
                    None
                )
                if matching_label:
                    valid_labels.append(matching_label.name)
        
        return valid_labels

    def _default_classification(
        self, email_message: EmailMessage, available_labels: List[Label]
    ) -> Dict:
        """Fallback classification when AI is unavailable"""
        subject = email_message.subject or "(No subject)"
        from_name = email_message.from_name or email_message.from_address
        
        # Try to find a default label (available_labels is a list, not QuerySet)
        default_label = None
        if available_labels:
            # Search for "Awaiting Reply" label (case-insensitive)
            default_label = next(
                (l for l in available_labels if l.name.lower() == "awaiting reply"),
                None
            )
            # If not found, use first label
            if not default_label:
                default_label = available_labels[0] if available_labels else None
        
        return {
            "task_title": subject[:255],
            "task_description": f"Email from {from_name}: {subject}",
            "priority": 1,
            "labels": [default_label.name] if default_label else [],
            "due_date": None,
            "reasoning": "Default classification (AI unavailable)",
        }

    def suggest_labels(self, prompt: str, text: str):
        """Legacy method - kept for backwards compatibility"""
        if not self.client:
            return []
        response = self.client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": "You are classifying emails for a line-marking company."},
                {"role": "user", "content": f"{prompt}\n\nEmail:\n{text}"},
            ],
        )
        choices = response.choices or []
        if not choices:
            return []
        # FIX: Use .content not .get("content")
        content = choices[0].message.content or ""
        return [line.strip() for line in content.splitlines() if line.strip()]

    def draft_reply(self, instructions: str, context: str):
        if not self.client:
            return ""
        response = self.client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": "You respond as a polite, concise operations assistant."},
                {"role": "user", "content": f"{instructions}\n\nContext:\n{context}"},
            ],
        )
        choices = response.choices or []
        if not choices:
            return ""
        # FIX: Use .content not .get("content")
        return choices[0].message.content or ""
    
    def rewrite_draft(self, email_context: str, current_draft: str, user_feedback: str, writing_style: str = None):
        """
        Rewrite a draft email based on user feedback.
        
        Args:
            email_context: The original email thread context
            current_draft: The current draft body HTML
            user_feedback: User's feedback/instructions for the rewrite
            writing_style: Optional account writing style
            
        Returns:
            Rewritten draft body HTML
        """
        if not self.client:
            return current_draft
        
        system_prompt = "You are an email writing assistant. Rewrite email drafts based on user feedback while maintaining professionalism and clarity."
        
        user_prompt = f"""Rewrite the following email draft based on the user's feedback.

ORIGINAL EMAIL CONTEXT:
{email_context}

CURRENT DRAFT:
{current_draft}

USER FEEDBACK/INSTRUCTIONS:
{user_feedback}
"""
        
        if writing_style:
            user_prompt += f"\n\nWRITING STYLE:\n{writing_style}"
        
        user_prompt += "\n\nRewrite the draft email body (HTML format) incorporating the user's feedback. Keep the same tone and structure unless the feedback specifically requests changes."
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            choices = response.choices or []
            if not choices:
                return current_draft
            return choices[0].message.content or current_draft
        except Exception as e:
            logger.error(f"Error rewriting draft: {e}", exc_info=True)
            return current_draft