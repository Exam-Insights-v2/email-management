import base64
import email
import email.utils
import logging
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import List, Optional

import requests
from django.db import transaction
from django.utils import timezone
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from accounts.models import Account
from accounts.services import GmailOAuthService, MicrosoftEmailOAuthService
from mail.models import Draft, EmailMessage, EmailThread

logger = logging.getLogger(__name__)

# Sync caps: first sync can fetch more; incremental is capped per run.
# For large mailboxes, run backfill_inbox_sync to pull more history after first sync.
FIRST_SYNC_MAX_MESSAGES = 500
INCREMENTAL_SYNC_MAX_MESSAGES = 200
PAGE_SIZE = 100  # Gmail max 500; use 100 for balance of requests vs latency


def _since_utc(since: Optional[datetime]) -> Optional[datetime]:
    """Return since as timezone-aware UTC for consistent API use."""
    if since is None:
        return None
    if timezone.is_naive(since):
        since = timezone.make_aware(since)
    return since.astimezone(timezone.utc)


def persist_sent_message(
    account: Account,
    send_result: dict,
    *,
    subject: str = "",
    from_address: str,
    to_addresses: List[str],
    body_html: str = "",
    cc_addresses: Optional[List[str]] = None,
    bcc_addresses: Optional[List[str]] = None,
    date_sent=None,
) -> EmailMessage:
    """
    Persist a sent message to the DB after a Gmail send (draft send, reply, or forward).
    Ensures thread exists (get_or_create) and creates the EmailMessage.
    Returns the created EmailMessage.
    """
    message_id = send_result.get("id", "")
    thread_id = (send_result.get("threadId") or "").strip()
    if not thread_id:
        thread_id = f"single-{message_id}" if message_id else f"single-{timezone.now().timestamp()}"
    thread, _ = EmailThread.objects.get_or_create(
        account=account,
        external_thread_id=thread_id,
    )
    if date_sent is None:
        date_sent = timezone.now()
    return EmailMessage.objects.create(
        account=account,
        thread=thread,
        external_message_id=message_id,
        subject=subject,
        from_address=from_address,
        to_addresses=to_addresses or [],
        cc_addresses=cc_addresses or [],
        bcc_addresses=bcc_addresses or [],
        body_html=body_html,
        date_sent=date_sent,
    )


