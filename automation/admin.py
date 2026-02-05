from django.contrib import admin

from .models import Action, EmailLabel, Label, LabelAction


@admin.register(Label)
class LabelAdmin(admin.ModelAdmin):
    list_display = ("name", "account")
    search_fields = ("name",)


@admin.register(Action)
class ActionAdmin(admin.ModelAdmin):
    list_display = ("name", "function", "account")
    search_fields = ("name", "function")


@admin.register(LabelAction)
class LabelActionAdmin(admin.ModelAdmin):
    list_display = ("label", "action", "order")
    ordering = ("label", "order")


@admin.register(EmailLabel)
class EmailLabelAdmin(admin.ModelAdmin):
    list_display = ("label", "email_message")
    search_fields = ("label__name", "email_message__subject")
