import base64
import email
import email.utils
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import List, Optional

import requests
from django.db import transaction
from django.utils import timezone
from googleapiclient.discovery import build

from accounts.models import Account
from accounts.services import GmailOAuthService, MicrosoftEmailOAuthService
from mail.models import Draft, EmailMessage, EmailThread


class EmailProviderService:
    """Base class for email provider services"""

    def fetch_messages(
        self, account: Account, max_results: int = 50, since: Optional[datetime] = None
    ) -> List[dict]:
        """Fetch messages from provider. Returns list of message dicts."""
        raise NotImplementedError

    def get_message(self, account: Account, external_message_id: str) -> dict:
        """Get a single message by external ID"""
        raise NotImplementedError


class GmailService(EmailProviderService):
    """Gmail API service for fetching emails"""
    
    # Class-level cache for service instances per account
    _service_cache = {}
    _credentials_cache = {}
    _cache_lock = {}  # Track which accounts are being refreshed

    def __init__(self):
        # Instance-level cache is not useful since new instances are created each time
        # Use class-level cache instead
        pass

    def _get_service(self, account: Account):
        """Get Gmail API service instance with proper caching"""
        account_id = account.pk
        
        # Check if we have cached credentials and service for this account
        if account_id in self._service_cache and account_id in self._credentials_cache:
            cached_credentials = self._credentials_cache[account_id]
            cached_service = self._service_cache[account_id]
            
            # Verify credentials are still valid (not expired)
            if cached_credentials and not cached_credentials.expired:
                return cached_service
        
        # Get fresh credentials (will refresh if needed)
        credentials = GmailOAuthService.get_valid_credentials(account)
        if not credentials:
            # Clear cache on failure
            self._service_cache.pop(account_id, None)
            self._credentials_cache.pop(account_id, None)
            raise ValueError(f"Account {account} is not connected or token is invalid")
        
        # Build service with fresh credentials
        service = build("gmail", "v1", credentials=credentials)
        
        # Cache both credentials and service
        self._credentials_cache[account_id] = credentials
        self._service_cache[account_id] = service
        
        return service
    
    @classmethod
    def clear_cache(cls, account_id=None):
        """Clear service cache for an account or all accounts"""
        if account_id:
            cls._service_cache.pop(account_id, None)
            cls._credentials_cache.pop(account_id, None)
            cls._cache_lock.pop(account_id, None)
        else:
            cls._service_cache.clear()
            cls._credentials_cache.clear()
            cls._cache_lock.clear()

    def _parse_message(self, msg_data: dict) -> dict:
        """Parse Gmail API message format"""
        payload = msg_data.get("payload", {})
        headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}

        # Extract addresses
        def parse_addresses(header_value: str) -> List[str]:
            if not header_value:
                return []
            addresses = email.utils.getaddresses([header_value])
            return [addr[1] for addr in addresses if addr[1]]

        # Recursively extract body from parts
        def extract_body_from_parts(parts: List[dict]) -> tuple[str, str]:
            """Extract HTML and plain text bodies from message parts (recursive)"""
            html_body = ""
            plain_body = ""
            
            for part in parts:
                mime_type = part.get("mimeType", "")
                
                # If this part has nested parts, recurse
                if "parts" in part:
                    nested_html, nested_plain = extract_body_from_parts(part["parts"])
                    if nested_html:
                        html_body = nested_html
                    if nested_plain and not plain_body:
                        plain_body = nested_plain
                
                # Check for body data in this part
                body_data = part.get("body", {}).get("data", "")
                if body_data:
                    try:
                        decoded = base64.urlsafe_b64decode(body_data).decode("utf-8")
                        if mime_type == "text/html":
                            html_body = decoded
                        elif mime_type == "text/plain" and not plain_body:
                            plain_body = decoded
                    except Exception:
                        pass
            
            return html_body, plain_body

        # Get body - prefer HTML, fallback to plain text
        body_html = ""
        body_plain = ""
        
        if "parts" in payload:
            # Multipart message - recursively extract
            body_html, body_plain = extract_body_from_parts(payload["parts"])
        else:
            # Single part message
            mime_type = payload.get("mimeType", "")
            body_data = payload.get("body", {}).get("data", "")
            if body_data:
                try:
                    decoded = base64.urlsafe_b64decode(body_data).decode("utf-8")
                    if mime_type == "text/html":
                        body_html = decoded
                    elif mime_type == "text/plain":
                        body_plain = decoded
                except Exception:
                    pass
        
        # Use HTML if available, otherwise use plain text (wrapped in <pre>)
        if body_html:
            final_body = body_html
        elif body_plain:
            # Convert plain text to HTML
            final_body = f"<pre>{body_plain}</pre>"
        else:
            final_body = ""

        # Parse date
        date_sent = None
        if headers.get("date"):
            try:
                date_sent = parsedate_to_datetime(headers["date"])
            except Exception:
                pass

        return {
            "external_message_id": msg_data["id"],
            "external_thread_id": msg_data.get("threadId", ""),
            "subject": headers.get("subject", ""),
            "from_address": headers.get("from", "").split("<")[-1].replace(">", "").strip(),
            "from_name": headers.get("from", "").split("<")[0].strip().strip('"'),
            "to_addresses": parse_addresses(headers.get("to", "")),
            "cc_addresses": parse_addresses(headers.get("cc", "")),
            "bcc_addresses": parse_addresses(headers.get("bcc", "")),
            "date_sent": date_sent,
            "body_html": final_body,
        }

    def fetch_messages(
        self, account: Account, max_results: int = 50, since: Optional[datetime] = None
    ) -> List[dict]:
        """Fetch messages from Gmail - only received emails (inbox)"""
        service = self._get_service(account)

        # Build query: only received emails (not sent)
        # -in:sent means exclude sent folder
        # is:inbox means only inbox emails
        query_parts = ["-in:sent", "is:inbox"]
        
        if since:
            # Gmail query format: after:YYYY/MM/DD
            query_parts.append(f"after:{since.strftime('%Y/%m/%d')}")
        
        query = " ".join(query_parts)

        try:
            results = (
                service.users()
                .messages()
                .list(userId="me", maxResults=max_results, q=query)
                .execute()
            )
            messages = results.get("messages", [])

            parsed_messages = []
            for msg in messages:
                msg_id = msg["id"]
                msg_data = (
                    service.users().messages().get(userId="me", id=msg_id, format="full").execute()
                )
                parsed_messages.append(self._parse_message(msg_data))

            return parsed_messages
        except Exception as e:
            raise ValueError(f"Error fetching Gmail messages: {str(e)}")

    def get_message(self, account: Account, external_message_id: str) -> dict:
        """Get a single message by ID"""
        service = self._get_service(account)
        try:
            msg_data = (
                service.users()
                .messages()
                .get(userId="me", id=external_message_id, format="full")
                .execute()
            )
            return self._parse_message(msg_data)
        except Exception as e:
            raise ValueError(f"Error fetching Gmail message: {str(e)}")

    def get_thread_messages(self, account: Account, external_thread_id: str) -> List[dict]:
        """Get all messages in a thread"""
        try:
            service = self._get_service(account)
            thread = (
                service.users()
                .threads()
                .get(userId="me", id=external_thread_id, format="full")
                .execute()
            )
            messages = []
            for msg in thread.get("messages", []):
                messages.append(self._parse_message(msg))
            return messages
        except Exception as e:
            # Clear cache on error (especially 401/authentication errors)
            error_str = str(e).lower()
            if any(keyword in error_str for keyword in ["401", "unauthorized", "invalid_token", "invalid_grant"]):
                self.clear_cache(account.pk)
            raise ValueError(f"Error fetching Gmail thread: {str(e)}")

    def delete_message(self, account: Account, external_message_id: str):
        """Delete (trash) a message in Gmail"""
        service = self._get_service(account)
        try:
            service.users().messages().trash(userId="me", id=external_message_id).execute()
        except Exception as e:
            raise ValueError(f"Error deleting Gmail message: {str(e)}")

    def archive_message(self, account: Account, external_message_id: str):
        """Archive a message (remove from inbox)"""
        service = self._get_service(account)
        try:
            service.users().messages().modify(
                userId="me",
                id=external_message_id,
                body={"removeLabelIds": ["INBOX"]}
            ).execute()
        except Exception as e:
            raise ValueError(f"Error archiving Gmail message: {str(e)}")

    def mark_as_spam(self, account: Account, external_message_id: str):
        """Mark a message as spam"""
        service = self._get_service(account)
        try:
            service.users().messages().modify(
                userId="me",
                id=external_message_id,
                body={"addLabelIds": ["SPAM"]}
            ).execute()
        except Exception as e:
            raise ValueError(f"Error marking Gmail message as spam: {str(e)}")

    def add_gmail_label(self, account: Account, external_message_id: str, label_id: str):
        """Add a Gmail label to a message"""
        service = self._get_service(account)
        try:
            service.users().messages().modify(
                userId="me",
                id=external_message_id,
                body={"addLabelIds": [label_id]}
            ).execute()
        except Exception as e:
            raise ValueError(f"Error adding Gmail label: {str(e)}")

    def remove_gmail_label(self, account: Account, external_message_id: str, label_id: str):
        """Remove a Gmail label from a message"""
        service = self._get_service(account)
        try:
            service.users().messages().modify(
                userId="me",
                id=external_message_id,
                body={"removeLabelIds": [label_id]}
            ).execute()
        except Exception as e:
            raise ValueError(f"Error removing Gmail label: {str(e)}")

    def forward_message(
        self,
        account: Account,
        external_message_id: str,
        to_addresses: List[str],
        cc_addresses: List[str] = None,
        bcc_addresses: List[str] = None,
        note: str = None
    ) -> dict:
        """Forward an email message"""
        service = self._get_service(account)
        
        # Get the original message
        try:
            original = service.users().messages().get(
                userId="me", id=external_message_id, format="full"
            ).execute()
        except Exception as e:
            raise ValueError(f"Error fetching original message: {str(e)}")
        
        # Parse original message
        payload = original.get("payload", {})
        headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}
        
        # Build forward subject
        original_subject = headers.get("subject", "")
        if not original_subject.startswith("Fwd:") and not original_subject.startswith("Fw:"):
            subject = f"Fwd: {original_subject}"
        else:
            subject = original_subject
        
        # Get original body
        body_html = ""
        if "parts" in payload:
            for part in payload["parts"]:
                if part.get("mimeType") == "text/html":
                    body_data = part.get("body", {}).get("data", "")
                    if body_data:
                        body_html = base64.urlsafe_b64decode(body_data).decode("utf-8")
                        break
        
        # Add forward note if provided
        if note:
            body_html = f"<p>{note}</p><hr>{body_html}"
        
        # Send as new message
        return self.send_message(
            account=account,
            to_addresses=to_addresses,
            subject=subject,
            body_html=body_html,
            cc_addresses=cc_addresses,
            bcc_addresses=bcc_addresses,
        )

    def send_message(
        self,
        account: Account,
        to_addresses: List[str],
        subject: str,
        body_html: str,
        cc_addresses: List[str] = None,
        bcc_addresses: List[str] = None,
        reply_to_message_id: str = None,
    ) -> dict:
        """Send an email via Gmail API"""
        import email.mime.text
        import email.mime.multipart

        service = self._get_service(account)

        # Create message
        message = email.mime.multipart.MIMEMultipart("alternative")
        message["to"] = ", ".join(to_addresses)
        message["subject"] = subject
        if cc_addresses:
            message["cc"] = ", ".join(cc_addresses)
        if bcc_addresses:
            message["bcc"] = ", ".join(bcc_addresses)
        if reply_to_message_id:
            # Get original message for In-Reply-To header
            try:
                original = service.users().messages().get(
                    userId="me", id=reply_to_message_id, format="metadata"
                ).execute()
                headers = {h["name"].lower(): h["value"] for h in original.get("payload", {}).get("headers", [])}
                message["In-Reply-To"] = headers.get("message-id", "")
                message["References"] = headers.get("references", "")
            except Exception:
                pass

        # Add HTML body
        html_part = email.mime.text.MIMEText(body_html, "html")
        message.attach(html_part)

        # Encode message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

        try:
            # Send message
            sent_message = (
                service.users()
                .messages()
                .send(userId="me", body={"raw": raw_message})
                .execute()
            )
            return {"id": sent_message["id"], "threadId": sent_message.get("threadId")}
        except Exception as e:
            raise ValueError(f"Error sending Gmail message: {str(e)}")

    def send_draft(self, account: Account, draft_id: int) -> dict:
        """Send a draft email"""
        draft = Draft.objects.get(pk=draft_id, account=account)
        service = self._get_service(account)
        
        try:
            # If draft doesn't exist in Gmail, send as new message instead
            if not draft.external_draft_id:
                # Send as new message
                return self.send_message(
                    account=account,
                    to_addresses=draft.to_addresses or [],
                    subject=draft.subject or "",
                    body_html=draft.body_html or "",
                    cc_addresses=draft.cc_addresses or [],
                    bcc_addresses=draft.bcc_addresses or [],
                )
            
            # Send existing draft
            sent_message = (
                service.users()
                .drafts()
                .send(userId="me", body={"id": draft.external_draft_id})
                .execute()
            )
            return {"id": sent_message["id"], "threadId": sent_message.get("threadId")}
        except Exception as e:
            raise ValueError(f"Error sending draft: {str(e)}")

    def create_draft(self, account: Account, draft) -> Draft:
        """Create or update a draft in Gmail"""
        import email.mime.text
        import email.mime.multipart

        service = self._get_service(account)

        # Create message
        message = email.mime.multipart.MIMEMultipart("alternative")
        message["to"] = ", ".join(draft.to_addresses or [])
        message["subject"] = draft.subject or ""
        if draft.cc_addresses:
            message["cc"] = ", ".join(draft.cc_addresses)
        if draft.bcc_addresses:
            message["bcc"] = ", ".join(draft.bcc_addresses)

        # Add HTML body
        html_part = email.mime.text.MIMEText(draft.body_html or "", "html")
        message.attach(html_part)

        # Encode message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

        try:
            # Create draft
            draft_obj = (
                service.users()
                .drafts()
                .create(userId="me", body={"message": {"raw": raw_message}})
                .execute()
            )
            draft.external_draft_id = draft_obj["id"]
            draft.save()
            return draft
        except Exception as e:
            raise ValueError(f"Error creating Gmail draft: {str(e)}")