def _escape_odata_string(value: str) -> str:
    """Escape single quotes for use in OData $filter string literal (double the quote)."""
    return (value or "").replace("'", "''")


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

    def _gmail_request_with_backoff(self, request_fn, max_retries: int = 3):
        """Execute a Gmail API request with exponential backoff on 429/5xx."""
        last_error = None
        for attempt in range(max_retries):
            try:
                return request_fn().execute()
            except HttpError as e:
                last_error = e
                status = getattr(e, "resp", None) and getattr(e.resp, "status", None)
                if status in (429, 500, 502, 503) and attempt < max_retries - 1:
                    delay = (2 ** attempt) + 1
                    time.sleep(delay)
                    continue
                raise
        if last_error:
            raise last_error

    def fetch_messages(
        self,
        account: Account,
        max_results: int = 50,
        since: Optional[datetime] = None,
        max_total: Optional[int] = None,
    ) -> List[dict]:
        """Fetch messages from Gmail: inbox, archived, and sent; excludes only trash and spam.
        Full threads are filled via thread backfill.
        max_total: cap total messages fetched (e.g. 500 for first sync); None = use max_results only (one page).
        """
        service = self._get_service(account)
        since_utc = _since_utc(since)
        query_parts = ["-in:trash", "-in:spam"]
        if since_utc:
            query_parts.append(f"after:{since_utc.strftime('%Y/%m/%d')}")
        query = " ".join(query_parts)
        page_size = min(max_results, PAGE_SIZE)
        cap = max_total if max_total is not None else page_size
        parsed_messages: List[dict] = []
        page_token: Optional[str] = None

        try:
            while len(parsed_messages) < cap:
                list_kwargs = {
                    "userId": "me",
                    "maxResults": min(page_size, cap - len(parsed_messages)),
                    "q": query,
                    "includeSpamTrash": False,
                }
                if page_token:
                    list_kwargs["pageToken"] = page_token
                list_request = service.users().messages().list(**list_kwargs)
                results = self._gmail_request_with_backoff(lambda: list_request)
                messages = results.get("messages", [])
                if not messages:
                    break
                for msg in messages:
                    if len(parsed_messages) >= cap:
                        break
                    msg_id = msg["id"]
                    try:
                        msg_data = self._gmail_request_with_backoff(
                            lambda mid=msg_id: service.users()
                            .messages()
                            .get(userId="me", id=mid, format="full")
                        )
                        parsed_messages.append(self._parse_message(msg_data))
                    except Exception:
                        continue
                page_token = results.get("nextPageToken")
                if not page_token:
                    break
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

    def check_email_status(self, account: Account, external_message_id: str) -> dict:
        """
        Check the status of an email in Gmail (inbox, deleted, archived, spam).
        Returns dict with status information.
        """
        service = self._get_service(account)
        try:
            msg_data = (
                service.users()
                .messages()
                .get(userId="me", id=external_message_id, format="metadata", metadataHeaders=["X-Gmail-Labels"])
                .execute()
            )
            
            # Get labels from the message
            label_ids = msg_data.get("labelIds", [])
            
            # Determine status
            is_in_inbox = "INBOX" in label_ids
            is_deleted = "TRASH" in label_ids
            is_spam = "SPAM" in label_ids
            is_archived = not is_in_inbox and not is_deleted and not is_spam
            
            return {
                "exists": True,
                "in_inbox": is_in_inbox,
                "is_deleted": is_deleted,
                "is_spam": is_spam,
                "is_archived": is_archived,
            }
        except Exception as e:
            # If message not found, it's likely deleted
            error_str = str(e).lower()
            if "not found" in error_str or "404" in error_str:
                return {
                    "exists": False,
                    "in_inbox": False,
                    "is_deleted": True,
                    "is_spam": False,
                    "is_archived": False,
                }
            # Re-raise other errors
            raise ValueError(f"Error checking Gmail message status: {str(e)}")
    
    def get_thread_messages(self, account: Account, external_thread_id: str) -> List[dict]:
        """Get all messages in a thread. Skips messages that fail to parse (logs and continues)."""
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
                msg_id = msg.get("id", "")
                try:
                    messages.append(self._parse_message(msg))
                except Exception:
                    pass
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

    def unarchive_message(self, account: Account, external_message_id: str):
        """Move a message back to inbox (undo archive)"""
        service = self._get_service(account)
        try:
            service.users().messages().modify(
                userId="me",
                id=external_message_id,
                body={"addLabelIds": ["INBOX"]}
            ).execute()
        except Exception as e:
            raise ValueError(f"Error moving message to inbox: {str(e)}")

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
        result = self.send_message(
            account=account,
            to_addresses=to_addresses,
            subject=subject,
            body_html=body_html,
            cc_addresses=cc_addresses,
            bcc_addresses=bcc_addresses,
        )
        # Include metadata so caller can persist the sent message to DB
        result["subject"] = subject
        result["from_address"] = account.email
        result["to_addresses"] = to_addresses
        result["body_html"] = body_html
        result["cc_addresses"] = cc_addresses or []
        result["bcc_addresses"] = bcc_addresses or []
        return result

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

    def _ms_request_with_backoff(self, url: str, headers: dict, params: Optional[dict] = None, max_retries: int = 3):
        """GET with exponential backoff on 429/5xx."""
        last_error = None
        for attempt in range(max_retries):
            try:
                resp = requests.get(url, headers=headers, params=params, timeout=30)
                if resp.status_code in (429, 500, 502, 503) and attempt < max_retries - 1:
                    delay = (2 ** attempt) + 1
                    logger.warning(
                        "[Microsoft] Request failed with %s, retrying in %ds (attempt %d/%d)",
                        resp.status_code, delay, attempt + 1, max_retries,
                    )
                    time.sleep(delay)
                    continue
                resp.raise_for_status()
                return resp
            except requests.RequestException as e:
                last_error = e
                if attempt < max_retries - 1:
                    time.sleep((2 ** attempt) + 1)
                    continue
                raise
        if last_error:
            raise last_error

    def _fetch_folder_messages(
        self,
        headers: dict,
        folder_path: str,
        max_results: int,
        since: Optional[datetime] = None,
        max_total: Optional[int] = None,
    ) -> List[dict]:
        """Fetch and parse messages from a single Microsoft mail folder with pagination and resilience."""
        since_utc = _since_utc(since)
        params = {
            "$top": min(max_results, PAGE_SIZE),
            "$orderby": "sentDateTime desc",
        }
        if since_utc:
            # ISO 8601 in UTC for Graph API
            params["$filter"] = f"sentDateTime ge {since_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}"
        cap = max_total if max_total is not None else max_results
        parsed: List[dict] = []
        url = f"https://graph.microsoft.com/v1.0/me/mailFolders/{folder_path}/messages"

        while len(parsed) < cap:
            resp = self._ms_request_with_backoff(url, headers, params)
            data = resp.json()
            messages = data.get("value", [])
            for msg in messages:
                if len(parsed) >= cap:
                    break
                msg_id = msg.get("id")
                if not msg_id:
                    continue
                try:
                    msg_resp = self._ms_request_with_backoff(
                        f"https://graph.microsoft.com/v1.0/me/messages/{msg_id}",
                        headers,
                    )
                    parsed.append(self._parse_message(msg_resp.json()))
                except Exception as e:
                    logger.warning(
                        "[Microsoft] Skip message %s: %s",
                        msg_id,
                        e,
                        exc_info=False,
                    )
                    continue
            next_link = data.get("@odata.nextLink")
            if not next_link:
                break
            url = next_link
            params = None  # nextLink is full URL
        return parsed

    def fetch_messages(
        self,
        account: Account,
        max_results: int = 50,
        since: Optional[datetime] = None,
        max_total: Optional[int] = None,
    ) -> List[dict]:
        """Fetch messages from Microsoft: inbox and archive (excludes deleted/junk). Sent in threads via thread backfill."""
        headers = self._get_headers(account)
        cap = max_total if max_total is not None else min(max_results, PAGE_SIZE)
        try:
            inbox_list = self._fetch_folder_messages(
                headers, "inbox", max_results, since, max_total=cap
            )
        except Exception as e:
            raise ValueError(f"Error fetching Microsoft messages: {str(e)}")
        try:
            archive_list = self._fetch_folder_messages(
                headers, "archive", max_results, since, max_total=cap
            )
        except Exception:
            archive_list = []
        # Merge by message ID (a message only lives in one folder), sort by date desc, apply cap
        by_id: dict = {}
        for m in inbox_list + archive_list:
            mid = m.get("external_message_id")
            if mid and mid not in by_id:
                by_id[mid] = m
        merged = list(by_id.values())

        def _sort_date(d):
            if d is None:
                return datetime.min.replace(tzinfo=timezone.utc)
            return timezone.make_aware(d) if timezone.is_naive(d) else d

        merged.sort(key=lambda m: _sort_date(m.get("date_sent")), reverse=True)
        return merged[:cap]

    def check_email_status(self, account: Account, external_message_id: str) -> dict:
        """
        Check the status of an email in Microsoft (inbox, deleted, junk).
        Returns dict with status information.
        """
        headers = self._get_headers(account)
        try:
            msg_response = requests.get(
                f"https://graph.microsoft.com/v1.0/me/messages/{external_message_id}",
                headers=headers,
                params={"$select": "id,parentFolderId,isRead"},
            )
            msg_response.raise_for_status()
            msg_data = msg_response.json()
            
            # Get folder info to determine if it's in inbox, deleted, or junk
            folder_id = msg_data.get("parentFolderId")
            
            # Check folder type
            folder_response = requests.get(
                f"https://graph.microsoft.com/v1.0/me/mailFolders/{folder_id}",
                headers=headers,
                params={"$select": "displayName,wellKnownName"},
            )
            folder_data = folder_response.json() if folder_response.status_code == 200 else {}
            folder_name = folder_data.get("wellKnownName") or folder_data.get("displayName", "").lower()
            
            is_in_inbox = folder_name in ["inbox", ""]  # Empty or inbox means inbox
            is_deleted = folder_name in ["deleteditems", "deleted items"]
            is_spam = folder_name in ["junkemail", "junk email", "junk"]
            is_archived = not is_in_inbox and not is_deleted and not is_spam
            
            return {
                "exists": True,
                "in_inbox": is_in_inbox,
                "is_deleted": is_deleted,
                "is_spam": is_spam,
                "is_archived": is_archived,
            }
        except requests.exceptions.HTTPError as e:
            # If message not found (404), it's likely deleted
            if e.response.status_code == 404:
                return {
                    "exists": False,
                    "in_inbox": False,
                    "is_deleted": True,
                    "is_spam": False,
                    "is_archived": False,
                }
            raise ValueError(f"Error checking Microsoft message status: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error checking Microsoft message status: {str(e)}")
    
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

    def get_thread_messages(self, account: Account, external_thread_id: str) -> List[dict]:
        """Get all messages in a conversation (thread) from Microsoft Graph. Includes inbox and sent; skips messages that fail to parse."""
        headers = self._get_headers(account)
        filter_val = f"conversationId eq '{_escape_odata_string(external_thread_id)}'"
        params = {
            "$filter": filter_val,
            "$orderby": "sentDateTime asc",
            "$top": 100,
        }
        try:
            # Fetch from /me/messages (all folders)
            response = requests.get(
                "https://graph.microsoft.com/v1.0/me/messages",
                headers=headers,
                params=params,
            )
            response.raise_for_status()
            messages = response.json().get("value", [])
            # Also fetch from sent folder so sent messages are definitely included
            sent_response = requests.get(
                "https://graph.microsoft.com/v1.0/me/mailFolders/sentitems/messages",
                headers=headers,
                params=params,
            )
            if sent_response.status_code == 200:
                sent_messages = sent_response.json().get("value", [])
                seen_ids = {m["id"] for m in messages}
                for sm in sent_messages:
                    if sm["id"] not in seen_ids:
                        messages.append(sm)
                        seen_ids.add(sm["id"])
            parsed = []
            for msg in messages:
                msg_id = msg.get("id", "")
                try:
                    msg_response = requests.get(
                        f"https://graph.microsoft.com/v1.0/me/messages/{msg_id}",
                        headers=headers,
                    )
                    msg_response.raise_for_status()
                    parsed.append(self._parse_message(msg_response.json()))
                except Exception as e:
                    logger.warning(
                        "[Email Sync] Skip message in thread (fetch/parse failed) thread_id=%s message_id=%s: %s",
                        external_thread_id,
                        msg_id,
                        e,
                        exc_info=True,
                    )
            return parsed
        except Exception as e:
            raise ValueError(f"Error fetching Microsoft thread messages: {str(e)}")


