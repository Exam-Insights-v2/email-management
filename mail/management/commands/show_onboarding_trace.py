"""
Show the last onboarding/sync run(s) for an account with all steps and IDs.
Requires SyncRun records (created during bootstrap and full sync).
"""
import json
from django.core.management.base import BaseCommand

from accounts.models import Account
from mail.models import SyncRun


class Command(BaseCommand):
    help = "Show last sync run(s) for an account (onboarding audit trail)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--account-id",
            type=int,
            required=True,
            help="Account ID to show sync runs for",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=5,
            help="Max number of runs to show (default 5)",
        )

    def handle(self, *args, **options):
        account_id = options["account_id"]
        limit = options["limit"]

        try:
            account = Account.objects.get(pk=account_id)
        except Account.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Account {account_id} not found."))
            return

        runs = SyncRun.objects.filter(account=account).order_by("-finished_at", "-started_at")[:limit]
        if not runs:
            self.stdout.write(
                self.style.WARNING(
                    f"No sync runs found for account {account_id} ({account.email}). "
                    "Runs are created on bootstrap (post-connect) and full sync."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(f"Last {runs.count()} sync run(s) for account {account_id} ({account.email}):\n")
        )
        for run in runs:
            self._print_run(run)

    def _print_run(self, run):
        self.stdout.write(f"--- SyncRun id={run.pk} phase={run.phase} ---")
        self.stdout.write(f"  started_at:  {run.started_at}")
        self.stdout.write(f"  finished_at: {run.finished_at}")
        if run.error:
            self.stdout.write(self.style.ERROR(f"  error: {run.error}"))
        self.stdout.write(f"  params: {json.dumps(run.params, default=str)}")
        if run.gmail_query:
            self.stdout.write(f"  gmail_query: {run.gmail_query}")
        self.stdout.write(f"  message_ids_from_provider: count={len(run.message_ids_from_provider)}")
        if run.message_ids_from_provider:
            sample = run.message_ids_from_provider[:15]
            self.stdout.write(f"    sample: {sample}")
        self.stdout.write(f"  synced_email_ids: count={len(run.synced_email_ids)}")
        if run.synced_email_ids:
            sample = run.synced_email_ids[:15]
            self.stdout.write(f"    sample: {sample}")
        if run.thread_backfill_stats:
            self.stdout.write(f"  thread_backfill_stats: {json.dumps(run.thread_backfill_stats)}")
        self.stdout.write(f"  emails_queued_for_processing: count={len(run.emails_queued_for_processing)}")
        if run.emails_queued_for_processing:
            sample = run.emails_queued_for_processing[:15]
            self.stdout.write(f"    sample: {sample}")
        self.stdout.write("")
