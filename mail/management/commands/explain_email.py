"""
Diagnostic command: explain why an email is or is not shown (in Emails list or Tasks list).
Helps debug onboarding and email-selection by reporting DB presence, task status, and eligibility for processing.
"""
from django.core.management.base import BaseCommand

from jobs.models import Task
from mail.models import EmailMessage, SyncRun


class Command(BaseCommand):
    help = (
        "Explain why an email is or is not shown. "
        "Use --email-id or (--external-id + --account-id)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--email-id",
            type=int,
            help="Database ID of the email (EmailMessage.pk)",
        )
        parser.add_argument(
            "--external-id",
            type=str,
            help="Gmail/external message ID (requires --account-id)",
        )
        parser.add_argument(
            "--account-id",
            type=int,
            help="Account ID when looking up by --external-id",
        )

    def handle(self, *args, **options):
        email_id = options.get("email_id")
        external_id = options.get("external_id")
        account_id = options.get("account_id")

        if email_id is not None:
            try:
                email = EmailMessage.objects.select_related("account", "thread").get(
                    pk=email_id
                )
            except EmailMessage.DoesNotExist:
                self._not_in_db(None)
                return
        elif external_id and account_id is not None:
            try:
                email = EmailMessage.objects.select_related("account", "thread").get(
                    account_id=account_id,
                    external_message_id=external_id,
                )
            except EmailMessage.DoesNotExist:
                self._not_in_db(account_id)
                return
        else:
            self.stdout.write(
                self.style.ERROR(
                    "Provide either --email-id OR (--external-id and --account-id)."
                )
            )
            return

        self._explain_in_db(email)

    def _not_in_db(self, account_id):
        self.stdout.write(
            self.style.WARNING("Email not in database.")
        )
        self.stdout.write(
            "Possible reasons: not in Gmail fetch window (first 100 bootstrap / "
            "first 500 full sync), excluded by query (in:inbox -in:trash -in:spam), or "
            "dropped during fetch/parse/thread backfill."
        )
        self.stdout.write(
            "Enable EMAIL_SYNC_AUDIT_LOGGING=1 and re-run onboarding or sync, "
            "or use show_onboarding_trace (if SyncRun is enabled) for this account."
        )

    def _explain_in_db(self, email):
        self.stdout.write(
            self.style.SUCCESS(
                f"In DB: id={email.pk} account_id={email.account_id} "
                f"thread_id={email.thread_id} external_message_id={email.external_message_id}"
            )
        )
        self.stdout.write("Shown in Emails list: yes.")

        tasks = list(email.tasks.all())
        if tasks:
            self.stdout.write(
                self.style.SUCCESS(f"Has task: yes (task_id={tasks[0].pk})")
            )
            return

        self.stdout.write("Has task: no.")

        # Eligible for processing = no task and thread has no task
        thread_has_task = (
            Task.objects.filter(
                account=email.account,
                thread_id=email.thread_id,
            ).exists()
            if email.thread_id
            else False
        )
        if thread_has_task:
            self.stdout.write(
                self.style.WARNING(
                    "Eligible for processing (no task, thread has no task): no. "
                    "Reason: thread already has a task."
                )
            )
        else:
            self.stdout.write(
                "Eligible for processing (no task, thread has no task): yes."
            )
            last_run = (
                SyncRun.objects.filter(account=email.account)
                .order_by("-finished_at")
                .first()
            )
            if last_run and email.pk in (last_run.emails_queued_for_processing or []):
                self.stdout.write(
                    "In last sync run: queued for process_email (emails_queued_for_processing)."
                )
            elif last_run and email.pk in (last_run.synced_email_ids or []):
                self.stdout.write(
                    "In last sync run: was in synced batch (synced_email_ids); "
                    "if still no task, it may have been eligible but not in the "
                    "'other 20' or processing may have failed."
                )
            else:
                self.stdout.write(
                    "Would be in 'synced' or 'other 20' batch: unknown without last "
                    "SyncRun; if eligible, it may be in the next sync batch. Check "
                    "sync_audit logs or show_onboarding_trace for this account."
                )
