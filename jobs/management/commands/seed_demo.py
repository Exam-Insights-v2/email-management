import json
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Account
from automation.models import Action, Label, LabelAction
from jobs.models import Job, Task
from mail.models import Draft, EmailMessage, EmailThread


class Command(BaseCommand):
    help = "Seed demo data for Email IQ."

    def handle(self, *args, **options):
        account, _ = Account.objects.get_or_create(
            provider="gmail",
            email="ops@example.com",
            defaults={
                "signature_html": "<p>Regards,<br/>Field Ops</p>",
                "writing_style": "Professional, Australian English, concise.",
            },
        )

        job, _ = Job.objects.get_or_create(
            account=account,
            title="Northshore Warehouse Line Marking",
            defaults={
                "status": "in_progress",
                "customer_name": ["Northshore Plastics"],
                "customer_email": ["ops@northshore.com"],
                "site_address": "41 Dockyard Road, Sydney",
                "description": "Warehouse bay marking and arrow guidance.",
                "dates": ["2026-02-10", "2026-02-12"],
            },
        )

        thread, _ = EmailThread.objects.get_or_create(
            account=account, external_thread_id="thread-001"
        )

        email, _ = EmailMessage.objects.get_or_create(
            account=account,
            thread=thread,
            external_message_id="msg-001",
            defaults={
                "subject": "Request for site quote",
                "from_address": "jane@northshore.com",
                "to_addresses": ["ops@example.com"],
                "body_html": "<p>Can we get an updated quote?</p>",
                "date_sent": timezone.now() - timedelta(days=1),
            },
        )

        Task.objects.get_or_create(
            account=account,
            job=job,
            email_message=email,
            defaults={
                "status": "pending",
                "priority": 3,
                "title": "Respond to Northshore quote request",
            },
        )

        label, _ = Label.objects.get_or_create(
            account=account,
            name="Quotes",
            defaults={
                "prompt": "Does this email need a quote or pricing follow-up?",
            },
        )

        action, _ = Action.objects.get_or_create(
            account=account,
            name="Draft quote reply",
            function="draft_reply",
            defaults={
                "instructions": "Create a concise quote reply referencing site address and dates.",
            },
        )

        LabelAction.objects.get_or_create(label=label, action=action, defaults={"order": 1})

        Draft.objects.get_or_create(
            account=account,
            email_message=email,
            subject="Re: Request for site quote",
            defaults={
                "body_html": "<p>Hi Jane,<br/>Thanks for reaching out. We will send a quote.</p>",
            },
        )

        self.stdout.write(self.style.SUCCESS("Demo data seeded"))
