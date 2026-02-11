import os
import secrets
import logging
import warnings
from datetime import datetime, timedelta
from typing import Optional, Tuple

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from msal import ConfidentialClientApplication

from accounts.models import Account, OAuthToken, Provider

# Suppress the file_cache warning from oauth2client
warnings.filterwarnings('ignore', message='.*file_cache.*oauth2client.*', category=UserWarning)

# Suppress INFO level logging for oauth2client file_cache messages
# The warning comes from oauth2client library initialization
for logger_name in ['oauth2client', 'oauth2client.client', '__init__']:
    oauth2client_logger = logging.getLogger(logger_name)
    oauth2client_logger.setLevel(logging.WARNING)  # Only show WARNING and above

# Also suppress via logging filter for any logger that contains file_cache messages
class FileCacheFilter(logging.Filter):
    def filter(self, record):
        return 'file_cache' not in str(record.getMessage()).lower()

# Apply filter to root logger to catch all file_cache messages
logging.getLogger().addFilter(FileCacheFilter())

User = get_user_model()


class GoogleOAuthService:
    """Unified OAuth service for both user login and email access"""

    # Scopes for user login (identity only)
    LOGIN_SCOPES = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/userinfo.email",
    ]

    # Scopes for Gmail email access
    GMAIL_SCOPES = [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.modify",  # For drafts
    ]

    @staticmethod
    def get_oauth_flow(redirect_uri: str, scopes: list = None) -> Flow:
        """Create OAuth flow with specified scopes"""
        if scopes is None:
            scopes = GoogleOAuthService.LOGIN_SCOPES

        client_config = {
            "web": {
                "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
                "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri],
            }
        }
        flow = Flow.from_client_config(
            client_config, scopes=scopes, redirect_uri=redirect_uri
        )
        return flow

    @staticmethod
    def get_authorization_url(
        redirect_uri: str, scopes: list = None, force_reauth: bool = False
    ) -> Tuple[str, str]:
        """Get authorization URL and state for OAuth flow

        Args:
            redirect_uri: OAuth redirect URI
            scopes: OAuth scopes to request (defaults to LOGIN_SCOPES)
            force_reauth: If True, force re-authorization even if user previously granted access
        """
        if scopes is None:
            scopes = GoogleOAuthService.LOGIN_SCOPES

        flow = GoogleOAuthService.get_oauth_flow(redirect_uri, scopes)
        prompt = "consent" if force_reauth else "select_account"
        authorization_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="false",
            prompt=prompt,
        )
        return authorization_url, state

    @staticmethod
    def exchange_code_for_token(code: str, redirect_uri: str, scopes: list = None) -> Credentials:
        """Exchange authorization code for access token"""
        if scopes is None:
            scopes = GoogleOAuthService.LOGIN_SCOPES

        flow = GoogleOAuthService.get_oauth_flow(redirect_uri, scopes)
        # Suppress scope mismatch warnings - Google may add additional scopes like 'openid'
        import warnings
        # Configure oauthlib session to not treat scope mismatches as errors
        # Set the session's scope validation to be lenient
        if hasattr(flow.oauth2session, '_client'):
            # Disable strict scope validation
            flow.oauth2session._client._scope_separator = ' '
        
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                try:
                    flow.fetch_token(code=code)
                except Warning as w:
                    # If it's a scope mismatch warning, the credentials might still be valid
                    if "scope" in str(w).lower() and hasattr(flow, 'credentials') and flow.credentials:
                        # Credentials are available despite the warning
                        pass
                    else:
                        raise
        except Warning as w:
            # Scope mismatch warnings are usually harmless - Google adds 'openid' automatically
            if "scope" in str(w).lower():
                # Check if credentials are still available
                if hasattr(flow, 'credentials') and flow.credentials:
                    return flow.credentials
            raise
        return flow.credentials

    @staticmethod
    def get_user_info(credentials: Credentials) -> dict:
        """Get user info from Google OAuth credentials"""
        from googleapiclient.discovery import build

        service = build("oauth2", "v2", credentials=credentials)
        user_info = service.userinfo().get().execute()
        return user_info

    @staticmethod
    def create_or_update_user(credentials: Credentials) -> User:
        """Create or update Django User from Google OAuth"""
        user_info = GoogleOAuthService.get_user_info(credentials)
        email = user_info.get("email")
        first_name = user_info.get("given_name", "")
        last_name = user_info.get("family_name", "")

        if not email:
            raise ValueError("Email not provided by Google")

        # Get or create user
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "username": email,
                "first_name": first_name,
                "last_name": last_name,
            },
        )

        # Update user info if it changed
        if not created:
            updated = False
            if user.first_name != first_name:
                user.first_name = first_name
                updated = True
            if user.last_name != last_name:
                user.last_name = last_name
                updated = True
            if updated:
                user.save()

        return user


