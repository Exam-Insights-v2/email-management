# Generated manually for onboarding observability (SyncRun audit trail)

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mail", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="SyncRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("phase", models.CharField(choices=[("bootstrap", "Bootstrap (post-connect)"), ("full", "Full sync (Celery)")], max_length=32)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("params", models.JSONField(blank=True, default=dict)),
                ("gmail_query", models.CharField(blank=True, max_length=512)),
                ("message_ids_from_provider", models.JSONField(blank=True, default=list)),
                ("synced_email_ids", models.JSONField(blank=True, default=list)),
                ("thread_backfill_stats", models.JSONField(blank=True, default=dict)),
                ("emails_queued_for_processing", models.JSONField(blank=True, default=list)),
                ("error", models.TextField(blank=True)),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sync_runs", to="accounts.account")),
            ],
            options={
                "ordering": ["-finished_at", "-started_at"],
            },
        ),
        migrations.AddIndex(
            model_name="syncrun",
            index=models.Index(fields=["account", "finished_at"], name="mail_syncru_account_8a1b2c_idx"),
        ),
    ]
