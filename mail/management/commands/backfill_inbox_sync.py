"""
Backfill inbox: run a one-off initial-style sync for accounts that were onboarded
when only 50 messages were fetched. Fetches up to EMAIL_FIRST_SYNC_MAX_MESSAGES
(no since filter) so older inbox messages are imported.
"""
from django.conf import settings
from django.core.management.base import BaseCommand

from accounts.models import Account
from mail.services import EmailSyncService


class Command(BaseCommand):
    help = (
        "Backfill inbox: fetch up to first-sync cap of messages (no date filter) "
        "for connected accounts. Use for accounts that were connected before pagination was added."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--account-id",
            type=int,
            help="Backfill only this account ID",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Log what would be done without syncing",
        )

    def handle(self, *args, **options):
        account_id = options.get("account_id")
        dry_run = options.get("dry_run", False)
        if account_id:
            accounts = Account.objects.filter(pk=account_id, is_connected=True)
        else:
            accounts = Account.objects.filter(is_connected=True, sync_enabled=True)
        if not accounts.exists():
            self.stdout.write(self.style.WARNING("No connected accounts to backfill."))
            return
        max_total = getattr(settings, "EMAIL_FIRST_SYNC_MAX_MESSAGES", 500)
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: would backfill {accounts.count()} account(s) with max_total={max_total}"
                )
            )
            for acc in accounts:
                self.stdout.write(f"  - {acc.email} (id={acc.pk})")
            return
        sync_service = EmailSyncService()
        for account in accounts:
            self.stdout.write(f"Backfilling {account.email} (id={account.pk})...")
            try:
                result = sync_service.sync_account(
                    account,
                    max_total=max_total,
                    force_initial=True,
                    backfill=True,
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Synced {result['total']} messages "
                        f"({result['created']} created, {result['updated']} updated)"
                    )
                )
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  Error: {e}"))