class GmailOAuthService:
    """Service for handling Gmail OAuth flow and token management"""

    # Combine Gmail scopes with userinfo scopes to get email address
    # Include 'openid' since Google automatically adds it when using userinfo scopes
    SCOPES = [
        "openid",  # Required when using userinfo scopes
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
    ] + GoogleOAuthService.GMAIL_SCOPES

    @staticmethod
    def get_authorization_url(redirect_uri: str, force_reauth: bool = False) -> Tuple[str, str]:
        """Get authorization URL and state for Gmail OAuth flow"""
        return GoogleOAuthService.get_authorization_url(
            redirect_uri, scopes=GmailOAuthService.SCOPES, force_reauth=force_reauth
        )

    @staticmethod
    def exchange_code_for_token(code: str, redirect_uri: str) -> Credentials:
        """Exchange authorization code for access token"""
        return GoogleOAuthService.exchange_code_for_token(
            code, redirect_uri, scopes=GmailOAuthService.SCOPES
        )

    @staticmethod
    def save_token(account: Account, credentials: Credentials) -> OAuthToken:
        """Save OAuth token to database"""
        expires_at = None
        if credentials.expiry:
            expires_at = credentials.expiry

        # Get the actual scopes granted (may include more than requested)
        granted_scopes = list(credentials.scopes) if credentials.scopes else GmailOAuthService.SCOPES
        scopes_str = ",".join(granted_scopes)

        oauth_token, created = OAuthToken.objects.update_or_create(
            account=account,
            defaults={
                "access_token": credentials.token,
                "refresh_token": credentials.refresh_token or "",
                "expires_at": expires_at,
                "token_type": "Bearer",
                "scopes": scopes_str,
            },
        )
        account.is_connected = True
        account.save(update_fields=["is_connected"])
        return oauth_token

    @staticmethod
    def get_valid_credentials(account: Account) -> Optional[Credentials]:
        """Get valid OAuth credentials, refreshing if necessary"""
        try:
            oauth_token = account.oauth_token
        except OAuthToken.DoesNotExist:
            return None

        # Use the scopes that were originally granted with this token
        # If no scopes stored, fall back to current SCOPES (for backward compatibility)
        token_scopes = oauth_token.get_scopes_list()
        if not token_scopes:
            token_scopes = GmailOAuthService.SCOPES

        # Check if token is expired using both DB expiry and credentials.expired
        # This prevents using expired tokens that might cause 401s
        is_token_expired = oauth_token.is_expired()
        
        # If token is expired and we don't have a refresh token, fail fast
        if is_token_expired and not oauth_token.refresh_token:
            return None

        credentials = Credentials(
            token=oauth_token.access_token,
            refresh_token=oauth_token.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
            client_secret=settings.GOOGLE_OAUTH_CLIENT_SECRET,
            scopes=token_scopes,  # Use stored scopes, not current SCOPES
        )
        
        # Set expiry from DB if available to ensure accurate expiry check
        if oauth_token.expires_at:
            credentials.expiry = oauth_token.expires_at

        # Refresh token if expired (check both DB and credentials object)
        if (is_token_expired or credentials.expired) and credentials.refresh_token:
            try:
                # Refresh the token
                credentials.refresh(Request())
                # Update stored token and scopes (in case they changed)
                oauth_token.access_token = credentials.token
                if credentials.expiry:
                    oauth_token.expires_at = credentials.expiry
                # Update scopes if they changed during refresh
                if credentials.scopes:
                    oauth_token.set_scopes_list(list(credentials.scopes))
                oauth_token.save()
            except Exception as e:
                # If refresh fails, mark account as disconnected to prevent retry loops
                error_str = str(e).lower()
                if any(keyword in error_str for keyword in ["scope", "invalid_grant", "invalid_token", "unauthorized", "401"]):
                    GmailOAuthService.disconnect_account(account)
                return None

        return credentials

    @staticmethod
    def disconnect_account(account: Account):
        """Disconnect account and remove OAuth token"""
        OAuthToken.objects.filter(account=account).delete()
        account.is_connected = False
        account.save(update_fields=["is_connected"])