class MicrosoftService(EmailProviderService):
    """Microsoft Graph Mail API service for fetching emails"""

    def _get_headers(self, account: Account):
        """Get authenticated headers for Microsoft Graph API"""
        credentials = MicrosoftEmailOAuthService.get_valid_credentials(account)
        if not credentials:
            raise ValueError(f"Account {account} is not connected or token is invalid")
        
        return {
            "Authorization": f"Bearer {credentials['access_token']}",
            "Content-Type": "application/json",
        }

    def _parse_message(self, msg_data: dict) -> dict:
        """Parse Microsoft Graph API message format"""
        headers = {h["name"].lower(): h["value"] for h in msg_data.get("internetMessageHeaders", [])}

        # Extract addresses
        def parse_addresses(address_obj: dict) -> List[str]:
            """Parse Microsoft Graph address object"""
            if not address_obj:
                return []
            if isinstance(address_obj, list):
                return [addr.get("emailAddress", {}).get("address", "") for addr in address_obj if addr.get("emailAddress", {}).get("address")]
            if isinstance(address_obj, dict) and "emailAddress" in address_obj:
                email_addr = address_obj["emailAddress"].get("address", "")
                return [email_addr] if email_addr else []
            return []

        # Get body
        body_html = msg_data.get("body", {}).get("content", "")
        body_type = msg_data.get("body", {}).get("contentType", "")
        
        # If body is plain text, wrap in pre
        if body_type == "text" and body_html:
            body_html = f"<pre>{body_html}</pre>"

        # Parse date
        date_sent = None
        if msg_data.get("sentDateTime"):
            try:
                date_sent = datetime.fromisoformat(msg_data["sentDateTime"].replace("Z", "+00:00"))
            except Exception:
                pass

        # Get from address
        from_obj = msg_data.get("from", {})
        from_address = from_obj.get("emailAddress", {}).get("address", "") if from_obj else ""
        from_name = from_obj.get("emailAddress", {}).get("name", "") if from_obj else ""

        return {
            "external_message_id": msg_data["id"],
            "external_thread_id": msg_data.get("conversationId", ""),
            "subject": msg_data.get("subject", ""),
            "from_address": from_address,
            "from_name": from_name,
            "to_addresses": parse_addresses(msg_data.get("toRecipients", [])),
            "cc_addresses": parse_addresses(msg_data.get("ccRecipients", [])),
            "bcc_addresses": parse_addresses(msg_data.get("bccRecipients", [])),
            "date_sent": date_sent,
            "body_html": body_html or "",
        }

    def fetch_messages(
        self, account: Account, max_results: int = 50, since: Optional[datetime] = None
    ) -> List[dict]:
        """Fetch messages from Microsoft - only received emails (inbox)"""
        headers = self._get_headers(account)

        # Build filter query - get all emails from inbox (not just unread)
        filter_parts = []
        
        if since:
            # Microsoft Graph filter format: sentDateTime ge YYYY-MM-DDTHH:MM:SSZ
            filter_parts.append(f"sentDateTime ge {since.strftime('%Y-%m-%dT%H:%M:%SZ')}")

        filter_query = " and ".join(filter_parts) if filter_parts else None

        params = {
            "$top": max_results,
            "$orderby": "sentDateTime desc",
        }
        if filter_query:
            params["$filter"] = filter_query

        try:
            # Get messages from inbox
            response = requests.get(
                "https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages",
                headers=headers,
                params=params,
            )
            response.raise_for_status()
            
            messages_data = response.json()
            messages = messages_data.get("value", [])

            parsed_messages = []
            for msg in messages:
                # Get full message details
                msg_id = msg["id"]
                msg_response = requests.get(
                    f"https://graph.microsoft.com/v1.0/me/messages/{msg_id}",
                    headers=headers,
                )
                msg_response.raise_for_status()
                msg_data = msg_response.json()
                parsed_messages.append(self._parse_message(msg_data))

            return parsed_messages
        except Exception as e:
            raise ValueError(f"Error fetching Microsoft messages: {str(e)}")

    def get_message(self, account: Account, external_message_id: str) -> dict:
        """Get a single message by ID"""
        headers = self._get_headers(account)
        try:
            response = requests.get(
                f"https://graph.microsoft.com/v1.0/me/messages/{external_message_id}",
                headers=headers,
            )
            response.raise_for_status()
            msg_data = response.json()
            return self._parse_message(msg_data)
        except Exception as e:
            raise ValueError(f"Error fetching Microsoft message: {str(e)}")


