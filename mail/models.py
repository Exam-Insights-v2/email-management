from django.db import models


class EmailThread(models.Model):
    account = models.ForeignKey(
        "accounts.Account", on_delete=models.CASCADE, related_name="email_threads"
    )
    external_thread_id = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("account", "external_thread_id"),)
        indexes = [models.Index(fields=["account", "external_thread_id"])]
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.external_thread_id} ({self.account})"


class EmailMessage(models.Model):
    account = models.ForeignKey(
        "accounts.Account", on_delete=models.CASCADE, related_name="email_messages"
    )
    thread = models.ForeignKey(
        EmailThread, on_delete=models.CASCADE, related_name="messages"
    )
    external_message_id = models.CharField(max_length=255)
    subject = models.CharField(max_length=512, blank=True, null=True)
    from_address = models.CharField(max_length=255)
    from_name = models.CharField(max_length=255, blank=True, null=True)
    to_addresses = models.JSONField(default=list)
    cc_addresses = models.JSONField(default=list, blank=True, null=True)
    bcc_addresses = models.JSONField(default=list, blank=True, null=True)
    date_sent = models.DateTimeField(blank=True, null=True)
    body_html = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("account", "external_message_id"),)
        indexes = [
            models.Index(fields=["account", "external_message_id"]),
            models.Index(fields=["account", "date_sent"]),
            models.Index(fields=["account", "from_address"]),
        ]
        ordering = ["-date_sent", "-created_at"]

    def __str__(self):
        return self.subject or self.external_message_id


class Draft(models.Model):
    account = models.ForeignKey(
        "accounts.Account", on_delete=models.CASCADE, related_name="drafts"
    )
    email_message = models.ForeignKey(
        EmailMessage,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="drafts",
    )
    external_draft_id = models.CharField(max_length=255, blank=True, null=True)
    to_addresses = models.JSONField(default=list, blank=True)
    cc_addresses = models.JSONField(default=list, blank=True)
    bcc_addresses = models.JSONField(default=list, blank=True)
    subject = models.CharField(max_length=512, blank=True, null=True)
    body_html = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["account", "external_draft_id"]),
            models.Index(fields=["email_message"]),
        ]
        ordering = ["-updated_at"]

    def __str__(self):
        return self.subject or f"Draft {self.pk}"

    @property
    def effective_to_addresses(self):
        """Recipients for sending; for replies with no To set, use original sender."""
        if self.to_addresses:
            return list(self.to_addresses)
        if self.email_message_id and self.email_message:
            return [self.email_message.from_address]
        return []


class DraftAttachment(models.Model):
    draft = models.ForeignKey(
        Draft, on_delete=models.CASCADE, related_name="attachments"
    )
    filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=128)
    size_bytes = models.PositiveIntegerField()
    content = models.BinaryField(blank=True, null=True)
    storage_path = models.CharField(max_length=1024, blank=True, null=True)

    class Meta:
        indexes = [models.Index(fields=["draft"])]

    def __str__(self):
        return self.filename


class EmailAttachment(models.Model):
    email_message = models.ForeignKey(
        EmailMessage, on_delete=models.CASCADE, related_name="attachments"
    )
    provider_attachment_id = models.CharField(max_length=255, blank=True, null=True)
    filename = models.CharField(max_length=255, blank=True, default="")
    content_type = models.CharField(max_length=128, blank=True, default="")
    size_bytes = models.PositiveIntegerField(default=0)
    is_inline = models.BooleanField(default=False)
    content_id = models.CharField(max_length=255, blank=True, null=True)
    content = models.BinaryField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["email_message"]),
            models.Index(fields=["provider_attachment_id"]),
        ]
        ordering = ["filename", "pk"]

    def __str__(self):
        return self.filename or f"Attachment {self.pk}"


class SyncRun(models.Model):
    """
    Audit record for an onboarding/sync run. Used to inspect which emails were seen,
    stored, and queued for processing (see show_onboarding_trace, explain_email).
    """
    class Phase(models.TextChoices):
        BOOTSTRAP = "bootstrap", "Bootstrap (post-connect)"
        FULL = "full", "Full sync (Celery)"

    account = models.ForeignKey(
        "accounts.Account", on_delete=models.CASCADE, related_name="sync_runs"
    )
    phase = models.CharField(max_length=32, choices=Phase.choices)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    params = models.JSONField(default=dict, blank=True)
    gmail_query = models.CharField(max_length=512, blank=True)
    message_ids_from_provider = models.JSONField(default=list, blank=True)
    synced_email_ids = models.JSONField(default=list, blank=True)
    thread_backfill_stats = models.JSONField(default=dict, blank=True)
    emails_queued_for_processing = models.JSONField(default=list, blank=True)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ["-finished_at", "-started_at"]
        indexes = [models.Index(fields=["account", "finished_at"])]

    def __str__(self):
        return f"SyncRun {self.phase} account={self.account_id} at {self.finished_at}"