class MicrosoftOAuthService:
    """Unified OAuth service for both user login and email access"""

    # Scopes for user login (identity only)
    LOGIN_SCOPES = [
        "openid",
        "profile",
        "email",
        "User.Read",
    ]

    # Scopes for Microsoft email access
    MAIL_SCOPES = [
        "Mail.Read",
        "Mail.ReadWrite",  # For drafts
    ]

    @staticmethod
    def get_msal_app(redirect_uri: str, scopes: list = None):
        """Create MSAL ConfidentialClientApplication with specified scopes"""
        if scopes is None:
            scopes = MicrosoftOAuthService.LOGIN_SCOPES

        tenant = settings.MICROSOFT_OAUTH_TENANT_ID
        authority = f"https://login.microsoftonline.com/{tenant}"

        app = ConfidentialClientApplication(
            client_id=settings.MICROSOFT_OAUTH_CLIENT_ID,
            client_credential=settings.MICROSOFT_OAUTH_CLIENT_SECRET,
            authority=authority,
        )
        return app

    @staticmethod
    def get_authorization_url(
        redirect_uri: str, scopes: list = None, force_reauth: bool = False
    ) -> Tuple[str, str]:
        """Get authorization URL and state for OAuth flow

        Args:
            redirect_uri: OAuth redirect URI
            scopes: OAuth scopes to request (defaults to LOGIN_SCOPES)
            force_reauth: If True, force re-authorization even if user previously granted access
        """
        if scopes is None:
            scopes = MicrosoftOAuthService.LOGIN_SCOPES

        app = MicrosoftOAuthService.get_msal_app(redirect_uri, scopes)
        
        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)
        
        # Build authorization URL - MSAL will use the state we provide
        auth_url = app.get_authorization_request_url(
            scopes=scopes,
            redirect_uri=redirect_uri,
            state=state,
            prompt="consent" if force_reauth else "select_account",
        )
        
        # MSAL returns the auth_url, and we use our generated state
        return auth_url, state

    @staticmethod
    def exchange_code_for_token(code: str, redirect_uri: str, scopes: list = None) -> dict:
        """Exchange authorization code for access token"""
        if scopes is None:
            scopes = MicrosoftOAuthService.LOGIN_SCOPES

        app = MicrosoftOAuthService.get_msal_app(redirect_uri, scopes)
        
        # Exchange code for token
        result = app.acquire_token_by_authorization_code(
            code=code,
            scopes=scopes,
            redirect_uri=redirect_uri,
        )
        
        if "error" in result:
            raise ValueError(f"Token exchange failed: {result.get('error_description', result.get('error'))}")
        
        return result

    @staticmethod
    def get_user_info(token_dict: dict) -> dict:
        """Get user info from Microsoft Graph API"""
        access_token = token_dict.get("access_token")
        if not access_token:
            raise ValueError("No access token available")

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        
        response = requests.get("https://graph.microsoft.com/v1.0/me", headers=headers)
        response.raise_for_status()
        
        return response.json()

    @staticmethod
    def create_or_update_user(token_dict: dict) -> User:
        """Create or update Django User from Microsoft OAuth"""
        user_info = MicrosoftOAuthService.get_user_info(token_dict)
        
        # Microsoft Graph API returns 'mail' or 'userPrincipalName' for email
        email = user_info.get("mail") or user_info.get("userPrincipalName")
        first_name = user_info.get("givenName", "")
        last_name = user_info.get("surname", "")

        if not email:
            raise ValueError("Email not provided by Microsoft")

        # Get or create user
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "username": email,
                "first_name": first_name,
                "last_name": last_name,
            },
        )

        # Update user info if it changed
        if not created:
            updated = False
            if user.first_name != first_name:
                user.first_name = first_name
                updated = True
            if user.last_name != last_name:
                user.last_name = last_name
                updated = True
            if updated:
                user.save()

        return user


