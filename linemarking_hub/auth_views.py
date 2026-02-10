from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse

from accounts.services import GoogleOAuthService, MicrosoftOAuthService


def login_view(request):
    """Show login page"""
    if request.user.is_authenticated:
        return redirect("/")

    return render(request, "account/login.html")


def google_oauth_login(request):
    """Initiate Google OAuth for user login"""
    if request.user.is_authenticated:
        return redirect("/")

    redirect_uri = request.build_absolute_uri(reverse("google_oauth_callback"))
    try:
        auth_url, state = GoogleOAuthService.get_authorization_url(
            redirect_uri, scopes=GoogleOAuthService.LOGIN_SCOPES
        )
        # Store state in session for verification
        request.session["oauth_state"] = state
        request.session["oauth_purpose"] = "login"
        return redirect(auth_url)
    except Exception as e:
        messages.error(request, f"Error initiating login: {str(e)}")
        return redirect("login")


def google_oauth_callback(request):
    """Handle Google OAuth callback for user login"""
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
        # Exchange code for token
        credentials = GoogleOAuthService.exchange_code_for_token(
            code, redirect_uri, scopes=GoogleOAuthService.LOGIN_SCOPES
        )

        # Create or update user
        user = GoogleOAuthService.create_or_update_user(credentials)

        # Log the user in
        login(request, user)

        messages.success(request, f"Welcome, {user.email}!")
        return redirect("/")
    except Exception as e:
        messages.error(request, f"Error during login: {str(e)}")
        return redirect("login")
    finally:
        # Clean up session
        request.session.pop("oauth_state", None)
        request.session.pop("oauth_purpose", None)


def microsoft_oauth_login(request):
    """Initiate Microsoft OAuth for user login"""
    if request.user.is_authenticated:
        return redirect("/")

    redirect_uri = request.build_absolute_uri(reverse("microsoft_oauth_callback"))
    try:
        auth_url, state = MicrosoftOAuthService.get_authorization_url(
            redirect_uri, scopes=MicrosoftOAuthService.LOGIN_SCOPES
        )
        # Store state in session for verification
        request.session["oauth_state"] = state
        request.session["oauth_purpose"] = "login"
        return redirect(auth_url)
    except Exception as e:
        messages.error(request, f"Error initiating login: {str(e)}")
        return redirect("login")


def microsoft_oauth_callback(request):
    """Handle Microsoft OAuth callback for user login"""
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
        # Exchange code for token
        token_dict = MicrosoftOAuthService.exchange_code_for_token(
            code, redirect_uri, scopes=MicrosoftOAuthService.LOGIN_SCOPES
        )

        # Create or update user
        user = MicrosoftOAuthService.create_or_update_user(token_dict)

        # Log the user in
        login(request, user)

        messages.success(request, f"Welcome, {user.email}!")
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