class EmailSyncService:
    """Service for syncing emails from providers to database"""

    def __init__(self):
        self.providers = {
            "gmail": GmailService(),
            "microsoft": MicrosoftService(),
        }

    def sync_account(self, account: Account, max_results: int = 50) -> dict:
        """Sync emails for an account"""
        if not account.is_connected:
            raise ValueError(f"Account {account} is not connected")

        provider_service = self.providers.get(account.provider)
        if not provider_service:
            raise ValueError(f"Unsupported provider: {account.provider}")

        # Get last sync time
        since = account.last_synced_at

        # Fetch messages
        messages = provider_service.fetch_messages(account, max_results=max_results, since=since)

        # Store in database
        created_count = 0
        updated_count = 0
        synced_email_ids = []  # Track which emails were synced in this batch

        with transaction.atomic():
            for msg_data in messages:
                # Get or create thread
                # If thread ID is missing/empty, use message ID as fallback to ensure unique threads
                external_thread_id = msg_data["external_thread_id"]
                if not external_thread_id or external_thread_id.strip() == "":
                    # Use message ID as thread ID to ensure each email gets its own thread
                    external_thread_id = f"single-{msg_data['external_message_id']}"
                
                thread, _ = EmailThread.objects.get_or_create(
                    account=account,
                    external_thread_id=external_thread_id,
                )

                # Get or create message
                email_msg, created = EmailMessage.objects.update_or_create(
                    account=account,
                    external_message_id=msg_data["external_message_id"],
                    defaults={
                        "thread": thread,
                        "subject": msg_data["subject"],
                        "from_address": msg_data["from_address"],
                        "from_name": msg_data["from_name"],
                        "to_addresses": msg_data["to_addresses"],
                        "cc_addresses": msg_data["cc_addresses"],
                        "bcc_addresses": msg_data["bcc_addresses"],
                        "date_sent": msg_data["date_sent"],
                        "body_html": msg_data["body_html"],
                    },
                )

                # Track this email as synced in this batch
                synced_email_ids.append(email_msg.pk)

                if created:
                    created_count += 1
                else:
                    updated_count += 1

            # Update last_synced_at
            account.last_synced_at = timezone.now()
            account.save(update_fields=["last_synced_at"])

        return {
            "created": created_count,
            "updated": updated_count,
            "total": len(messages),
            "synced_email_ids": synced_email_ids,  # Return list of synced email IDs
        }
