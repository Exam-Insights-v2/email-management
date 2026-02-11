# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='account_task_number',
            field=models.PositiveIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddIndex(
            model_name='task',
            index=models.Index(fields=['account', 'account_task_number'], name='jobs_task_account_ta_123456_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='task',
            unique_together={('account', 'account_task_number')},
        ),
    ]