class MicrosoftEmailOAuthService:
    """Service for handling Microsoft email OAuth flow and token management"""

    # Combine Mail scopes with userinfo scopes to get email address
    SCOPES = [
        "openid",
        "profile",
        "email",
        "User.Read",
        "offline_access",
    ] + MicrosoftOAuthService.MAIL_SCOPES

    @staticmethod
    def get_authorization_url(redirect_uri: str, force_reauth: bool = False) -> Tuple[str, str]:
        """Get authorization URL and state for Microsoft email OAuth flow"""
        return MicrosoftOAuthService.get_authorization_url(
            redirect_uri, scopes=MicrosoftEmailOAuthService.SCOPES, force_reauth=force_reauth
        )

    @staticmethod
    def exchange_code_for_token(code: str, redirect_uri: str) -> dict:
        """Exchange authorization code for access token"""
        return MicrosoftOAuthService.exchange_code_for_token(
            code, redirect_uri, scopes=MicrosoftEmailOAuthService.SCOPES
        )

    @staticmethod
    def save_token(account: Account, token_dict: dict) -> OAuthToken:
        """Save OAuth token to database"""
        access_token = token_dict.get("access_token")
        refresh_token = token_dict.get("refresh_token", "")
        expires_in = token_dict.get("expires_in")
        
        expires_at = None
        if expires_in:
            expires_at = timezone.now() + timedelta(seconds=expires_in)

        # Get the actual scopes granted
        granted_scopes = token_dict.get("scope", "").split() if token_dict.get("scope") else MicrosoftEmailOAuthService.SCOPES
        scopes_str = ",".join(granted_scopes)

        oauth_token, created = OAuthToken.objects.update_or_create(
            account=account,
            defaults={
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at,
                "token_type": "Bearer",
                "scopes": scopes_str,
            },
        )
        account.is_connected = True
        account.save(update_fields=["is_connected"])
        return oauth_token

    @staticmethod
    def get_valid_credentials(account: Account) -> Optional[dict]:
        """Get valid OAuth credentials, refreshing if necessary"""
        try:
            oauth_token = account.oauth_token
        except OAuthToken.DoesNotExist:
            return None

        # Use the scopes that were originally granted with this token
        token_scopes = oauth_token.get_scopes_list()
        if not token_scopes:
            token_scopes = MicrosoftEmailOAuthService.SCOPES

        # Check if token is expired
        is_expired = oauth_token.is_expired()

        # If expired and we have a refresh token, refresh it
        if is_expired and oauth_token.refresh_token:
            try:
                tenant = settings.MICROSOFT_OAUTH_TENANT_ID
                authority = f"https://login.microsoftonline.com/{tenant}"
                
                app = ConfidentialClientApplication(
                    client_id=settings.MICROSOFT_OAUTH_CLIENT_ID,
                    client_credential=settings.MICROSOFT_OAUTH_CLIENT_SECRET,
                    authority=authority,
                )
                
                result = app.acquire_token_by_refresh_token(
                    refresh_token=oauth_token.refresh_token,
                    scopes=token_scopes,
                )
                
                if "error" in result:
                    # If refresh fails, disconnect the account
                    MicrosoftEmailOAuthService.disconnect_account(account)
                    return None
                
                # Update stored token
                access_token = result.get("access_token")
                refresh_token = result.get("refresh_token", oauth_token.refresh_token)
                expires_in = result.get("expires_in")
                
                expires_at = None
                if expires_in:
                    expires_at = timezone.now() + timedelta(seconds=expires_in)
                
                oauth_token.access_token = access_token
                oauth_token.refresh_token = refresh_token
                oauth_token.expires_at = expires_at
                
                # Update scopes if they changed during refresh
                if result.get("scope"):
                    oauth_token.set_scopes_list(result["scope"].split())
                
                oauth_token.save()
                
                return {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "expires_at": expires_at,
                    "token_type": "Bearer",
                }
            except Exception as e:
                # If refresh fails due to scope mismatch, disconnect the account
                if "scope" in str(e).lower() or "invalid_grant" in str(e).lower():
                    MicrosoftEmailOAuthService.disconnect_account(account)
                return None

        # Return current token
        return {
            "access_token": oauth_token.access_token,
            "refresh_token": oauth_token.refresh_token,
            "expires_at": oauth_token.expires_at,
            "token_type": oauth_token.token_type,
        }

    @staticmethod
    def disconnect_account(account: Account):
        """Disconnect account and remove OAuth token"""
        OAuthToken.objects.filter(account=account).delete()
        account.is_connected = False
        account.save(update_fields=["is_connected"])