class EmailSyncService:
    """Service for syncing emails from providers to database"""

    def __init__(self):
        self.providers = {
            "gmail": GmailService(),
            "microsoft": MicrosoftService(),
        }
    
    def sync_email_status(self, account: Account, email_messages: List[EmailMessage]) -> dict:
        """
        Check and sync the status of emails that have tasks.
        Updates task status based on email status (deleted/archived/spam).
        
        Args:
            account: The account to check
            email_messages: List of EmailMessage objects to check
            
        Returns:
            dict with counts of updated tasks
        """
        from jobs.models import Task, TaskStatus
        
        provider_service = self.providers.get(account.provider)
        if not provider_service:
            logger.info(f"[Email Status Sync] No provider service for {account.provider}")
            return {"checked": 0, "updated": 0, "errors": 0}
        
        if not hasattr(provider_service, "check_email_status"):
            logger.info(f"[Email Status Sync] Provider {account.provider} doesn't support status checking")
            return {"checked": 0, "updated": 0, "errors": 0}
        
        logger.info(f"[Email Status Sync] Starting status check for {len(email_messages)} emails with tasks (account: {account.email})")
        
        checked_count = 0
        updated_count = 0
        error_count = 0
        
        for email_msg in email_messages:
            # Only check emails that have tasks
            if not email_msg.tasks.exists():
                continue
            
            try:
                logger.info(f"[Email Status Sync] Checking email {email_msg.pk} (external_id: {email_msg.external_message_id}, subject: {email_msg.subject[:50] if email_msg.subject else 'No subject'})")
                
                # Check email status in provider
                status = provider_service.check_email_status(account, email_msg.external_message_id)
                checked_count += 1
                
                logger.info(f"[Email Status Sync] Email {email_msg.pk} status - exists: {status.get('exists')}, in_inbox: {status.get('in_inbox')}, deleted: {status.get('is_deleted')}, spam: {status.get('is_spam')}, archived: {status.get('is_archived')}")
                
                # Determine what to do based on status
                if status.get("is_deleted") or status.get("is_spam"):
                    # Email deleted or marked as spam - mark tasks as cancelled
                    tasks_to_update = email_msg.tasks.filter(status__in=[TaskStatus.PENDING, TaskStatus.IN_PROGRESS])
                    task_count = tasks_to_update.count()
                    tasks_updated = tasks_to_update.update(status=TaskStatus.CANCELLED)
                    if tasks_updated > 0:
                        updated_count += tasks_updated
                        logger.info(f"[Email Status Sync] ✅ Updated {tasks_updated} task(s) to CANCELLED for email {email_msg.pk} (deleted/spam)")
                elif status.get("is_archived") and not status.get("in_inbox"):
                    # Email archived (not in inbox) - mark tasks as done
                    tasks_to_update = email_msg.tasks.filter(status__in=[TaskStatus.PENDING, TaskStatus.IN_PROGRESS])
                    task_count = tasks_to_update.count()
                    tasks_updated = tasks_to_update.update(
                        status=TaskStatus.DONE,
                        completed_at=timezone.now()
                    )
                    if tasks_updated > 0:
                        updated_count += tasks_updated
                        logger.info(f"[Email Status Sync] ✅ Updated {tasks_updated} task(s) to DONE for email {email_msg.pk} (archived)")
                else:
                    logger.info(f"[Email Status Sync] No action needed for email {email_msg.pk} (still in inbox)")
                # If email is back in inbox and task was done/cancelled, we could reactivate it
                # but that might be too aggressive, so we'll leave it as is
                
            except Exception as e:
                error_count += 1
                logger.warning(f"[Email Status Sync] ❌ Error checking status for email {email_msg.pk} ({email_msg.external_message_id}): {e}", exc_info=True)
                continue
        
        logger.info(f"[Email Status Sync] Completed - Checked: {checked_count}, Updated: {updated_count}, Errors: {error_count}")
        
        return {
            "checked": checked_count,
            "updated": updated_count,
            "errors": error_count,
        }

    def sync_account(
        self,
        account: Account,
        max_results: int = 50,
        max_total: Optional[int] = None,
        force_initial: bool = False,
        backfill: bool = False,
    ) -> dict:
        """Sync emails for an account. Uses initial vs incremental caps when max_total not provided.
        backfill=True: ignore last_synced_at and fetch most recent messages (for one-off backfill).
        """
        if not account.is_connected:
            raise ValueError(f"Account {account} is not connected")

        provider_service = self.providers.get(account.provider)
        if not provider_service:
            raise ValueError(f"Unsupported provider: {account.provider}")

        since = None if backfill else account.last_synced_at
        is_initial = force_initial or (since is None)
        if max_total is None:
            from django.conf import settings
            max_total = (
                getattr(settings, "EMAIL_FIRST_SYNC_MAX_MESSAGES", FIRST_SYNC_MAX_MESSAGES)
                if is_initial
                else getattr(
                    settings,
                    "EMAIL_INCREMENTAL_SYNC_MAX_MESSAGES",
                    INCREMENTAL_SYNC_MAX_MESSAGES,
                )
            )
        page_size = min(max_results, PAGE_SIZE)

        messages = provider_service.fetch_messages(
            account,
            max_results=page_size,
            since=since,
            max_total=max_total,
        )

        # Store in database
        created_count = 0
        updated_count = 0
        synced_email_ids = []  # Track which emails were synced in this batch
        thread_ids_to_backfill = set()  # Real thread IDs to fetch in full (excludes single-message threads)

        with transaction.atomic():
            for msg_data in messages:
                # Get or create thread
                # If thread ID is missing/empty, use message ID as fallback to ensure unique threads
                external_thread_id = msg_data["external_thread_id"]
                if not external_thread_id or external_thread_id.strip() == "":
                    # Use message ID as thread ID to ensure each email gets its own thread
                    external_thread_id = f"single-{msg_data['external_message_id']}"
                else:
                    thread_ids_to_backfill.add(external_thread_id)

                thread, thread_created = EmailThread.objects.get_or_create(
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

            # Step 1: When an email comes in, fetch the full thread from Gmail and save every message to the DB.
            # This is the only place we fetch thread messages from the API; the task view only reads from the DB.
            if thread_ids_to_backfill and hasattr(provider_service, "get_thread_messages"):
                for ext_thread_id in thread_ids_to_backfill:
                    try:
                        thread_messages = provider_service.get_thread_messages(account, ext_thread_id)
                    except Exception:
                        continue
                    thread, _ = EmailThread.objects.get_or_create(
                        account=account,
                        external_thread_id=ext_thread_id,
                    )
                    saved_in_thread = 0
                    for m in thread_messages:
                        try:
                            EmailMessage.objects.update_or_create(
                                account=account,
                                external_message_id=m["external_message_id"],
                                defaults={
                                    "thread": thread,
                                    "subject": m.get("subject") or "",
                                    "from_address": m.get("from_address") or "",
                                    "from_name": m.get("from_name") or "",
                                    "to_addresses": m.get("to_addresses") or [],
                                    "cc_addresses": m.get("cc_addresses") or [],
                                    "bcc_addresses": m.get("bcc_addresses") or [],
                                    "date_sent": m.get("date_sent"),
                                    "body_html": m.get("body_html") or "",
                                },
                            )
                            saved_in_thread += 1
                        except Exception:
                            pass

            account.last_synced_at = timezone.now()
            account.save(update_fields=["last_synced_at"])

        return {
            "created": created_count,
            "updated": updated_count,
            "total": len(messages),
            "synced_email_ids": synced_email_ids,  # Return list of synced email IDs
        }
