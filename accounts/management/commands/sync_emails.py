from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Account
from mail.services import EmailSyncService


class Command(BaseCommand):
    help = "Sync emails for all connected accounts or a specific account"

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
            # Default: sync all connected accounts
            accounts = Account.objects.filter(is_connected=True, sync_enabled=True)

        if not accounts.exists():
            self.stdout.write(self.style.WARNING("No connected accounts found to sync."))
            return

        sync_service = EmailSyncService()
        total_created = 0
        total_updated = 0

        for account in accounts:
            self.stdout.write(f"\nSyncing {account.email} ({account.provider})...")

            if not account.is_connected:
                self.stdout.write(
                    self.style.WARNING(f"  ⚠️  Account {account.email} is not connected. Skipping.")
                )
                continue

            try:
                result = sync_service.sync_account(account, max_results=50)
                total_created += result["created"]
                total_updated += result["updated"]

                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✅ Synced {result['total']} emails "
                        f"({result['created']} new, {result['updated']} updated)"
                    )
                )
                self.stdout.write(f"  📅 Last synced: {account.last_synced_at}")

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"  ❌ Error syncing {account.email}: {str(e)}")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅ Sync complete! Total: {total_created} new, {total_updated} updated emails"
            )
        )
