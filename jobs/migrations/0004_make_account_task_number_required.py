# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0003_backfill_account_task_numbers'),
    ]

    operations = [
        # Make account_task_number non-nullable after backfill
        migrations.AlterField(
            model_name='task',
            name='account_task_number',
            field=models.PositiveIntegerField(db_index=True),
        ),
    ]
