from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from rest_framework import viewsets

from .models import Account, Provider
from .serializers import AccountSerializer
from .services import GmailOAuthService


class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.all().order_by("provider", "email")
    serializer_class = AccountSerializer


@login_required
def account_connect_gmail(request):
    """Initiate Gmail OAuth connection"""
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        if not email:
            messages.error(request, "Email address is required.")
            return redirect("accounts_list")

        # Get or create account
        account, created = Account.objects.get_or_create(
            provider=Provider.GMAIL, email=email, defaults={"sync_enabled": True}
        )

        if account.is_connected:
            messages.info(request, f"Account {email} is already connected.")
            return redirect("account_detail", pk=account.pk)

        # Get authorization URL
        redirect_uri = request.build_absolute_uri(reverse("gmail_oauth_callback"))
        try:
            auth_url, state = GmailOAuthService.get_authorization_url(redirect_uri)
            # Store state in session for verification
            request.session["oauth_state"] = state
            request.session["oauth_account_id"] = account.pk
            return redirect(auth_url)
        except Exception as e:
            messages.error(request, f"Error initiating OAuth: {str(e)}")
            return redirect("accounts_list")

    return redirect("accounts_list")


@login_required
def account_gmail_oauth_callback(request):
    """Handle Gmail OAuth callback - get email from OAuth and create/update account"""
    code = request.GET.get("code")
    error = request.GET.get("error")

    if error:
        messages.error(request, f"OAuth error: {error}")
        return redirect("accounts_list")

    if not code:
        messages.error(request, "No authorization code received.")
        return redirect("accounts_list")

    # Exchange code for token
    redirect_uri = request.build_absolute_uri(reverse("gmail_oauth_callback"))
    credentials = None
    
    try:
        credentials = GmailOAuthService.exchange_code_for_token(code, redirect_uri)
    except Warning as w:
        # OAuth scope mismatch warnings - Google may add 'openid' scope automatically
        # These are usually harmless - try to get credentials anyway
        error_msg = str(w)
        if "scope" in error_msg.lower():
            # Log the warning but try to continue - scope mismatches are often harmless
            import logging
            from accounts.services import GoogleOAuthService
            logger = logging.getLogger(__name__)
            logger.warning(f"OAuth scope warning (attempting to continue): {error_msg}")
            # Try to create a new flow and fetch token, ignoring the warning
            try:
                # Use the scopes that Google actually granted (including openid)
                all_scopes = GmailOAuthService.SCOPES
                flow = GoogleOAuthService.get_oauth_flow(redirect_uri, all_scopes)
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    flow.fetch_token(code=code)
                credentials = flow.credentials
            except Exception as e2:
                messages.error(
                    request,
                    f"OAuth error after scope warning: {str(e2)}. Please try connecting again.",
                )
                return redirect("accounts_list")
        else:
            # Non-scope warnings should be treated as errors
            messages.error(request, f"OAuth warning: {error_msg}")
            return redirect("accounts_list")
    
    if not credentials:
        messages.error(request, "Failed to obtain OAuth credentials.")
        return redirect("accounts_list")
    
    try:
        # Get email from Gmail API profile (this works with Gmail scopes)
        email = None
        gmail_error = None
        try:
            from googleapiclient.discovery import build
            gmail_service = build("gmail", "v1", credentials=credentials)
            profile = gmail_service.users().getProfile(userId="me").execute()
            email = profile.get("emailAddress")
        except Exception as e:
            gmail_error = e
            # Fallback: try userinfo API if we have those scopes
            try:
                from accounts.services import GoogleOAuthService
                user_info = GoogleOAuthService.get_user_info(credentials)
                email = user_info.get("email")
            except Exception as userinfo_error:
                import traceback
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Gmail API error: {gmail_error}\nUserinfo API error: {userinfo_error}\n{traceback.format_exc()}")
                messages.error(
                    request, 
                    f"Could not retrieve email address. Gmail API: {str(gmail_error)}. Userinfo API: {str(userinfo_error)}. Please try connecting again."
                )
                return redirect("accounts_list")
        
        if not email:
            messages.error(request, "Could not retrieve email address from Google.")
            return redirect("accounts_list")
        
        # Get or create account with the email from OAuth
        account, created = Account.objects.get_or_create(
            provider=Provider.GMAIL, 
            email=email, 
            defaults={"sync_enabled": True}
        )
        
        # Save the OAuth token
        GmailOAuthService.save_token(account, credentials)
        
        if created:
            messages.success(
                request, f"Successfully connected new Gmail account: {account.email}"
            )
        else:
            messages.success(
                request, f"Successfully reconnected Gmail account: {account.email}"
            )
        return redirect("account_detail", pk=account.pk)
    except Exception as e:
        import traceback
        error_msg = str(e)
        error_traceback = traceback.format_exc()
        
        # Log the full error for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"OAuth callback error: {error_msg}\n{error_traceback}")
        
        # Provide helpful message for scope mismatch errors
        if "scope" in error_msg.lower() or "invalid_grant" in error_msg.lower():
            messages.error(
                request,
                f"OAuth scope error: {error_msg}. Please try connecting again.",
            )
        else:
            messages.error(request, f"Error connecting account: {error_msg}")
        return redirect("accounts_list")
    finally:
        # Clean up session
        request.session.pop("oauth_state", None)
        request.session.pop("oauth_account_id", None)


@login_required
def account_disconnect(request, pk):
    """Disconnect an account"""
    if request.method == "POST":
        try:
            account = Account.objects.get(pk=pk)
            GmailOAuthService.disconnect_account(account)
            messages.success(request, f"Disconnected account: {account.email}")
        except Account.DoesNotExist:
            messages.error(request, "Account not found.")
        except Exception as e:
            messages.error(request, f"Error disconnecting: {str(e)}")

    return redirect("account_detail", pk=pk)


@login_required
def account_sync(request, pk):
    """Manually trigger email sync for an account"""
    if request.method == "POST":
        from mail.tasks import sync_account_emails

        try:
            account = Account.objects.get(pk=pk)
            if not account.is_connected:
                messages.error(request, "Account is not connected.")
            else:
                sync_account_emails.delay(account.pk)
                messages.success(
                    request, f"Sync started for {account.email}. Emails will appear shortly."
                )
        except Account.DoesNotExist:
            messages.error(request, "Account not found.")
        except Exception as e:
            messages.error(request, f"Error starting sync: {str(e)}")

    return redirect("account_detail", pk=pk)
