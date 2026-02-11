from django.db import models


class Label(models.Model):
    """Smart Rules: Combine email classification with business logic and actions"""
    account = models.ForeignKey(
        "accounts.Account", 
        on_delete=models.CASCADE, 
        related_name="owned_labels",
        help_text="The account that owns/created this label"
    )
    accounts = models.ManyToManyField(
        "accounts.Account",
        related_name="available_labels",
        blank=True,
        help_text="Accounts that can use this label for classification. If empty, only the owner account can use it."
    )
    name = models.CharField(max_length=255)
    prompt = models.TextField(
        blank=True,
        null=True,
        help_text="When this label applies (classification criteria)"
    )
    instructions = models.TextField(
        blank=True,
        null=True,
        help_text="What the AI should do when this label applies (business logic)"
    )
    priority = models.PositiveIntegerField(
        default=1,
        help_text="Higher priority labels are considered first when multiple labels match"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Only active labels will trigger actions"
    )
    actions = models.ManyToManyField(
        "Action",
        related_name="labels",
        blank=True,
        help_text="Actions that can be executed when this label is applied"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("account", "name"),)
        ordering = ["-priority", "name"]

    def __str__(self):
        return self.name
    
    def get_available_accounts(self):
        """Get all accounts that can use this label (owner + accounts in ManyToMany)"""
        accounts = [self.account]
        accounts.extend(self.accounts.all())
        return accounts


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


