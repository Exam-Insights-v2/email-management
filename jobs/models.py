from django.db import models


class JobStatus(models.TextChoices):
    DRAFT = "draft"
    QUOTED = "quoted"
    WON = "won"
    LOST = "lost"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskStatus(models.TextChoices):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


class Job(models.Model):
    account = models.ForeignKey(
        "accounts.Account", on_delete=models.CASCADE, related_name="jobs"
    )
    title = models.CharField(max_length=255)
    status = models.CharField(max_length=64, choices=JobStatus.choices)
    customer_name = models.JSONField(default=list, blank=True)
    customer_email = models.JSONField(default=list, blank=True)
    site_address = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    dates = models.JSONField(default=list, blank=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["account", "status"]),
            models.Index(fields=["account"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Task(models.Model):
    account = models.ForeignKey(
        "accounts.Account", on_delete=models.CASCADE, related_name="tasks"
    )
    job = models.ForeignKey(
        Job, on_delete=models.SET_NULL, blank=True, null=True, related_name="tasks"
    )
    email_message = models.ForeignKey(
        "mail.EmailMessage",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="tasks",
    )
    thread = models.ForeignKey(
        "mail.EmailThread",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="tasks",
    )
    status = models.CharField(
        max_length=64, choices=TaskStatus.choices, default=TaskStatus.PENDING
    )
    priority = models.SmallIntegerField(default=1)
    title = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    due_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["account", "status"]),
            models.Index(fields=["due_at"]),
            models.Index(fields=["email_message"]),
            models.Index(fields=["job"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return self.title or f"Task {self.pk}"
