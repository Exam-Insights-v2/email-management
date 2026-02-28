from rest_framework import viewsets

from .models import Draft, EmailMessage, EmailThread
from .serializers import DraftSerializer, EmailMessageSerializer, EmailThreadSerializer


class EmailThreadViewSet(viewsets.ModelViewSet):
    queryset = EmailThread.objects.all()
    serializer_class = EmailThreadSerializer


class EmailMessageViewSet(viewsets.ModelViewSet):
    queryset = EmailMessage.objects.all().select_related("thread").prefetch_related("attachments")
    serializer_class = EmailMessageSerializer


class DraftViewSet(viewsets.ModelViewSet):
    queryset = Draft.objects.all().prefetch_related("attachments")
    serializer_class = DraftSerializer
