from django.db import models
from django.db.models import Max
from django.db import transaction


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
    account_task_number = models.PositiveIntegerField(db_index=True)
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
            models.Index(fields=["account", "account_task_number"]),
            models.Index(fields=["due_at"]),
            models.Index(fields=["email_message"]),
            models.Index(fields=["job"]),
        ]
        unique_together = [["account", "account_task_number"]]
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        # Auto-generate account_task_number if not set and account exists
        # Get account_id - try multiple ways to ensure we get it
        account_id = getattr(self, 'account_id', None)
        if not account_id and hasattr(self, 'account') and self.account:
            # If account is a model instance, get its pk
            if hasattr(self.account, 'pk'):
                account_id = self.account.pk
            elif hasattr(self.account, 'id'):
                account_id = self.account.id
        
        if not self.account_task_number and account_id:
            try:
                # Check if we're already in a transaction
                from django.db import connection
                in_atomic = connection.in_atomic_block
                
                if in_atomic:
                    # Already in transaction, use select_for_update directly
                    max_number = Task.objects.filter(
                        account_id=account_id
                    ).select_for_update().aggregate(
                        Max("account_task_number")
                    )["account_task_number__max"]
                else:
                    # Not in transaction, wrap in atomic
                    with transaction.atomic():
                        max_number = Task.objects.filter(
                            account_id=account_id
                        ).select_for_update().aggregate(
                            Max("account_task_number")
                        )["account_task_number__max"]
                
                # Set to 1 if no tasks exist for this account, otherwise increment
                self.account_task_number = (max_number or 0) + 1
            except Exception as e:
                # Fallback: just get max without locking (less safe but will work)
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Error generating account_task_number with locking: {e}. Using fallback method.")
                max_number = Task.objects.filter(
                    account_id=account_id
                ).aggregate(
                    Max("account_task_number")
                )["account_task_number__max"]
                self.account_task_number = (max_number or 0) + 1
        
        # Ensure account_task_number is set before calling super().save()
        if not self.account_task_number and account_id:
            raise ValueError(f"account_task_number must be set before saving Task (account_id={account_id})")
        
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title or f"Task {self.pk}"
