import json
import logging
import os
import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse

from accounts.models import Account, Provider

logger = logging.getLogger(__name__)
from accounts.services import (
    GoogleOAuthService,
    MicrosoftOAuthService,
    GmailOAuthService,
    MicrosoftEmailOAuthService,
)
from automation.utils import setup_account_automation
from mail.onboarding import trigger_sync_after_connect


def login_view(request):
    """Show login page"""
    if request.user.is_authenticated:
        return redirect("/")

    return render(request, "account/login.html")


def google_oauth_login(request):
    """Initiate Google OAuth for user login and email account connection"""
    if request.user.is_authenticated:
        return redirect("/")

    redirect_uri = request.build_absolute_uri(reverse("google_oauth_callback"))
    try:
        # Request both login and Gmail scopes to automatically connect email account
        combined_scopes = GoogleOAuthService.LOGIN_SCOPES + GoogleOAuthService.GMAIL_SCOPES
        auth_url, state = GoogleOAuthService.get_authorization_url(
            redirect_uri, scopes=combined_scopes
        )
        # Store state in session for verification
        request.session["oauth_state"] = state
        request.session["oauth_purpose"] = "login"
        return redirect(auth_url)
    except Exception as e:
        messages.error(request, f"Error initiating login: {str(e)}")
        return redirect("login")


def google_oauth_callback(request):
    """Handle Google OAuth callback for user login and automatic email account connection"""
    code = request.GET.get("code")
    error = request.GET.get("error")

    if error:
        messages.error(request, f"OAuth error: {error}")
        return redirect("login")

    if not code:
        messages.error(request, "No authorization code received.")
        return redirect("login")

    # Verify this is a login callback
    purpose = request.session.get("oauth_purpose")
    if purpose != "login":
        messages.error(request, "Invalid OAuth session.")
        return redirect("login")

    redirect_uri = request.build_absolute_uri(reverse("google_oauth_callback"))
    try:
        # Exchange code for token with combined scopes
        combined_scopes = GoogleOAuthService.LOGIN_SCOPES + GoogleOAuthService.GMAIL_SCOPES
        credentials = GoogleOAuthService.exchange_code_for_token(
            code, redirect_uri, scopes=combined_scopes
        )

        # Create or update user
        user = GoogleOAuthService.create_or_update_user(credentials)

        # Log the user in
        login(request, user)

        # Automatically connect Gmail account
        try:
            # Get email from user info
            user_email = user.email

            # Get or create account
            account, created = Account.objects.get_or_create(
                provider=Provider.GMAIL,
                email=user_email,
                defaults={"sync_enabled": True}
            )

            # Link account to user
            if user not in account.users.all():
                account.users.add(user)

            # Save OAuth token if account is not already connected
            if not account.is_connected:
                GmailOAuthService.save_token(account, credentials)

                # Set up recommended labels and actions for new accounts
                if created:
                    from automation.utils import setup_account_automation
                    setup_account_automation(account)
                
                from mail.onboarding import trigger_sync_after_connect
                ok, _ = trigger_sync_after_connect(account)
                if ok:
                    messages.success(request, f"Welcome, {user.email}! Your Gmail account has been connected. Syncing emails...")
                else:
                    messages.success(request, f"Welcome, {user.email}! Your Gmail account has been connected. (Email sync will start shortly)")
            else:
                messages.success(request, f"Welcome, {user.email}!")
        except Exception as account_error:
            # Log error but don't fail login if account connection fails
            logger.error("Error connecting Gmail account during login: %s", account_error)
            messages.success(request, f"Welcome, {user.email}! (Note: Email account connection had an issue - you can connect it manually in Settings)")

        return redirect("/")
    except Exception as e:
        messages.error(request, f"Error during login: {str(e)}")
        return redirect("login")
    finally:
        # Clean up session
        request.session.pop("oauth_state", None)
        request.session.pop("oauth_purpose", None)


