from rest_framework import viewsets

from .models import Job, Task
from .serializers import JobSerializer, TaskSerializer


class JobViewSet(viewsets.ModelViewSet):
    queryset = Job.objects.all().select_related("account").prefetch_related("tasks")
    serializer_class = JobSerializer


class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.all().select_related("account", "job")
    serializer_class = TaskSerializer
