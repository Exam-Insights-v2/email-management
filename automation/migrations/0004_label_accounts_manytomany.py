# Generated migration for adding accounts ManyToMany field to Label

from django.db import migrations, models


def populate_label_accounts(apps, schema_editor):
    """Populate the accounts ManyToMany field for existing labels"""
    Label = apps.get_model('automation', 'Label')
    # For each existing label, add the owner account to the accounts field
    for label in Label.objects.all():
        label.accounts.add(label.account)


class Migration(migrations.Migration):

    dependencies = [
        ('automation', '0003_simplify_labels_merge_sops'),
        ('accounts', '0001_initial'),
    ]

    operations = [
        # Add the accounts ManyToMany field
        migrations.AddField(
            model_name='label',
            name='accounts',
            field=models.ManyToManyField(
                blank=True,
                help_text='Accounts that can use this label for classification. If empty, only the owner account can use it.',
                related_name='available_labels',
                to='accounts.account'
            ),
        ),
        # Populate existing labels with their owner account
        migrations.RunPython(populate_label_accounts, migrations.RunPython.noop),
        # Update the account field's related_name to avoid conflict
        migrations.AlterField(
            model_name='label',
            name='account',
            field=models.ForeignKey(
                help_text='The account that owns/created this label',
                on_delete=models.CASCADE,
                related_name='owned_labels',
                to='accounts.account'
            ),
        ),
    ]
