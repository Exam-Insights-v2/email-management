from rest_framework import serializers

from .models import Action, EmailLabel, Label, LabelAction


class LabelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Label
        fields = ["id", "account", "name", "prompt", "created_at", "updated_at"]


class ActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Action
        fields = ["id", "account", "name", "function", "instructions", "created_at"]


class LabelActionSerializer(serializers.ModelSerializer):
    action = ActionSerializer(read_only=True)

    class Meta:
        model = LabelAction
        fields = ["id", "label", "action", "order"]


class EmailLabelSerializer(serializers.ModelSerializer):
    label = LabelSerializer(read_only=True)

    class Meta:
        model = EmailLabel
        fields = ["id", "email_message", "label"]
