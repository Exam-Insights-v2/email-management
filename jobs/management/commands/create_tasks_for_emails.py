from django.core.management.base import BaseCommand
from django.db.models import Q, Count
from mail.models import EmailMessage
from jobs.models import Task
from automation.tasks import process_email


class Command(BaseCommand):
    help = "Create tasks for emails that don't have tasks yet. Processes them with AI classification."

    def add_arguments(self, parser):
        parser.add_argument(
            "--account-id",
            type=int,
            help="Only process emails for this account ID",
        )
        parser.add_argument(
            "--email-id",
            type=int,
            help="Only process this specific email ID",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be processed without actually processing",
        )
        parser.add_argument(
            "--async",
            action="store_true",
            default=True,
            help="Process emails asynchronously via Celery (default: True)",
        )
        parser.add_argument(
            "--sync",
            action="store_true",
            help="Process emails synchronously (calls process_email directly)",
        )

    def handle(self, *args, **options):
        account_id = options.get("account_id")
        email_id = options.get("email_id")
        dry_run = options.get("dry_run", False)
        use_async = options.get("async", True) and not options.get("sync", False)

        # Build query for emails without tasks
        # Annotate with task count and filter for emails with 0 tasks
        emails_query = EmailMessage.objects.annotate(
            task_count=Count('tasks')
        ).filter(task_count=0).select_related("account", "thread")

        if account_id:
            emails_query = emails_query.filter(account_id=account_id)
            self.stdout.write(f"Filtering by account ID: {account_id}")

        if email_id:
            emails_query = emails_query.filter(pk=email_id)
            self.stdout.write(f"Processing specific email ID: {email_id}")

        emails = list(emails_query.order_by("-created_at"))
        total_count = len(emails)

        if total_count == 0:
            self.stdout.write(
                self.style.SUCCESS("✅ All emails already have tasks!")
            )
            return

        self.stdout.write(
            self.style.WARNING(
                f"\nFound {total_count} email(s) without tasks"
            )
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING("\n🔍 DRY RUN MODE - No emails will be processed\n")
            )
            for email in emails[:10]:  # Show first 10
                self.stdout.write(
                    f"  - Email #{email.pk}: {email.subject or '(No subject)'} "
                    f"({email.account.email})"
                )
            if total_count > 10:
                self.stdout.write(f"  ... and {total_count - 10} more")
            return

        # Process emails
        processed = 0
        errors = 0

        self.stdout.write("\nProcessing emails...\n")

        for email in emails:
            try:
                if use_async:
                    # Queue for async processing via Celery
                    process_email.delay(email.pk)
                    self.stdout.write(
                        f"  ✅ Queued email #{email.pk}: {email.subject or '(No subject)'}"
                    )
                else:
                    # Process synchronously
                    process_email(email.pk)
                    self.stdout.write(
                        f"  ✅ Processed email #{email.pk}: {email.subject or '(No subject)'}"
                    )
                processed += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"  ❌ Error processing email #{email.pk}: {str(e)}"
                    )
                )
                errors += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅ Complete! Processed {processed} email(s)"
            )
        )
        if errors > 0:
            self.stdout.write(
                self.style.ERROR(f"❌ {errors} error(s) occurred")
            )

        if use_async:
            self.stdout.write(
                self.style.WARNING(
                    "\n📝 Note: Emails are being processed asynchronously. "
                    "Check Celery worker logs to see progress."
                )
            )
