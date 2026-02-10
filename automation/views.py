from rest_framework import viewsets

from .models import Action, EmailLabel, Label
from .serializers import (
    ActionSerializer,
    EmailLabelSerializer,
    LabelSerializer,
)


class LabelViewSet(viewsets.ModelViewSet):
    queryset = Label.objects.all().prefetch_related("actions")
    serializer_class = LabelSerializer


class ActionViewSet(viewsets.ModelViewSet):
    queryset = Action.objects.all()
    serializer_class = ActionSerializer


class EmailLabelViewSet(viewsets.ModelViewSet):
    queryset = EmailLabel.objects.all().select_related("label", "email_message")
    serializer_class = EmailLabelSerializer
