"""
Clear all synced email data, tasks created from emails, and sync runs so the next
sync runs fresh (e.g. with inbox-only query). Keeps accounts and OAuth tokens.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Account
from automation.models import EmailLabel
from jobs.models import Task
from mail.models import Draft, DraftAttachment, EmailMessage, EmailThread, SyncRun


class Command(BaseCommand):
    help = (
        "Clear email messages, threads, drafts, email-backed tasks, sync runs, and reset "
        "last_synced_at so the next sync runs as a fresh inbox-only sync."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--account-id",
            type=int,
            help="Only clear data for this account ID (default: all accounts)",
        )

    def handle(self, *args, **options):
        account_id = options.get("account_id")
        accounts = Account.objects.all()
        if account_id is not None:
            accounts = accounts.filter(pk=account_id)
            if not accounts.exists():
                self.stdout.write(self.style.ERROR(f"Account id={account_id} not found."))
                return

        with transaction.atomic():
            # Delete in dependency order
            draft_attachments = DraftAttachment.objects.filter(draft__account__in=accounts)
            n_attachments = draft_attachments.count()
            draft_attachments.delete()
            self.stdout.write(f"Deleted {n_attachments} draft attachment(s).")

            drafts = Draft.objects.filter(account__in=accounts)
            n_drafts = drafts.count()
            drafts.delete()
            self.stdout.write(f"Deleted {n_drafts} draft(s).")

            email_labels = EmailLabel.objects.filter(email_message__account__in=accounts)
            n_labels = email_labels.count()
            email_labels.delete()
            self.stdout.write(f"Deleted {n_labels} email label link(s).")

            email_tasks = Task.objects.filter(account__in=accounts).exclude(email_message__isnull=True)
            n_tasks = email_tasks.count()
            email_tasks.delete()
            self.stdout.write(f"Deleted {n_tasks} email-backed task(s).")

            messages = EmailMessage.objects.filter(account__in=accounts)
            n_messages = messages.count()
            messages.delete()
            self.stdout.write(f"Deleted {n_messages} email message(s).")

            threads = EmailThread.objects.filter(account__in=accounts)
            n_threads = threads.count()
            threads.delete()
            self.stdout.write(f"Deleted {n_threads} email thread(s).")

            runs = SyncRun.objects.filter(account__in=accounts)
            n_runs = runs.count()
            runs.delete()
            self.stdout.write(f"Deleted {n_runs} sync run(s).")

            updated = accounts.update(last_synced_at=None)
            self.stdout.write(f"Reset last_synced_at for {updated} account(s).")

        self.stdout.write(self.style.SUCCESS("Done. Run sync_emails or use Sync now to re-sync (inbox only)."))
