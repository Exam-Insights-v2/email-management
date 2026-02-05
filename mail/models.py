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
