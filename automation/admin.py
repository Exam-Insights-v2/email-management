from django.contrib import admin

from .models import Action, EmailLabel, Label


@admin.register(Label)
class LabelAdmin(admin.ModelAdmin):
    list_display = ("name", "account", "priority", "is_active")
    list_filter = ("is_active", "account", "priority")
    search_fields = ("name", "prompt", "instructions")
    filter_horizontal = ("actions",)
    fieldsets = (
        (None, {
            "fields": ("account", "name", "is_active", "priority")
        }),
        ("Classification", {
            "fields": ("prompt",),
            "description": "When this label applies (classification criteria)"
        }),
        ("Business Logic", {
            "fields": ("instructions",),
            "description": "What the AI should do when this label applies"
        }),
        ("Actions", {
            "fields": ("actions",),
            "description": "Actions that can be executed when this label is applied"
        }),
    )
    ordering = ("-priority", "name")


@admin.register(Action)
class ActionAdmin(admin.ModelAdmin):
    list_display = ("name", "function", "mcp_tool_name", "account")
    search_fields = ("name", "function", "mcp_tool_name")
    fieldsets = (
        (None, {
            "fields": ("account", "name", "function")
        }),
        ("MCP Configuration", {
            "fields": ("mcp_tool_name", "tool_description"),
            "classes": ("collapse",),
        }),
        ("Instructions", {
            "fields": ("instructions",),
        }),
    )


@admin.register(EmailLabel)
class EmailLabelAdmin(admin.ModelAdmin):
    list_display = ("label", "email_message")
    search_fields = ("label__name", "email_message__subject")
