from django.contrib import admin

from .models import Action, EmailLabel, Label, LabelAction, StandardOperatingProcedure


@admin.register(Label)
class LabelAdmin(admin.ModelAdmin):
    list_display = ("name", "account", "use_mcp")
    list_filter = ("use_mcp", "account")
    search_fields = ("name",)
    fieldsets = (
        (None, {
            "fields": ("account", "name", "prompt", "sop_context", "use_mcp")
        }),
    )


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


@admin.register(StandardOperatingProcedure)
class StandardOperatingProcedureAdmin(admin.ModelAdmin):
    list_display = ("name", "account", "priority", "is_active")
    list_filter = ("is_active", "account", "priority")
    search_fields = ("name", "description")
    fieldsets = (
        (None, {
            "fields": ("account", "name", "is_active", "priority")
        }),
        ("Content", {
            "fields": ("description", "instructions")
        }),
    )
    ordering = ("-priority", "name")


@admin.register(LabelAction)
class LabelActionAdmin(admin.ModelAdmin):
    list_display = ("label", "action", "order")
    ordering = ("label", "order")


@admin.register(EmailLabel)
class EmailLabelAdmin(admin.ModelAdmin):
    list_display = ("label", "email_message")
    search_fields = ("label__name", "email_message__subject")
