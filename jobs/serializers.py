from rest_framework import serializers

from .models import Job, Task


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = [
            "id",
            "account",
            "job",
            "email_message",
            "thread",
            "status",
            "priority",
            "title",
            "description",
            "due_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]


class JobSerializer(serializers.ModelSerializer):
    tasks = TaskSerializer(many=True, read_only=True)

    class Meta:
        model = Job
        fields = [
            "id",
            "account",
            "title",
            "status",
            "customer_name",
            "customer_email",
            "site_address",
            "description",
            "dates",
            "completed_at",
            "created_at",
            "updated_at",
            "tasks",
        ]
