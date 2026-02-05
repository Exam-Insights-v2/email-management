from rest_framework import serializers

from .models import Account


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = [
            "id",
            "provider",
            "email",
            "signature_html",
            "writing_style",
        ]
