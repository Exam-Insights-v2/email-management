from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Provider(models.TextChoices):
    GMAIL = "gmail", "Gmail"
    MICROSOFT = "microsoft", "Microsoft"


class Account(models.Model):
    provider = models.CharField(max_length=32, choices=Provider.choices)
    email = models.EmailField(max_length=255)
    users = models.ManyToManyField(
        User,
        related_name="accounts",
        blank=True,
        help_text="Users who have access to this account"
    )
    signature_html = models.TextField(blank=True, null=True)
    writing_style = models.TextField(blank=True, null=True)
    is_connected = models.BooleanField(default=False)
    last_synced_at = models.DateTimeField(blank=True, null=True)
    sync_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        unique_together = (("provider", "email"),)
        indexes = [models.Index(fields=["provider", "email"])]
        ordering = ["provider", "email"]

    def __str__(self):
        return f"{self.provider} | {self.email}"


class OAuthToken(models.Model):
    """OAuth tokens for email account access (Gmail/Microsoft)"""
    account = models.OneToOneField(
        Account, on_delete=models.CASCADE, related_name="oauth_token"
    )
    access_token = models.TextField()
    refresh_token = models.TextField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    token_type = models.CharField(max_length=32, default="Bearer")
    scopes = models.TextField(
        blank=True,
        help_text="Comma-separated list of OAuth scopes granted with this token",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["account", "expires_at"])]

    def __str__(self):
        return f"Token for {self.account}"

    def is_expired(self):
        if not self.expires_at:
            return False
        from django.utils import timezone
        return timezone.now() >= self.expires_at

    def get_scopes_list(self):
        """Get scopes as a list"""
        if not self.scopes:
            return []
        return [s.strip() for s in self.scopes.split(",") if s.strip()]

    def set_scopes_list(self, scopes_list):
        """Set scopes from a list"""
        self.scopes = ",".join(scopes_list) if scopes_list else ""


class NotificationPreference(models.Model):
    """Per-user notification preferences for an account."""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notification_preferences"
    )
    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name="notification_preferences"
    )
    task_push_enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("user", "account"),)
        indexes = [models.Index(fields=["user", "account"])]

    def __str__(self):
        return f"NotificationPreference<{self.user_id}:{self.account_id}>"


class BrowserPushSubscription(models.Model):
    """Web Push subscription per browser/device endpoint."""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="push_subscriptions"
    )
    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name="push_subscriptions"
    )
    endpoint = models.URLField(max_length=1024)
    p256dh = models.TextField()
    auth = models.TextField()
    user_agent = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    last_active_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("user", "account", "endpoint"),)
        indexes = [
            models.Index(fields=["user", "account", "is_active"]),
            models.Index(fields=["account", "is_active"]),
        ]

    def __str__(self):
        return f"PushSubscription<{self.user_id}:{self.account_id}>"
