from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import Account, OAuthToken
from automation.models import Action, EmailLabel, Label, LabelAction
from jobs.models import Job, Task
from mail.models import Draft, DraftAttachment, EmailMessage, EmailThread


@login_required
def database_home(request):
    """Show list of all database tables"""
    tables = [
        {"name": "Accounts", "slug": "accounts", "model": Account, "count": Account.objects.count()},
        {"name": "OAuth Tokens", "slug": "oauth_tokens", "model": OAuthToken, "count": OAuthToken.objects.count()},
        {"name": "Jobs", "slug": "jobs", "model": Job, "count": Job.objects.count()},
        {"name": "Tasks", "slug": "tasks", "model": Task, "count": Task.objects.count()},
        {"name": "Email Threads", "slug": "email_threads", "model": EmailThread, "count": EmailThread.objects.count()},
        {"name": "Email Messages", "slug": "email_messages", "model": EmailMessage, "count": EmailMessage.objects.count()},
        {"name": "Drafts", "slug": "drafts", "model": Draft, "count": Draft.objects.count()},
        {"name": "Draft Attachments", "slug": "draft_attachments", "model": DraftAttachment, "count": DraftAttachment.objects.count()},
        {"name": "Labels", "slug": "labels", "model": Label, "count": Label.objects.count()},
        {"name": "Email Labels", "slug": "email_labels", "model": EmailLabel, "count": EmailLabel.objects.count()},
        {"name": "Actions", "slug": "actions", "model": Action, "count": Action.objects.count()},
        {"name": "Label Actions", "slug": "label_actions", "model": LabelAction, "count": LabelAction.objects.count()},
    ]
    
    return render(request, "database/home.html", {"tables": tables})


@login_required
def database_table_view(request, model_name: str):
    """View all rows in a specific table"""
    model_map = {
        "accounts": Account,
        "oauth_tokens": OAuthToken,
        "jobs": Job,
        "tasks": Task,
        "email_threads": EmailThread,
        "email_messages": EmailMessage,
        "drafts": Draft,
        "draft_attachments": DraftAttachment,
        "labels": Label,
        "email_labels": EmailLabel,
        "actions": Action,
        "label_actions": LabelAction,
    }
    
    model = model_map.get(model_name)
    if not model:
        messages.error(request, f"Unknown table: {model_name}")
        return redirect("database_home")
    
    # Get all objects
    queryset = model.objects.all()
    
    # Get field names for display
    fields = [f.name for f in model._meta.get_fields() if not f.many_to_many and not f.one_to_many]
    
    # Pagination
    paginator = Paginator(queryset, 50)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)
    
    return render(
        request,
        "database/table_view.html",
        {
            "model": model,
            "model_name": model_name,
            "fields": fields,
            "page_obj": page_obj,
            "total_count": queryset.count(),
        },
    )


@login_required
def database_row_detail(request, model_name: str, pk: int):
    """View details of a specific row"""
    model_map = {
        "accounts": Account,
        "oauth_tokens": OAuthToken,
        "jobs": Job,
        "tasks": Task,
        "email_threads": EmailThread,
        "email_messages": EmailMessage,
        "drafts": Draft,
        "draft_attachments": DraftAttachment,
        "labels": Label,
        "email_labels": EmailLabel,
        "actions": Action,
        "label_actions": LabelAction,
    }
    
    model = model_map.get(model_name)
    if not model:
        messages.error(request, f"Unknown table: {model_name}")
        return redirect("database_home")
    
    obj = get_object_or_404(model, pk=pk)
    
    # Get all field values
    fields = {}
    for field in model._meta.get_fields():
        if field.many_to_many or field.one_to_many:
            continue
        try:
            value = getattr(obj, field.name)
            # Handle special types
            if isinstance(value, models.Model):
                fields[field.name] = {
                    "value": str(value),
                    "type": "ForeignKey",
                    "pk": value.pk,
                }
            elif isinstance(value, (list, dict)):
                fields[field.name] = {"value": value, "type": "JSON"}
            else:
                fields[field.name] = {"value": value, "type": type(value).__name__}
        except Exception:
            fields[field.name] = {"value": "N/A", "type": "Error"}
    
    return render(
        request,
        "database/row_detail.html",
        {
            "model": model,
            "model_name": model_name,
            "obj": obj,
            "fields": fields,
        },
    )


@login_required
def database_row_delete(request, model_name: str, pk: int):
    """Delete a specific row"""
    if request.method != "POST":
        messages.error(request, "Invalid request method.")
        return redirect("database_home")
    
    model_map = {
        "accounts": Account,
        "oauth_tokens": OAuthToken,
        "jobs": Job,
        "tasks": Task,
        "email_threads": EmailThread,
        "email_messages": EmailMessage,
        "drafts": Draft,
        "draft_attachments": DraftAttachment,
        "labels": Label,
        "email_labels": EmailLabel,
        "actions": Action,
        "label_actions": LabelAction,
    }
    
    model = model_map.get(model_name)
    if not model:
        messages.error(request, f"Unknown table: {model_name}")
        return redirect("database_home")
    
    obj = get_object_or_404(model, pk=pk)
    obj_str = str(obj)
    
    try:
        obj.delete()
        messages.success(request, f"Deleted {model._meta.verbose_name}: {obj_str}")
    except Exception as e:
        messages.error(request, f"Error deleting row: {str(e)}")
    
    return redirect("database_table_view", model_name=model_name)
