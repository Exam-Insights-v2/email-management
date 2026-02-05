from rest_framework import viewsets

from .models import Action, EmailLabel, Label, LabelAction
from .serializers import (
    ActionSerializer,
    EmailLabelSerializer,
    LabelActionSerializer,
    LabelSerializer,
)


class LabelViewSet(viewsets.ModelViewSet):
    queryset = Label.objects.all()
    serializer_class = LabelSerializer


class ActionViewSet(viewsets.ModelViewSet):
    queryset = Action.objects.all()
    serializer_class = ActionSerializer


class LabelActionViewSet(viewsets.ModelViewSet):
    queryset = LabelAction.objects.all().select_related("action", "label")
    serializer_class = LabelActionSerializer


class EmailLabelViewSet(viewsets.ModelViewSet):
    queryset = EmailLabel.objects.all().select_related("label", "email_message")
    serializer_class = EmailLabelSerializer