def microsoft_oauth_login(request):
    """Initiate Microsoft OAuth for user login and email account connection"""
    if request.user.is_authenticated:
        return redirect("/")

    redirect_uri = request.build_absolute_uri(reverse("microsoft_oauth_callback"))
    try:
        # Request both login and Mail scopes to automatically connect email account
        combined_scopes = MicrosoftOAuthService.LOGIN_SCOPES + MicrosoftOAuthService.MAIL_SCOPES
        auth_url, state = MicrosoftOAuthService.get_authorization_url(
            redirect_uri, scopes=combined_scopes
        )
        # Store state in session for verification
        request.session["oauth_state"] = state
        request.session["oauth_purpose"] = "login"
        return redirect(auth_url)
    except Exception as e:
        messages.error(request, f"Error initiating login: {str(e)}")
        return redirect("login")


def microsoft_oauth_callback(request):
    """Handle Microsoft OAuth callback for user login and automatic email account connection"""
    code = request.GET.get("code")
    error = request.GET.get("error")
    state = request.GET.get("state")

    if error:
        messages.error(request, f"OAuth error: {error}")
        return redirect("login")

    if not code:
        messages.error(request, "No authorization code received.")
        return redirect("login")

    # Verify state
    session_state = request.session.get("oauth_state")
    if not session_state or state != session_state:
        messages.error(request, "Invalid OAuth state.")
        return redirect("login")

    # Verify this is a login callback
    purpose = request.session.get("oauth_purpose")
    if purpose != "login":
        messages.error(request, "Invalid OAuth session.")
        return redirect("login")

    redirect_uri = request.build_absolute_uri(reverse("microsoft_oauth_callback"))
    try:
        # Exchange code for token with combined scopes
        combined_scopes = MicrosoftOAuthService.LOGIN_SCOPES + MicrosoftOAuthService.MAIL_SCOPES
        token_dict = MicrosoftOAuthService.exchange_code_for_token(
            code, redirect_uri, scopes=combined_scopes
        )

        # Create or update user
        user = MicrosoftOAuthService.create_or_update_user(token_dict)

        # Log the user in
        login(request, user)

        # Automatically connect Microsoft email account
        try:
            # Get email from Microsoft Graph API (more reliable than user.email)
            user_info = MicrosoftOAuthService.get_user_info(token_dict)
            user_email = user_info.get("mail") or user_info.get("userPrincipalName") or user.email
            
            # Get or create account
            account, created = Account.objects.get_or_create(
                provider=Provider.MICROSOFT,
                email=user_email,
                defaults={"sync_enabled": True}
            )
            
            # Link account to user
            if user not in account.users.all():
                account.users.add(user)
            
            # Save OAuth token if account is not already connected
            if not account.is_connected:
                MicrosoftEmailOAuthService.save_token(account, token_dict)
                
                # Set up recommended labels and actions for new accounts
                if created:
                    setup_account_automation(account)
                
                ok, _ = trigger_sync_after_connect(account)
                if ok:
                    messages.success(request, f"Welcome, {user.email}! Your Microsoft email account has been connected. Syncing emails...")
                else:
                    messages.success(request, f"Welcome, {user.email}! Your Microsoft email account has been connected. (Email sync will start shortly)")
            else:
                messages.success(request, f"Welcome, {user.email}!")
        except Exception as account_error:
            # Log error but don't fail login if account connection fails
            logger.error("Error connecting Microsoft account during login: %s", account_error)
            messages.success(request, f"Welcome, {user.email}! (Note: Email account connection had an issue - you can connect it manually in Settings)")

        return redirect("/")
    except Exception as e:
        messages.error(request, f"Error during login: {str(e)}")
        return redirect("login")
    finally:
        # Clean up session
        request.session.pop("oauth_state", None)
        request.session.pop("oauth_purpose", None)


@login_required
def logout_view(request):
    """Log out the user"""
    from django.contrib.auth import logout

    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("login")
