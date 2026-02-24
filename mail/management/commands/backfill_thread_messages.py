"""
Backfill all messages in each thread so the task view can show full threads.

Run once after deploying the thread-backfill sync change, or whenever threads
only have one message in the DB. Uses provider API (Gmail or Microsoft) to
fetch full thread and stores every message.
"""
import logging

from django.core.management.base import BaseCommand
from django.db import transaction

from mail.models import EmailMessage, EmailThread

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Backfill all messages in each thread (Gmail and Microsoft) so task view shows full threads"

    def add_arguments(self, parser):
        parser.add_argument(
            "--account-id",
            type=int,
            help="Only backfill threads for this account ID",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only report what would be done",
        )

    def handle(self, *args, **options):
        account_id = options.get("account_id")
        dry_run = options.get("dry_run", False)

        qs = EmailThread.objects.select_related("account").filter(
            account__is_connected=True,
        ).exclude(
            external_thread_id__startswith="single-",
        )
        if account_id:
            qs = qs.filter(account_id=account_id)

        if not qs.exists():
            self.stdout.write(self.style.WARNING("No threads found to backfill."))
            return

        try:
            from mail.services import EmailSyncService
            sync = EmailSyncService()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Cannot get sync service: {e}"))
            return

        total_threads = 0
        total_messages = 0
        errors = 0

        for thread in qs:
            account = thread.account
            provider_service = sync.providers.get(account.provider)
            if not provider_service or not hasattr(provider_service, "get_thread_messages"):
                continue
            ext_id = thread.external_thread_id
            current_count = thread.messages.count()
            total_threads += 1
            if dry_run:
                self.stdout.write(f"Would backfill thread {ext_id} (account {account.email}, currently {current_count} message(s))")
                continue
            try:
                thread_messages = provider_service.get_thread_messages(account, ext_id)
            except Exception as e:
                logger.warning("Failed to fetch thread %s: %s", ext_id, e)
                self.stdout.write(self.style.WARNING(f"  Skip thread {ext_id}: {e}"))
                errors += 1
                continue
            with transaction.atomic():
                for m in thread_messages:
                    EmailMessage.objects.update_or_create(
                        account=account,
                        external_message_id=m["external_message_id"],
                        defaults={
                            "thread": thread,
                            "subject": m.get("subject") or "",
                            "from_address": m.get("from_address") or "",
                            "from_name": m.get("from_name") or "",
                            "to_addresses": m.get("to_addresses") or [],
                            "cc_addresses": m.get("cc_addresses") or [],
                            "bcc_addresses": m.get("bcc_addresses") or [],
                            "date_sent": m.get("date_sent"),
                            "body_html": m.get("body_html") or "",
                        },
                    )
                    total_messages += 1
            self.stdout.write(f"  Backfilled thread {ext_id}: {len(thread_messages)} message(s)")

        self.stdout.write(
            self.style.SUCCESS(
                f"Backfill complete. Threads: {total_threads}, messages stored: {total_messages}, errors: {errors}"
            )
        )
