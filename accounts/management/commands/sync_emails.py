"""
Sync emails via the same full pipeline as Celery and "Sync now" in the UI.
Runs sync_account_emails synchronously so sync, SyncRun, and process_email queue
all run without a Celery worker for the sync step. process_email tasks still
require a worker to run.
"""
from django.core.management.base import BaseCommand

from accounts.models import Account
from mail.tasks import sync_account_emails


class Command(BaseCommand):
    help = (
        "Full sync for connected accounts (same as Celery/UI Sync now): "
        "sync from provider, create SyncRun, queue process_email. "
        "Use --account-id or --email to sync one account, or --all for all connected."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--account-id",
            type=int,
            help="Sync only this account ID",
        )
        parser.add_argument(
            "--email",
            type=str,
            help="Sync only this email address",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Sync all connected accounts",
        )

    def handle(self, *args, **options):
        if options["account_id"]:
            accounts = Account.objects.filter(pk=options["account_id"])
        elif options["email"]:
            accounts = Account.objects.filter(email=options["email"])
        elif options["all"]:
            accounts = Account.objects.filter(is_connected=True, sync_enabled=True)
        else:
            accounts = Account.objects.filter(is_connected=True, sync_enabled=True)

        if not accounts.exists():
            self.stdout.write(self.style.WARNING("No connected accounts found to sync."))
            return

        for account in accounts:
            self.stdout.write(f"\nSyncing {account.email} ({account.provider})...")

            if not account.is_connected:
                self.stdout.write(
                    self.style.WARNING(f"  Account {account.email} is not connected. Skipping.")
                )
                continue

            try:
                result = sync_account_emails.apply(args=(account.pk,))
                out = result.get()
                if isinstance(out, dict) and "error" in out:
                    self.stdout.write(self.style.ERROR(f"  Error: {out['error']}"))
                else:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  Synced {out.get('total', 0)} emails "
                            f"({out.get('created', 0)} new, {out.get('updated', 0)} updated)"
                        )
                    )
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  Error syncing {account.email}: {e}"))

        self.stdout.write(self.style.SUCCESS("\nSync complete."))
