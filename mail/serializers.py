from rest_framework import serializers

from .models import Draft, DraftAttachment, EmailAttachment, EmailMessage, EmailThread


class EmailThreadSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailThread
        fields = ["id", "account", "external_thread_id", "created_at", "updated_at"]


class EmailAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailAttachment
        fields = ["id", "filename", "content_type", "size_bytes", "is_inline", "content_id"]


class EmailMessageSerializer(serializers.ModelSerializer):
    thread = EmailThreadSerializer(read_only=True)
    attachments = EmailAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = EmailMessage
        fields = [
            "id",
            "account",
            "thread",
            "external_message_id",
            "subject",
            "from_address",
            "from_name",
            "to_addresses",
            "cc_addresses",
            "bcc_addresses",
            "date_sent",
            "body_html",
            "created_at",
            "attachments",
        ]


class DraftAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = DraftAttachment
        fields = ["id", "filename", "content_type", "size_bytes", "storage_path"]


class DraftSerializer(serializers.ModelSerializer):
    attachments = DraftAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = Draft
        fields = [
            "id",
            "account",
            "email_message",
            "external_draft_id",
            "to_addresses",
            "cc_addresses",
            "bcc_addresses",
            "subject",
            "body_html",
            "created_at",
            "updated_at",
            "attachments",
        ]
