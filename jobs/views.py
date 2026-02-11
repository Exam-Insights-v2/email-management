from rest_framework import viewsets

from .models import Job, Task
from .serializers import JobSerializer, TaskSerializer


class JobViewSet(viewsets.ModelViewSet):
    serializer_class = JobSerializer
    
    def get_queryset(self):
        # Only show jobs from accounts that belong to the logged-in user
        if self.request.user.is_authenticated:
            return Job.objects.filter(account__users=self.request.user).select_related("account").prefetch_related("tasks")
        return Job.objects.none()


class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    
    def get_queryset(self):
        # Only show tasks from accounts that belong to the logged-in user
        if self.request.user.is_authenticated:
            return Task.objects.filter(account__users=self.request.user).select_related("account", "job")
        return Task.objects.none()