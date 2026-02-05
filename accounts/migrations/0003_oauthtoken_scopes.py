# Generated manually to fix OAuth scope mismatch issue

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_account_created_at_account_is_connected_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='oauthtoken',
            name='scopes',
            field=models.TextField(
                blank=True,
                help_text='Comma-separated list of OAuth scopes granted with this token',
            ),
        ),
    ]
