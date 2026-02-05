from django.db import models


class Label(models.Model):
    account = models.ForeignKey(
        "accounts.Account", on_delete=models.CASCADE, related_name="labels"
    )
    name = models.CharField(max_length=255)
    prompt = models.TextField(blank=True, null=True)
    sop_context = models.TextField(
        blank=True,
        null=True,
        help_text="Additional SOP context specific to this label"
    )
    use_mcp = models.BooleanField(
        default=False,
        help_text="Use MCP for dynamic action orchestration instead of sequential execution"
    )
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
    mcp_tool_name = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        help_text="MCP tool name (if different from function). If set, action is exposed as MCP tool."
    )
    tool_description = models.TextField(
        blank=True,
        null=True,
        help_text="Description for MCP tool (used when action is exposed as MCP tool)"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def effective_tool_name(self):
        """Get the tool name to use for MCP (mcp_tool_name or function)"""
        return self.mcp_tool_name or self.function


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


class StandardOperatingProcedure(models.Model):
    """SOPs that guide AI decision-making for actions"""
    account = models.ForeignKey(
        "accounts.Account", on_delete=models.CASCADE, related_name="sops"
    )
    name = models.CharField(max_length=255)
    description = models.TextField(help_text="When this SOP applies")
    instructions = models.TextField(help_text="What the AI should do when this SOP applies")
    priority = models.PositiveIntegerField(
        default=1,
        help_text="Higher priority SOPs are considered first"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-priority", "name"]
        verbose_name = "Standard Operating Procedure"
        verbose_name_plural = "Standard Operating Procedures"

    def __str__(self):
        return self.name
