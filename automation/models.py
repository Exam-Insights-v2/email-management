from django.db import models


class Label(models.Model):
    account = models.ForeignKey(
        "accounts.Account", on_delete=models.CASCADE, related_name="labels"
    )
    name = models.CharField(max_length=255)
    prompt = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("account", "name"),)
        ordering = ["name"]

    def __str__(self):
        return self.name


class EmailLabel(models.Model):
    email_message = models.ForeignKey(
        "mail.EmailMessage", on_delete=models.CASCADE, related_name="labels"
    )
    label = models.ForeignKey(
        Label, on_delete=models.CASCADE, related_name="email_labels"
    )

    class Meta:
        unique_together = (("email_message", "label"),)
        indexes = [
            models.Index(fields=["label"]),
            models.Index(fields=["email_message"]),
        ]

    def __str__(self):
        return f"{self.label.name} on {self.email_message}"


class Action(models.Model):
    account = models.ForeignKey(
        "accounts.Account", on_delete=models.CASCADE, related_name="actions"
    )
    name = models.CharField(max_length=255)
    function = models.CharField(max_length=64)
    instructions = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class LabelAction(models.Model):
    label = models.ForeignKey(
        Label, on_delete=models.CASCADE, related_name="actions"
    )
    action = models.ForeignKey(
        Action, on_delete=models.CASCADE, related_name="label_links"
    )
    order = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = (("label", "action"),)
        ordering = ["order"]
        indexes = [models.Index(fields=["label", "order"])]

    def __str__(self):
        return f"{self.label.name} → {self.action.name} ({self.order})"
