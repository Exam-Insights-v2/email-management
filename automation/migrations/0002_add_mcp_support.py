# Generated manually for MCP support

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('automation', '0001_initial'),
        ('accounts', '0003_oauthtoken_scopes'),
    ]

    operations = [
        # Add MCP fields to Label
        migrations.AddField(
            model_name='label',
            name='sop_context',
            field=models.TextField(blank=True, help_text='Additional SOP context specific to this label', null=True),
        ),
        migrations.AddField(
            model_name='label',
            name='use_mcp',
            field=models.BooleanField(default=False, help_text='Use MCP for dynamic action orchestration instead of sequential execution'),
        ),
        # Add MCP fields to Action
        migrations.AddField(
            model_name='action',
            name='mcp_tool_name',
            field=models.CharField(blank=True, help_text='MCP tool name (if different from function). If set, action is exposed as MCP tool.', max_length=64, null=True),
        ),
        migrations.AddField(
            model_name='action',
            name='tool_description',
            field=models.TextField(blank=True, help_text='Description for MCP tool (used when action is exposed as MCP tool)', null=True),
        ),
        # Create StandardOperatingProcedure model
        migrations.CreateModel(
            name='StandardOperatingProcedure',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(help_text='When this SOP applies')),
                ('instructions', models.TextField(help_text='What the AI should do when this SOP applies')),
                ('priority', models.PositiveIntegerField(default=1, help_text='Higher priority SOPs are considered first')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sops', to='accounts.account')),
            ],
            options={
                'verbose_name': 'Standard Operating Procedure',
                'verbose_name_plural': 'Standard Operating Procedures',
                'ordering': ['-priority', 'name'],
            },
        ),
    ]
