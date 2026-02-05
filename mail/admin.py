from django.contrib import admin

from .models import Draft, DraftAttachment, EmailMessage, EmailThread


@admin.register(EmailThread)
class EmailThreadAdmin(admin.ModelAdmin):
    list_display = ("external_thread_id", "account", "updated_at")
    search_fields = ("external_thread_id",)


@admin.register(EmailMessage)
class EmailMessageAdmin(admin.ModelAdmin):
    list_display = ("subject", "from_address", "account", "date_sent")
    search_fields = ("subject", "from_address")
    list_filter = ("account",)


@admin.register(Draft)
class DraftAdmin(admin.ModelAdmin):
    list_display = ("subject", "account", "updated_at")
    search_fields = ("subject", "external_draft_id")


@admin.register(DraftAttachment)
class DraftAttachmentAdmin(admin.ModelAdmin):
    list_display = ("filename", "draft", "size_bytes")
    search_fields = ("filename",)
