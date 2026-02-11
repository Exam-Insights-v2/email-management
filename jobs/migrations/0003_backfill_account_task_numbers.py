# Generated manually

from django.db import migrations


def backfill_account_task_numbers(apps, schema_editor):
    """Backfill account_task_number for existing tasks"""
    Task = apps.get_model('jobs', 'Task')
    
    # Get all unique accounts that have tasks
    accounts_with_tasks = Task.objects.values('account_id').distinct()
    
    for account_data in accounts_with_tasks:
        account_id = account_data['account_id']
        # Get all tasks for this account ordered by created_at
        tasks = Task.objects.filter(account_id=account_id).order_by('created_at', 'id')
        
        # Assign sequential numbers starting from 1
        for index, task in enumerate(tasks, start=1):
            task.account_task_number = index
            task.save(update_fields=['account_task_number'])


def reverse_backfill(apps, schema_editor):
    """Reverse migration - set account_task_number to None"""
    Task = apps.get_model('jobs', 'Task')
    Task.objects.all().update(account_task_number=None)


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0002_add_account_task_number'),
    ]

    operations = [
        migrations.RunPython(backfill_account_task_numbers, reverse_backfill),
    ]
