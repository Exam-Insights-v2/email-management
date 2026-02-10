from rest_framework import serializers

from .models import Action, EmailLabel, Label


class LabelSerializer(serializers.ModelSerializer):
    actions = serializers.PrimaryKeyRelatedField(many=True, queryset=Action.objects.all(), required=False)
    
    class Meta:
        model = Label
        fields = [
            "id", "account", "name", "prompt", "instructions", "priority", "is_active",
            "actions", "created_at", "updated_at"
        ]


class ActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Action
        fields = [
            "id", "account", "name", "function", "instructions",
            "mcp_tool_name", "tool_description", "created_at"
        ]


class EmailLabelSerializer(serializers.ModelSerializer):
    label = LabelSerializer(read_only=True)

    class Meta:
        model = EmailLabel
        fields = ["id", "email_message", "label"]
