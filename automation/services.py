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
            system_prompt = """You are an email classification assistant for a line-marking company in Australia.
You analyse emails and return structured JSON with task classification.

Return JSON with these exact fields:
- task_title: Clear, actionable task title (max 255 chars)
- task_description: Summary of email content and required action
- priority: Integer 1-5 (1=low priority, 5=urgent)
- labels: Array of applicable label names from the available labels list
- due_date: YYYY-MM-DD format if mentioned in email, null otherwise
- reasoning: Brief explanation of your classification

Use Australian English spelling. Be concise but informative."""

            user_prompt = f"""Available Labels:
{labels_text}

Email to classify:
Subject: {email_subject}
From: {email_from}
Body:
{email_body[:3000]}  # Limit body length to avoid token limits

Return JSON only, no additional text."""

            response = self.client.chat.completions.create(
                model="gpt-5-mini",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )

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
