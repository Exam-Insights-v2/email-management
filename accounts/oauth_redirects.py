from django.conf import settings
from django.urls import reverse


def build_oauth_redirect_uri(request, callback_view_name: str) -> str:
    """
    Build a stable OAuth redirect URI.

    Priority:
    1) Provider-specific env override
    2) APP_BASE_URL + callback path
    3) request.build_absolute_uri(callback path) fallback
    """
    override_map = {
        "google_oauth_callback": settings.GOOGLE_OAUTH_REDIRECT_URI,
        "gmail_oauth_callback": settings.GMAIL_OAUTH_REDIRECT_URI,
        "microsoft_oauth_callback": settings.MICROSOFT_OAUTH_REDIRECT_URI,
        "microsoft_email_oauth_callback": settings.MICROSOFT_EMAIL_OAUTH_REDIRECT_URI,
    }
    explicit_uri = (override_map.get(callback_view_name) or "").strip()
    if explicit_uri:
        return explicit_uri

    path = reverse(callback_view_name)
    if settings.APP_BASE_URL:
        return f"{settings.APP_BASE_URL}{path}"

    return request.build_absolute_uri(path)
