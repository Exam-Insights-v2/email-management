# Generated manually for simplification: Merge SOPs into Labels, remove LabelAction

import django.db.models.deletion
from django.db import migrations, models


def migrate_label_actions_to_manytomany(apps, schema_editor):
    """Migrate LabelAction relationships to Label.actions ManyToMany"""
    Label = apps.get_model('automation', 'Label')
    Action = apps.get_model('automation', 'Action')
    LabelAction = apps.get_model('automation', 'LabelAction')
    
    # For each LabelAction, add the action to the label's actions
    for label_action in LabelAction.objects.all():
        label = Label.objects.get(pk=label_action.label_id)
        action = Action.objects.get(pk=label_action.action_id)
        label.actions.add(action)


def migrate_sops_to_labels(apps, schema_editor):
    """Migrate SOP data to matching Labels if they exist"""
    Label = apps.get_model('automation', 'Label')
    StandardOperatingProcedure = apps.get_model('automation', 'StandardOperatingProcedure')
    
    # Try to match SOPs to Labels by name and account
    for sop in StandardOperatingProcedure.objects.all():
        try:
            # Try to find a label with the same name and account
            label = Label.objects.get(name=sop.name, account=sop.account)
            # Migrate SOP data to Label
            if not label.instructions:
                label.instructions = sop.instructions
            if label.priority == 1:  # Only update if default
                label.priority = sop.priority
            label.is_active = sop.is_active
            label.save()
        except Label.DoesNotExist:
            # If no matching label, create one from the SOP
            Label.objects.create(
                account=sop.account,
                name=sop.name,
                prompt=sop.description,  # Use description as prompt
                instructions=sop.instructions,
                priority=sop.priority,
                is_active=sop.is_active,
                created_at=sop.created_at,
                updated_at=sop.updated_at,
            )


def reverse_migrate(apps, schema_editor):
    """Reverse migration - recreate LabelAction and SOPs from Labels"""
    # This is complex and may lose data, so we'll just pass
    # In production, you'd want to properly reverse this
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('automation', '0002_add_mcp_support'),
        ('accounts', '0003_oauthtoken_scopes'),
    ]

    operations = [
        # Step 1: Add new fields to Label
        migrations.AddField(
            model_name='label',
            name='instructions',
            field=models.TextField(blank=True, help_text='What the AI should do when this label applies (business logic)', null=True),
        ),
        migrations.AddField(
            model_name='label',
            name='priority',
            field=models.PositiveIntegerField(default=1, help_text='Higher priority labels are considered first when multiple labels match'),
        ),
        migrations.AddField(
            model_name='label',
            name='is_active',
            field=models.BooleanField(default=True, help_text='Only active labels will trigger actions'),
        ),
        
        # Step 2: Create ManyToMany relationship
        migrations.AddField(
            model_name='label',
            name='actions',
            field=models.ManyToManyField(blank=True, help_text='Actions that can be executed when this label is applied', related_name='labels', to='automation.action'),
        ),
        
        # Step 3: Migrate data
        migrations.RunPython(migrate_label_actions_to_manytomany, reverse_migrate),
        migrations.RunPython(migrate_sops_to_labels, reverse_migrate),
        
        # Step 4: Update Label Meta ordering
        migrations.AlterModelOptions(
            name='label',
            options={'ordering': ['-priority', 'name']},
        ),
        
        # Step 5: Remove old fields from Label
        migrations.RemoveField(
            model_name='label',
            name='sop_context',
        ),
        migrations.RemoveField(
            model_name='label',
            name='use_mcp',
        ),
        
        # Step 6: Update Label.prompt help text
        migrations.AlterField(
            model_name='label',
            name='prompt',
            field=models.TextField(blank=True, help_text='When this label applies (classification criteria)', null=True),
        ),
        
        # Step 7: Delete LabelAction model
        migrations.DeleteModel(
            name='LabelAction',
        ),
        
        # Step 8: Delete StandardOperatingProcedure model
        migrations.DeleteModel(
            name='StandardOperatingProcedure',
        ),
    ]
