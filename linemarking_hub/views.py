import json
import logging
import os
import time
from datetime import datetime
from django.conf import settings
from django.contrib import messages

logger = logging.getLogger(__name__)
from django.contrib.auth.decorators import login_required
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from accounts.models import Account, OAuthToken
from accounts.oauth_redirects import build_oauth_redirect_uri
from accounts.services import GmailOAuthService, MicrosoftEmailOAuthService
from automation.models import Action, EmailLabel, Label
from jobs.models import Job, Task
from mail.models import Draft, DraftAttachment, EmailMessage, EmailThread
from mail.services import GmailService, MicrosoftService, persist_sent_message
from linemarking_hub.templatetags.db_filters import _strip_quoted_email_html
from linemarking_hub.forms import (
    AccountForm,
    ActionForm,
    JobForm,
    LabelForm,
    TaskForm,
    TaskFilterForm,
)


# Jobs CRUD
@login_required
def jobs_list(request):
    # Redirect to tasks list - jobs page is disabled
    return redirect("tasks_list")


@login_required
def jobs_calendar(request):
    # Redirect to tasks list - jobs page is disabled
    return redirect("tasks_list")
    from collections import defaultdict
    from datetime import datetime, timedelta
    
    # Get search query
    search_query = request.GET.get('search', '').strip()
    
    # Get all jobs
    all_jobs = Job.objects.select_related("account").prefetch_related("tasks").all()
    
    # Filter jobs by search query if provided
    if search_query:
        from django.db.models import Q
        all_jobs = all_jobs.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(site_address__icontains=search_query) |
            Q(customer_name__icontains=search_query)
        )
    
    # Separate scheduled and unscheduled jobs
    unscheduled_jobs = []
    scheduled_jobs = []
    jobs_by_date = defaultdict(list)
    
    for job in all_jobs:
        if job.dates:
            dates = job.dates if isinstance(job.dates, list) else json.loads(job.dates) if isinstance(job.dates, str) else []
            if dates:
                scheduled_jobs.append(job)
                for date_str in dates:
                    try:
                        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                        jobs_by_date[date_str].append(job)
                    except (ValueError, TypeError):
                        continue
            else:
                unscheduled_jobs.append(job)
        else:
            unscheduled_jobs.append(job)
    
    # Get week parameter or default to current week
    today = timezone.now().date()
    week_start_param = request.GET.get('week_start')
    
    if week_start_param:
        try:
            week_start = datetime.strptime(week_start_param, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            week_start = today - timedelta(days=today.weekday())
    else:
        # Default to start of current week (Monday)
        week_start = today - timedelta(days=today.weekday())
    
    # Calculate week end (Sunday)
    week_end = week_start + timedelta(days=6)
    
    # Generate dates for the week
    calendar_dates = []
    current_date = week_start
    while current_date <= week_end:
        date_str = current_date.strftime("%Y-%m-%d")
        calendar_dates.append({
            "date": current_date,
            "date_str": date_str,
            "jobs": jobs_by_date.get(date_str, []),
            "is_today": current_date == today,
            "is_past": current_date < today,
        })
        current_date += timedelta(days=1)
    
    # Calculate previous and next week start dates
    prev_week_start = week_start - timedelta(days=7)
    next_week_start = week_start + timedelta(days=7)
    current_week_start = today - timedelta(days=today.weekday())
    
    form = JobForm()
    return render(request, "jobs/calendar.html", {
        "calendar_dates": calendar_dates,
        "unscheduled_jobs": unscheduled_jobs,
        "week_start": week_start,
        "week_end": week_end,
        "prev_week_start": prev_week_start,
        "next_week_start": next_week_start,
        "current_week_start": current_week_start,
        "search_query": search_query,
        "form": form,
    })


@login_required
def job_detail(request, pk):
    # Redirect to tasks list - jobs page is disabled
    return redirect("tasks_list")


@login_required
def job_create(request):
    # Redirect to tasks list - jobs page is disabled
    return redirect("tasks_list")
    if request.method == "POST":
        form = JobForm(request.POST)
        if form.is_valid():
            try:
                job = form.save(commit=False)
                # Parse JSON fields
                if isinstance(job.customer_name, str):
                    job.customer_name = json.loads(job.customer_name) if job.customer_name else []
                if isinstance(job.customer_email, str):
                    job.customer_email = json.loads(job.customer_email) if job.customer_email else []
                if isinstance(job.dates, str):
                    job.dates = json.loads(job.dates) if job.dates else []
                job.save()
                messages.success(request, f"Job '{job.title}' created successfully.")
                return redirect("job_detail", pk=job.pk)
            except (ValidationError, json.JSONDecodeError) as e:
                messages.error(request, f"Error: {str(e)}")
    else:
        form = JobForm()
    return render(request, "jobs/form.html", {"form": form, "title": "Create Job"})


@login_required
def job_update(request, pk):
    # Redirect to tasks list - jobs page is disabled
    return redirect("tasks_list")
    job = get_object_or_404(Job, pk=pk)
    if request.method == "POST":
        form = JobForm(request.POST, instance=job)
        if form.is_valid():
            try:
                job = form.save(commit=False)
                # Parse JSON fields
                if isinstance(job.customer_name, str):
                    job.customer_name = json.loads(job.customer_name) if job.customer_name else []
                if isinstance(job.customer_email, str):
                    job.customer_email = json.loads(job.customer_email) if job.customer_email else []
                if isinstance(job.dates, str):
                    job.dates = json.loads(job.dates) if job.dates else []
                job.save()
                messages.success(request, f"Job '{job.title}' updated successfully.")
                return redirect("job_detail", pk=job.pk)
            except (ValidationError, json.JSONDecodeError) as e:
                messages.error(request, f"Error: {str(e)}")
    else:
        # Convert JSON fields to strings for form display
        initial_data = {
            "customer_name": json.dumps(job.customer_name) if job.customer_name else "[]",
            "customer_email": json.dumps(job.customer_email) if job.customer_email else "[]",
            "dates": json.dumps(job.dates) if job.dates else "[]",
        }
        form = JobForm(instance=job, initial=initial_data)
    return render(request, "jobs/form.html", {"form": form, "job": job, "title": "Edit Job"})


@login_required
@require_http_methods(["POST"])
def job_delete(request, pk):
    # Redirect to tasks list - jobs page is disabled
    return redirect("tasks_list")


# Tasks CRUD
@login_required
def tasks_list(request):
    from django.db.models import Q
    from collections import defaultdict
    from datetime import datetime
    
    # Get search query
    search_query = request.GET.get('search', '').strip()
    
    # Get first available connected account for forms (from user's accounts)
    from accounts.models import Account
    account = request.user.accounts.filter(is_connected=True).first() if request.user.is_authenticated else None
    
    # Initialize filter form with GET parameters
    filter_form = TaskFilterForm(request.GET, user=request.user, account=account)
    
    # Get tasks only from accounts that belong to the logged-in user
    from django.db.models import Prefetch
    tasks = Task.objects.filter(
        account__users=request.user
    ).select_related(
        "account", 
        "job", 
        "email_message",
        "email_message__thread"
    ).prefetch_related(
        Prefetch(
            "email_message__labels",
            queryset=EmailLabel.objects.select_related("label").prefetch_related("label__actions")
        )
    )
    
    # Filter tasks by search query if provided
    if search_query:
        tasks = tasks.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(email_message__subject__icontains=search_query) |
            Q(email_message__from_address__icontains=search_query) |
            Q(email_message__from_name__icontains=search_query) |
            Q(email_message__body_html__icontains=search_query)
        )
    
    # Apply filter form filters
    if filter_form.is_valid():
        # Filter by email (supports multiple comma-separated emails)
        email_filter = filter_form.cleaned_data.get('email')
        if email_filter:
            email_list = [e.strip() for e in email_filter.split(',') if e.strip()]
            if email_list:
                email_q = Q()
                for email in email_list:
                    # Check from_address, from_name, and to_addresses (JSONField array)
                    # For to_addresses, we check if the email appears in the JSON representation
                    # This works because JSONField stores arrays as JSON strings
                    email_q |= (
                        Q(email_message__from_address__icontains=email) | 
                        Q(email_message__from_name__icontains=email) |
                        Q(email_message__to_addresses__icontains=email)
                    )
                tasks = tasks.filter(email_q)
        
        # Filter by date range
        date_from = filter_form.cleaned_data.get('date_from')
        date_to = filter_form.cleaned_data.get('date_to')
        if date_from:
            tasks = tasks.filter(created_at__date__gte=date_from)
        if date_to:
            tasks = tasks.filter(created_at__date__lte=date_to)
        
        # Filter by status (multiple)
        statuses = filter_form.cleaned_data.get('status')
        if statuses:
            tasks = tasks.filter(status__in=statuses)
        else:
            # Default: exclude done and cancelled tasks if no status filter is set
            from jobs.models import TaskStatus
            tasks = tasks.exclude(status__in=[TaskStatus.DONE, TaskStatus.CANCELLED])
        
        # Filter by task ID (supports multiple comma-separated IDs)
        task_id = filter_form.cleaned_data.get('task_id')
        if task_id:
            task_ids = [tid.strip() for tid in task_id.split(',') if tid.strip()]
            if task_ids:
                try:
                    task_id_list = [int(tid) for tid in task_ids]
                    tasks = tasks.filter(pk__in=task_id_list)
                except ValueError:
                    pass  # Invalid task IDs, skip filtering
        
        # Filter by priority (multiple)
        priorities = filter_form.cleaned_data.get('priority')
        if priorities:
            priority_list = [int(p) for p in priorities]
            tasks = tasks.filter(priority__in=priority_list)
        
        # Filter by label (multiple)
        labels = filter_form.cleaned_data.get('label')
        if labels:
            tasks = tasks.filter(email_message__labels__label__in=labels).distinct()
    
    # Group tasks by priority (5=Urgent, 4=High, 3=Medium, 2=Low, 1=Lowest)
    tasks_by_priority = defaultdict(list)
    all_tasks = list(tasks.order_by("-created_at"))
    
    for task in all_tasks:
        # Ensure priority is between 1-5
        priority = max(1, min(5, task.priority or 1))
        tasks_by_priority[priority].append(task)
    
    # Preload email thread and draft data for tasks with email messages
    # Get thread messages from database (not Gmail API - much faster!)
    
    # Batch load all drafts for tasks with emails (one query instead of N)
    email_messages = [task.email_message for task in all_tasks if task.email_message]
    email_message_ids = [em.pk for em in email_messages]
    
    # Get all drafts in one query (then pick latest per email in Python)
    drafts_by_email = {}
    if email_message_ids:
        all_drafts = Draft.objects.filter(
            email_message_id__in=email_message_ids
        ).order_by('email_message_id', '-updated_at')
        # Keep only the latest draft per email_message_id
        for draft in all_drafts:
            if draft.email_message_id not in drafts_by_email:
                drafts_by_email[draft.email_message_id] = draft
    
    # Step 2: Load all thread messages from DB only (same thread_id = same thread). Order: oldest first.
    thread_ids = {em.thread_id for em in email_messages if em.thread_id}
    threads_with_messages = {}
    if thread_ids:
        from mail.models import EmailThread
        threads = EmailThread.objects.filter(pk__in=thread_ids).prefetch_related(
            Prefetch(
                "messages",
                queryset=EmailMessage.objects.all().order_by("date_sent", "created_at")
            )
        )
        for thread in threads:
            threads_with_messages[thread.pk] = [
                {
                    "external_message_id": msg.external_message_id,
                    "subject": msg.subject,
                    "from_address": msg.from_address,
                    "from_name": msg.from_name,
                    "to_addresses": msg.to_addresses or [],
                    "cc_addresses": msg.cc_addresses or [],
                    "bcc_addresses": msg.bcc_addresses or [],
                    "date_sent": msg.date_sent,
                    "body_html": msg.body_html or "",
                }
                for msg in thread.messages.all()
            ]
    
    task_email_data = {}
    
    for task in all_tasks:
        if task.email_message:
            email = task.email_message
            
            # Check if task has labels with draft_reply action (now using prefetched data)
            has_draft_reply = False
            for email_label in email.labels.all():
                # Check prefetched actions (no database query!)
                if any(action.function == "draft_reply" for action in email_label.label.actions.all()):
                    has_draft_reply = True
                    break
            
            # Get thread messages from DB only (Gmail/API is used only to sync messages into the DB)
            thread_messages = threads_with_messages.get(email.thread_id, []) if email.thread_id else []
            account = email.account

            # Get draft from prefetched data
            draft = drafts_by_email.get(email.pk)
            
            # If no draft exists and we should have one, create it (body = draft only, no thread history)
            if not draft and has_draft_reply:
                reply_subject = f"Re: {email.subject or 'No subject'}"
                reply_to = [email.from_address]
                reply_body = ""
                if email.account.signature_html:
                    reply_body = f"<div style=\"margin-top: 20px; padding-top: 20px; border-top: 1px solid #e5e7eb;\">{email.account.signature_html}</div>"
                draft = Draft.objects.create(
                    account=email.account,
                    email_message=email,
                    to_addresses=reply_to,
                    subject=reply_subject,
                    body_html=reply_body,
                )
            
            task_email_data[task.pk] = {
                "email": email,
                "thread_messages": thread_messages,
                "has_draft_reply": has_draft_reply,
                "draft": draft,
                "draft_body_display": _strip_quoted_email_html(draft.body_html) if (draft and draft.body_html) else "",
            }
    
    form = TaskForm(user=request.user, account=account)
    
    # Check account connection status and token validity for user's accounts
    user_accounts = request.user.accounts.all() if request.user.is_authenticated else Account.objects.none()
    account_statuses = {}
    for acc in user_accounts:
        has_token_error = False
        token_error_message = None
        
        if acc.is_connected:
            # Check if token is valid (refresh logic will handle proactive refresh)
            try:
                if acc.provider == 'gmail':
                    credentials = GmailOAuthService.get_valid_credentials(acc)
                    if not credentials:
                        has_token_error = True
                        token_error_message = "Unable to get valid credentials. Please reconnect your account."
                elif acc.provider == 'microsoft':
                    credentials = MicrosoftEmailOAuthService.get_valid_credentials(acc)
                    if not credentials:
                        has_token_error = True
                        token_error_message = "Unable to get valid credentials. Please reconnect your account."
            except Exception as e:
                logger.warning("Error checking token for account %s: %s", acc.pk, e)
                has_token_error = True
                token_error_message = "Unable to verify token. Please reconnect your account."
        
        account_statuses[acc.pk] = {
            'has_token_error': has_token_error,
            'token_error_message': token_error_message or "Your account is not connected. Please reconnect to sync emails.",
        }
    
    # Count active filters
    active_filter_count = 0
    if filter_form.is_valid():
        if filter_form.cleaned_data.get('email'):
            active_filter_count += 1
        if filter_form.cleaned_data.get('date_from'):
            active_filter_count += 1
        if filter_form.cleaned_data.get('date_to'):
            active_filter_count += 1
        if filter_form.cleaned_data.get('status'):
            active_filter_count += 1
        if filter_form.cleaned_data.get('task_id'):
            active_filter_count += 1
        if filter_form.cleaned_data.get('priority'):
            active_filter_count += 1
        if filter_form.cleaned_data.get('label'):
            active_filter_count += 1
    
    return render(request, "tasks/list.html", {
        "tasks_by_priority": dict(tasks_by_priority),
        "all_tasks": all_tasks,
        "form": form,
        "filter_form": filter_form,
        "search_query": search_query,
        "task_email_data": task_email_data,
        "account_statuses": account_statuses,
        "user_accounts": user_accounts,
        "user_connected_accounts": list(user_accounts.filter(is_connected=True)),
        "active_filter_count": active_filter_count,
    })


@login_required
def task_detail(request, pk):
    # Redirect to tasks list with task parameter to open modal
    from django.shortcuts import redirect
    from django.urls import reverse
    return redirect(reverse("tasks_list") + f"?task={pk}", permanent=False)


@login_required
def task_create(request):
    # Get first available connected account from user's accounts
    from accounts.models import Account
    account = request.user.accounts.filter(is_connected=True).first()
    
    if request.method == "POST":
        form = TaskForm(request.POST, user=request.user, account=account)
        if form.is_valid():
            try:
                task = form.save()
                messages.success(request, f"Task '{task.title or task.pk}' created successfully.")
                return redirect("task_detail", pk=task.pk)
            except ValidationError as e:
                messages.error(request, str(e))
    else:
        form = TaskForm(user=request.user, account=account)
    return render(request, "tasks/form.html", {"form": form, "title": "Create Task"})


@login_required
def task_update(request, pk):
    # Only allow updating tasks from user's accounts
    task = get_object_or_404(Task, pk=pk, account__users=request.user)
    # Get account from task or first available from user's accounts
    account = task.account if task.account else None
    if not account:
        from accounts.models import Account
        account = request.user.accounts.filter(is_connected=True).first()
    
    if request.method == "POST":
        form = TaskForm(request.POST, instance=task, user=request.user, account=account)
        if form.is_valid():
            try:
                task = form.save()
                from jobs.models import TaskStatus
                if task.status == TaskStatus.DONE and not task.completed_at:
                    task.completed_at = timezone.now()
                    task.save(update_fields=["completed_at"])
                elif task.status != TaskStatus.DONE and task.completed_at:
                    task.completed_at = None
                    task.save(update_fields=["completed_at"])
                messages.success(request, f"Task '{task.title or task.pk}' updated successfully.")
                return redirect("task_detail", pk=task.pk)
            except ValidationError as e:
                messages.error(request, str(e))
                # Return form with errors for modal/drawer
                modal_id = f"edit-task-{pk}"
                return render(request, "tasks/form_content.html", {"form": form, "task": task, "form_url": "task_update", "drawer_id": modal_id, "modal_id": modal_id})
    else:
        form = TaskForm(instance=task, user=request.user, account=account)
    modal_id = f"edit-task-{pk}"
    return render(request, "tasks/form_content.html", {"form": form, "task": task, "form_url": "task_update", "drawer_id": modal_id, "modal_id": modal_id})


@login_required
@require_http_methods(["POST"])
def task_delete(request, pk):
    # Only allow deleting tasks from user's accounts
    task = get_object_or_404(Task, pk=pk, account__users=request.user)
    title = task.title or f"Task {task.pk}"
    task.delete()
    messages.success(request, f"Task '{title}' deleted successfully.")
    return redirect("tasks_list")


@login_required
@require_http_methods(["POST"])
def task_reprocess(request, pk):
    """Delete this task (and any other tasks for the same email), then queue process_email so the email is reclassified and a new task is created. Use to verify processing fixes."""
    task = get_object_or_404(Task, pk=pk, account__users=request.user)
    if not task.email_message_id:
        messages.error(request, "This task has no linked email, so it cannot be reprocessed.")
        return redirect("tasks_list")
    email_message_id = task.email_message_id
    email = task.email_message
    # Delete all tasks for this email so process_email will run (it skips when tasks exist)
    for t in email.tasks.all():
        t.delete()
    from automation.tasks import process_email
    process_email.delay(email_message_id)
    messages.success(
        request,
        "Reprocessing started. Refresh in a few seconds to see the updated task.",
    )
    return redirect("tasks_list")


# Emails CRUD
@login_required
def emails_list(request):
    emails = EmailMessage.objects.filter(
        account__in=request.user.accounts.all()
    ).select_related("account", "thread").prefetch_related("thread__messages", "labels__label", "tasks").order_by("-date_sent", "-created_at")
    
    # Build thread message data from DB (sync already stores full threads)
    email_data = {}
    for email in emails:
        thread_messages = []
        if email.thread:
            for m in email.thread.messages.all():
                thread_messages.append({
                    "from_address": m.from_address or "",
                    "from_name": m.from_name or m.from_address or "",
                    "subject": m.subject or "",
                    "date_sent": m.date_sent,
                    "body_html": m.body_html or "",
                })
            thread_messages.sort(key=lambda x: x.get("date_sent") or datetime.min, reverse=True)
        
        drafts = Draft.objects.filter(account=email.account, email_message=email).order_by("-updated_at")
        
        email_data[email.pk] = {
            "thread_messages": thread_messages,
            "drafts": list(drafts),
        }
    
    return render(request, "emails/list.html", {"emails": emails, "email_data": email_data})


@login_required
def email_detail(request, pk):
    """Redirect to emails list with modal parameter - email detail is now shown in modal"""
    return redirect("{}?email={}".format(reverse("emails_list"), pk))


@login_required
def task_email_data(request, pk):
    """API endpoint to get email thread and draft data for a task (thread messages from DB only)."""
    task = get_object_or_404(
        Task.objects.select_related("email_message__account", "email_message__thread").prefetch_related(
            "email_message__labels__label",
            "email_message__thread__messages",
        ),
        pk=pk,
    )
    
    if not task.email_message:
        return JsonResponse({"error": "Task has no associated email"}, status=400)
    
    email = task.email_message
    
    # Check if task has labels with draft_reply action
    has_draft_reply = False
    for email_label in email.labels.all():
        if email_label.label.actions.filter(function="draft_reply").exists():
            has_draft_reply = True
            break
    
    # Step 2: Get all email messages for this thread from DB (same thread_id). Order: oldest first.
    thread_messages = []
    if email.thread_id:
        for msg in EmailMessage.objects.filter(thread_id=email.thread_id).order_by("date_sent", "created_at"):
            thread_messages.append({
                "external_message_id": msg.external_message_id,
                "subject": msg.subject,
                "from_address": msg.from_address,
                "from_name": msg.from_name,
                "to_addresses": msg.to_addresses or [],
                "cc_addresses": msg.cc_addresses or [],
                "bcc_addresses": msg.bcc_addresses or [],
                "date_sent": msg.date_sent,
                "body_html": msg.body_html or "",
            })
    
    # Get or create draft for this email
    draft = Draft.objects.filter(account=email.account, email_message=email).order_by("-updated_at").first()
    
    # If no draft exists and we should have one, create it
    if not draft and has_draft_reply:
        reply_subject = f"Re: {email.subject or 'No subject'}"
        reply_to = [email.from_address]
        reply_body = ""
        if email.account.signature_html:
            reply_body = f"<div style=\"margin-top: 20px; padding-top: 20px; border-top: 1px solid #e5e7eb;\">{email.account.signature_html}</div>"
        draft = Draft.objects.create(
            account=email.account,
            email_message=email,
            to_addresses=reply_to,
            subject=reply_subject,
            body_html=reply_body,
        )
    
    # Serialize data
    data = {
        "email": {
            "id": email.pk,
            "subject": email.subject or "(No subject)",
            "from_address": email.from_address,
            "from_name": email.from_name or email.from_address,
            "to_addresses": email.to_addresses or [],
            "cc_addresses": email.cc_addresses or [],
            "date_sent": email.date_sent.isoformat() if email.date_sent else None,
            "body_html": email.body_html or "",
        },
        "thread_messages": thread_messages,
        "has_draft_reply": has_draft_reply,
        "draft": None,
    }
    
    if draft:
        data["draft"] = {
            "id": draft.pk,
            "to_addresses": draft.to_addresses or [],
            "cc_addresses": draft.cc_addresses or [],
            "subject": draft.subject or "",
            "body_html": _strip_quoted_email_html(draft.body_html or "") or "",
        }
    
    return JsonResponse(data)


@login_required
@require_http_methods(["POST"])
def email_delete(request, pk):
    email = get_object_or_404(EmailMessage, pk=pk)
    subject = email.subject or f"Email {email.pk}"
    
    # Delete from Gmail if connected
    if email.account.is_connected:
        try:
            gmail_service = GmailService()
            gmail_service.delete_message(email.account, email.external_message_id)
            messages.success(request, f"Email '{subject}' deleted from Gmail and database.")
        except Exception as e:
            messages.warning(request, f"Deleted from database but Gmail error: {str(e)}")
    
    email.delete()
    messages.success(request, f"Email '{subject}' deleted successfully.")
    return redirect("emails_list")


@login_required
@require_http_methods(["POST"])
def email_archive(request, pk):
    """Archive email (mark as done)"""
    email = get_object_or_404(EmailMessage, pk=pk)
    
    if not email.account.is_connected:
        messages.error(request, "Account is not connected to Gmail.")
        return redirect("{}?email={}".format(reverse("emails_list"), email.pk))
    
    try:
        gmail_service = GmailService()
        gmail_service.archive_message(email.account, email.external_message_id)
        messages.success(request, f"Email '{email.subject or 'Untitled'}' archived successfully.")
    except Exception as e:
        messages.error(request, f"Error archiving email: {str(e)}")
    
    return redirect("{}?email={}".format(reverse("emails_list"), email.pk))


@login_required
@require_http_methods(["POST"])
def email_unarchive(request, pk):
    """Move email back to inbox (undo archive / mark as undone)"""
    email = get_object_or_404(EmailMessage, pk=pk)

    if not email.account.is_connected:
        messages.error(request, "Account is not connected to Gmail.")
        return redirect("{}?email={}".format(reverse("emails_list"), email.pk))

    try:
        gmail_service = GmailService()
        gmail_service.unarchive_message(email.account, email.external_message_id)
        messages.success(request, f"Email '{email.subject or 'Untitled'}' moved back to inbox.")
    except Exception as e:
        messages.error(request, f"Error moving email to inbox: {str(e)}")

    return redirect("{}?email={}".format(reverse("emails_list"), email.pk))


@login_required
def email_forward(request, pk):
    """Forward email - shows form or creates draft"""
    email = get_object_or_404(EmailMessage, pk=pk)
    
    if request.method == "POST":
        if not email.account.is_connected:
            messages.error(request, "Account is not connected to Gmail.")
            return redirect("{}?email={}".format(reverse("emails_list"), email.pk))
        
        to_addresses = request.POST.get("to_addresses", "").split(",")
        to_addresses = [addr.strip() for addr in to_addresses if addr.strip()]
        
        if not to_addresses:
            messages.error(request, "Please provide at least one recipient.")
            return redirect("email_forward", pk=email.pk)
        
        # Create forward draft
        forward_subject = f"Fwd: {email.subject or 'No subject'}"
        forward_body = f"""
<div>
  <p>---------- Forwarded message ----------</p>
  <p>From: {email.from_name or email.from_address}</p>
  <p>Date: {email.date_sent.strftime('%Y-%m-%d %H:%M') if email.date_sent else 'Unknown'}</p>
  <p>Subject: {email.subject or 'No subject'}</p>
  <p>To: {', '.join(email.to_addresses)}</p>
  <br>
  {email.body_html}
</div>
"""
        
        try:
            draft = Draft.objects.create(
                account=email.account,
                email_message=email,
                to_addresses=to_addresses,
                subject=forward_subject,
                body_html=forward_body,
            )
            messages.success(request, f"Forward draft created. <a href='/drafts/{draft.pk}/edit/'>Edit draft</a>")
            return redirect("tasks_list")
        except Exception as e:
            messages.error(request, f"Error creating forward draft: {str(e)}")
            return redirect("{}?email={}".format(reverse("emails_list"), email.pk))
    
    # GET request - show forward form
    return render(request, "emails/forward.html", {"email": email})


@login_required
@require_http_methods(["POST"])
def email_reply(request, pk):
    """Reply to email - creates a draft"""
    email = get_object_or_404(EmailMessage, pk=pk)
    
    if not email.account.is_connected:
        messages.error(request, "Account is not connected to Gmail.")
        return redirect("{}?email={}".format(reverse("emails_list"), email.pk))
    
    # Create reply draft (body = draft only, no thread history)
    reply_subject = f"Re: {email.subject or 'No subject'}"
    reply_to = [email.from_address]
    reply_body = ""
    if email.account.signature_html:
        reply_body = f"<div style=\"margin-top: 20px; padding-top: 20px; border-top: 1px solid #e5e7eb;\">{email.account.signature_html}</div>"
    try:
        draft = Draft.objects.create(
            account=email.account,
            email_message=email,
            to_addresses=reply_to,
            subject=reply_subject,
            body_html=reply_body,
        )
        messages.success(request, f"Reply draft created. <a href='/drafts/{draft.pk}/edit/'>Edit draft</a>")
    except Exception as e:
        messages.error(request, f"Error creating reply draft: {str(e)}")

    return redirect("{}?email={}".format(reverse("emails_list"), email.pk))


@login_required
@require_http_methods(["POST"])
def draft_send(request, pk):
    """Send a draft. Uses from_account from POST if provided (user's connected account)."""
    from accounts.models import Account
    from mail.models import Draft

    draft = get_object_or_404(Draft, pk=pk)

    send_account = draft.account
    from_account_id = request.POST.get("from_account")
    if from_account_id:
        try:
            chosen = Account.objects.get(pk=from_account_id, users=request.user, is_connected=True)
            send_account = chosen
        except Account.DoesNotExist:
            pass

    if not send_account.is_connected:
        messages.error(request, "The chosen account is not connected.")
        return redirect("tasks_list")

    try:
        provider_services = {
            "gmail": GmailService(),
            "microsoft": MicrosoftService(),
        }
        provider_service = provider_services.get(send_account.provider)
        if not provider_service:
            messages.error(request, f"Provider '{send_account.provider}' does not support sending.")
            return redirect("tasks_list")

        to_addresses = draft.effective_to_addresses
        if not to_addresses:
            messages.error(request, "Recipient address required. Please add at least one To address.")
            return redirect("tasks_list")

        if send_account.pk == draft.account_id:
            result = provider_service.send_draft(send_account, draft.pk)
        else:
            reply_to_id = None
            thread_id = None
            if getattr(draft, "email_message", None):
                reply_to_id = draft.email_message.external_message_id
                thread_id = draft.email_message.thread.external_thread_id
            result = provider_service.send_message(
                account=send_account,
                to_addresses=to_addresses,
                subject=draft.subject or "",
                body_html=draft.body_html or "",
                cc_addresses=draft.cc_addresses or [],
                bcc_addresses=draft.bcc_addresses or [],
                reply_to_message_id=reply_to_id,
                thread_id=thread_id,
            )

        persist_sent_message(
            account=send_account,
            send_result=result,
            subject=draft.subject or "",
            from_address=send_account.email,
            to_addresses=to_addresses,
            cc_addresses=draft.cc_addresses or [],
            bcc_addresses=draft.bcc_addresses or [],
            body_html=draft.body_html or "",
        )

        messages.success(request, f"Draft '{draft.subject or 'Untitled'}' sent successfully from {send_account.email}!")
        draft.delete()
        return redirect("tasks_list")
    except Exception as e:
        messages.error(request, f"Error sending draft: {str(e)}")
        return redirect("tasks_list")


@login_required
@require_http_methods(["POST"])
def draft_send_and_mark_done(request, pk):
    """Send a draft and mark the given task as done. Uses from_account from POST if provided."""
    from accounts.models import Account
    from jobs.models import Task, TaskStatus
    from mail.models import Draft

    draft = get_object_or_404(Draft, pk=pk)

    send_account = draft.account
    from_account_id = request.POST.get("from_account")
    if from_account_id:
        try:
            chosen = Account.objects.get(pk=from_account_id, users=request.user, is_connected=True)
            send_account = chosen
        except Account.DoesNotExist:
            pass

    if not send_account.is_connected:
        messages.error(request, "The chosen account is not connected.")
        return redirect("tasks_list")

    try:
        provider_services = {
            "gmail": GmailService(),
            "microsoft": MicrosoftService(),
        }
        provider_service = provider_services.get(send_account.provider)
        if not provider_service:
            messages.error(request, f"Provider '{send_account.provider}' does not support sending.")
            return redirect("tasks_list")

        to_addresses = draft.effective_to_addresses
        if not to_addresses:
            messages.error(request, "Recipient address required. Please add at least one To address.")
            return redirect("tasks_list")

        if send_account.pk == draft.account_id:
            result = provider_service.send_draft(send_account, draft.pk)
        else:
            reply_to_id = None
            thread_id = None
            if getattr(draft, "email_message", None):
                reply_to_id = draft.email_message.external_message_id
                thread_id = draft.email_message.thread.external_thread_id
            result = provider_service.send_message(
                account=send_account,
                to_addresses=to_addresses,
                subject=draft.subject or "",
                body_html=draft.body_html or "",
                cc_addresses=draft.cc_addresses or [],
                bcc_addresses=draft.bcc_addresses or [],
                reply_to_message_id=reply_to_id,
                thread_id=thread_id,
            )

        persist_sent_message(
            account=send_account,
            send_result=result,
            subject=draft.subject or "",
            from_address=send_account.email,
            to_addresses=to_addresses,
            cc_addresses=draft.cc_addresses or [],
            bcc_addresses=draft.bcc_addresses or [],
            body_html=draft.body_html or "",
        )

        draft_email_message_id = draft.email_message_id
        draft.delete()

        task_id = request.POST.get("task_id")
        if task_id:
            try:
                task = Task.objects.get(pk=task_id, account__users=request.user)
                if task.email_message_id == draft_email_message_id:
                    task.status = TaskStatus.DONE
                    task.completed_at = timezone.now()
                    task.save()
            except (Task.DoesNotExist, ValueError):
                pass

        messages.success(request, f"Email sent from {send_account.email} and task marked as done.")
        return redirect("tasks_list")
    except Exception as e:
        messages.error(request, f"Error sending draft: {str(e)}")
        return redirect("tasks_list")


# Labels CRUD
@login_required
def label_create(request):
    if request.method == "POST":
        form = LabelForm(request.POST)
        if form.is_valid():
            try:
                label = form.save()
                messages.success(request, f"Label '{label.name}' created successfully.")
                return redirect("{}?tab=labels".format(reverse("settings")))
            except ValidationError as e:
                messages.error(request, str(e))
        else:
            # Form has errors - show them and redirect back
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
        return redirect("{}?tab=labels".format(reverse("settings")))
    else:
        # If accessed directly (not via drawer), redirect to settings
        return redirect("{}?tab=labels".format(reverse("settings")))


@login_required
def label_update(request, pk):
    label = get_object_or_404(Label, pk=pk)
    
    # Get all labels with the same name (case-insensitive) for user's accounts
    user_accounts = request.user.accounts.all() if request.user.is_authenticated else []
    labels_to_update = Label.objects.filter(
        name__iexact=label.name,
        account__in=user_accounts
    )
    
    if request.method == "POST":
        form = LabelForm(request.POST, instance=label, user=request.user)
        if form.is_valid():
            try:
                # Get the form data
                updated_label = form.save(commit=False)
                
                # Update all labels with the same name
                updated_count = 0
                for lbl in labels_to_update:
                    # Update fields that should be synced across all instances
                    lbl.prompt = updated_label.prompt
                    lbl.instructions = updated_label.instructions
                    lbl.priority = updated_label.priority
                    lbl.is_active = updated_label.is_active
                    lbl.save()
                    
                    # Update actions for each label instance
                    lbl.actions.set(updated_label.actions.all())
                    
                    # Update accounts ManyToMany - keep owner account's settings
                    if lbl.account == label.account:
                        # For the primary label, use the form's accounts
                        lbl.accounts.set(updated_label.accounts.all())
                    # For other instances, keep their existing accounts settings
                    
                    # If no accounts selected, automatically add the owner account
                    if not lbl.accounts.exists():
                        lbl.accounts.add(lbl.account)
                    
                    updated_count += 1
                
                messages.success(request, f"Label '{label.name}' updated successfully across {updated_count} account(s).")
                # Redirect back to settings if coming from settings page
                if request.GET.get('modal') == 'true' or request.GET.get('from') == 'settings' or request.headers.get('Referer', '').endswith('settings'):
                    return redirect("{}?tab=labels".format(reverse("settings")))
                return redirect("{}?tab=labels".format(reverse("settings")))
            except ValidationError as e:
                messages.error(request, str(e))
    else:
        form = LabelForm(instance=label, user=request.user)
    
    # If it's an AJAX request (for modal/drawer), return just the form content
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.GET.get('drawer') == 'true' or request.GET.get('modal') == 'true':
        return render(request, "labels/form_content.html", {"form": form, "form_url": "label_update", "drawer_id": f"edit-label-{pk}", "object_pk": pk})
    
    return render(request, "labels/form.html", {"form": form, "label": label, "title": "Edit Label"})


@login_required
def labels_add_recommended(request):
    """Add recommended labels to user's accounts"""
    if request.method != "POST":
        return redirect("{}?tab=labels".format(reverse("settings")))
    
    from automation.recommended_labels import RECOMMENDED_LABELS
    
    # Get selected label names from POST data
    selected_labels = request.POST.getlist('label_names')
    
    if not selected_labels:
        messages.warning(request, "No labels selected.")
        return redirect("{}?tab=labels".format(reverse("settings")))
    
    # Get user's accounts
    user_accounts = request.user.accounts.all() if request.user.is_authenticated else Account.objects.none()
    
    if not user_accounts.exists():
        messages.error(request, "No accounts found. Please connect an account first.")
        return redirect("{}?tab=labels".format(reverse("settings")))
    
    # Create a mapping of label name to label data
    label_data_map = {label['name']: label for label in RECOMMENDED_LABELS}
    
    created_count = 0
    skipped_count = 0
    
    # For each account, add the selected labels
    for account in user_accounts:
        for label_name in selected_labels:
            if label_name not in label_data_map:
                continue
            
            label_data = label_data_map[label_name]
            
            # Check if label already exists (case-insensitive)
            existing = Label.objects.filter(
                account=account,
                name__iexact=label_name
            ).first()
            
            if existing:
                skipped_count += 1
                continue
            
            # Create the label
            Label.objects.create(
                account=account,
                name=label_data['name'],
                prompt=label_data['prompt'],
                priority=label_data['priority'],
                is_active=True
            )
            created_count += 1
    
    if created_count > 0:
        messages.success(request, f"Successfully added {created_count} label(s).")
    if skipped_count > 0:
        messages.info(request, f"{skipped_count} label(s) already exist and were skipped.")
    
    return redirect("{}?tab=labels".format(reverse("settings")))


@require_http_methods(["POST"])
def label_delete(request, pk):
    label = get_object_or_404(Label, pk=pk)
    name = label.name
    label.delete()
    messages.success(request, f"Label '{name}' deleted successfully.")
    return redirect("{}?tab=labels".format(reverse("settings")))


# Accounts CRUD
@login_required
def accounts_list(request):
    accounts = Account.objects.all().order_by("provider", "email")
    form = AccountForm()
    return render(request, "accounts/list.html", {"accounts": accounts, "form": form})


@login_required
def account_detail(request, pk):
    from mail.sync_status import get_last_sync_error, get_sync_in_progress

    account = get_object_or_404(Account, pk=pk)
    context = {
        "account": account,
        "sync_in_progress": get_sync_in_progress(account.pk),
        "last_sync_error": get_last_sync_error(account.pk),
    }
    return render(request, "accounts/detail.html", context)


@login_required
def account_create(request):
    """Redirect directly to Gmail OAuth connection - email will be obtained from OAuth"""
    # Get authorization URL - we'll get the email from OAuth response
    # Default to normal OAuth to avoid repeated consent screens
    redirect_uri = build_oauth_redirect_uri(request, "gmail_oauth_callback")
    try:
        auth_url, state = GmailOAuthService.get_authorization_url(redirect_uri, force_reauth=False)
        # Store state in session for verification
        request.session["oauth_state"] = state
        # Don't store account_id yet - we'll create it after getting email from OAuth
        return redirect(auth_url)
    except Exception as e:
        messages.error(request, f"Error initiating OAuth: {str(e)}")
        return redirect("settings?tab=accounts")


@login_required
def account_update(request, pk):
    account = get_object_or_404(Account, pk=pk)
    if request.method == "POST":
        # For settings page, only allow updating signature and writing_style
        if request.GET.get('modal') == 'true' or request.GET.get('from') == 'settings':
            form = AccountForm(request.POST, instance=account, fields=['signature_html', 'writing_style'])
        else:
            form = AccountForm(request.POST, instance=account)
        if form.is_valid():
            try:
                account = form.save()
                messages.success(request, f"Account '{account.email}' updated successfully.")
                # Redirect back to settings if coming from settings page
                if request.GET.get('from') == 'settings' or request.GET.get('modal') == 'true' or request.headers.get('Referer', '').endswith('settings'):
                    return redirect("{}?tab=accounts".format(reverse("settings")))
                return redirect("account_detail", pk=account.pk)
            except ValidationError as e:
                messages.error(request, str(e))
    else:
        # For settings page modal, only show signature and writing_style
        if request.GET.get('modal') == 'true' or request.GET.get('from') == 'settings':
            form = AccountForm(instance=account, fields=['signature_html', 'writing_style'])
        else:
            form = AccountForm(instance=account)
    
    # If it's an AJAX request (for modal/drawer), return just the form content
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.GET.get('drawer') == 'true' or request.GET.get('modal') == 'true':
        modal_id = f"edit-account-{pk}"
        return render(request, "accounts/form_content.html", {"form": form, "form_url": "account_update", "modal_id": modal_id, "drawer_id": modal_id, "object_pk": pk})
    
    return render(
        request, "accounts/form.html", {"form": form, "account": account, "title": "Edit Account"}
    )


@login_required
@require_http_methods(["POST"])
def account_delete(request, pk):
    account = get_object_or_404(Account, pk=pk)
    email = account.email
    account.delete()
    messages.success(request, f"Account '{email}' deleted successfully.")
    return redirect("settings?tab=accounts")


@login_required
@require_http_methods(["POST"])
def account_clear_signature(request, pk):
    account = get_object_or_404(Account, pk=pk)
    account.signature_html = None
    account.save()
    messages.success(request, "Signature deleted successfully.")
    return redirect("account_detail", pk=account.pk)


@login_required
@require_http_methods(["POST"])
def account_clear_writing_style(request, pk):
    account = get_object_or_404(Account, pk=pk)
    account.writing_style = None
    account.save()
    messages.success(request, "Writing style deleted successfully.")
    return redirect("account_detail", pk=account.pk)


# Drafts CRUD (no standalone draft pages; /drafts/<pk>/ redirects to home)
@login_required
def draft_detail(request, pk):
    """Individual draft pages removed; redirect to home (tasks)."""
    return redirect("tasks_list")


@login_required
def draft_create(request):
    if request.method == "POST":
        account_id = request.POST.get("account")
        email_message_id = request.POST.get("email_message") or None
        to_addresses = request.POST.get("to_addresses", "")
        subject = request.POST.get("subject", "")
        body_html = request.POST.get("body_html", "")
        body_html = _strip_quoted_email_html(body_html)

        try:
            account = Account.objects.get(pk=account_id)
            email_message = (
                EmailMessage.objects.get(pk=email_message_id) if email_message_id else None
            )

            # Parse JSON arrays; for replies with no To, default to original sender
            to_list = json.loads(to_addresses) if to_addresses else []
            if not to_list and email_message:
                to_list = [email_message.from_address]
            cc_list = json.loads(request.POST.get("cc_addresses", "[]")) if request.POST.get(
                "cc_addresses"
            ) else []
            bcc_list = json.loads(request.POST.get("bcc_addresses", "[]")) if request.POST.get(
                "bcc_addresses"
            ) else []

            draft = Draft.objects.create(
                account=account,
                email_message=email_message,
                to_addresses=to_list,
                cc_addresses=cc_list,
                bcc_addresses=bcc_list,
                subject=subject,
                body_html=body_html,
            )
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"success": True, "draft_id": draft.pk})
            messages.success(request, f"Draft '{draft.subject or 'Untitled'}' created successfully.")
            return redirect("tasks_list")
        except (Account.DoesNotExist, EmailMessage.DoesNotExist, json.JSONDecodeError) as e:
            messages.error(request, f"Error creating draft: {str(e)}")
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"success": False, "error": str(e)}, status=400)

    accounts = Account.objects.all()
    emails = EmailMessage.objects.all()[:100]  # Limit for dropdown
    return render(request, "drafts/form.html", {"accounts": accounts, "emails": emails, "title": "Create Draft"})


@login_required
def draft_update(request, pk):
    draft = get_object_or_404(Draft, pk=pk)
    if request.method == "POST":
        draft.account = Account.objects.get(pk=request.POST.get("account"))
        if request.POST.get("email_message"):
            draft.email_message = EmailMessage.objects.get(pk=request.POST.get("email_message"))
        to_list = json.loads(request.POST.get("to_addresses", "[]"))
        if not to_list and getattr(draft, "email_message", None):
            to_list = [draft.email_message.from_address]
        draft.to_addresses = to_list
        draft.cc_addresses = json.loads(request.POST.get("cc_addresses", "[]"))
        draft.bcc_addresses = json.loads(request.POST.get("bcc_addresses", "[]"))
        draft.subject = request.POST.get("subject", "")
        draft.body_html = _strip_quoted_email_html(request.POST.get("body_html", ""))
        draft.save()
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": True, "draft_id": draft.pk})
        messages.success(request, f"Draft '{draft.subject or 'Untitled'}' updated successfully.")
        return redirect("tasks_list")

    accounts = Account.objects.all()
    emails = EmailMessage.objects.all()[:100]
    return render(
        request,
        "drafts/form.html",
        {"draft": draft, "accounts": accounts, "emails": emails, "title": "Edit Draft"},
    )


@login_required
@require_http_methods(["POST"])
def draft_rewrite(request, pk):
    """Rewrite a draft using AI based on user feedback"""
    from django.http import JsonResponse
    from automation.services import OpenAIClient
    
    draft = get_object_or_404(Draft, pk=pk)
    user_feedback = request.POST.get("feedback", "").strip()
    
    if not user_feedback:
        return JsonResponse({"success": False, "error": "Feedback is required"}, status=400)
    
    if not draft.email_message:
        return JsonResponse({"success": False, "error": "Draft must be associated with an email"}, status=400)
    
    # Build email context from thread
    email = draft.email_message
    email_context = f"Subject: {email.subject or '(No subject)'}\nFrom: {email.from_name or email.from_address} ({email.from_address})\nBody:\n{email.body_html or ''}"
    
    # Include thread messages from DB (sync already stores full threads)
    if email.thread:
        thread_messages = list(
            email.thread.messages.values("from_name", "from_address", "subject", "body_html").order_by("-date_sent")
        )
        if thread_messages:
            thread_context = "\n\nEmail Thread:\n"
            for msg in thread_messages[:5]:
                thread_context += f"From: {msg.get('from_name') or msg.get('from_address', '')}\n"
                thread_context += f"Subject: {msg.get('subject', '')}\n"
                thread_context += f"Body: {(msg.get('body_html') or '')[:500]}\n\n"
            email_context += thread_context
    
    # Get writing style if available
    writing_style = email.account.writing_style if email.account.writing_style else None
    
    # Extract signature from current draft (if present) to preserve it
    current_body = draft.body_html or ""
    signature = email.account.signature_html or ""
    body_without_signature = current_body
    if signature and signature in current_body:
        # Remove signature from body before rewriting
        body_without_signature = current_body.replace(signature, "").strip()
        # Also remove the separator if present
        separator = '<div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #e5e7eb;"></div>'
        body_without_signature = body_without_signature.replace(separator, "").strip()
    
    # Rewrite the draft (without signature)
    client = OpenAIClient()
    rewritten_body = client.rewrite_draft(
        email_context=email_context,
        current_draft=body_without_signature,
        user_feedback=user_feedback,
        writing_style=writing_style
    )
    
    # Append signature back to rewritten body
    if signature:
        separator = '<div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #e5e7eb;"></div>'
        rewritten_body = rewritten_body + separator + signature
    
    # Update the draft
    draft.body_html = rewritten_body
    draft.save()
    
    return JsonResponse({
        "success": True,
        "body_html": rewritten_body
    })


@login_required
@require_http_methods(["POST"])
def draft_delete(request, pk):
    draft = get_object_or_404(Draft, pk=pk)
    subject = draft.subject or f"Draft {draft.pk}"
    draft.delete()
    messages.success(request, f"Draft '{subject}' deleted successfully.")
    return redirect("tasks_list")


# Actions CRUD
@login_required
def actions_list(request):
    actions = Action.objects.select_related("account").order_by("name")
    form = ActionForm()
    return render(request, "actions/list.html", {"actions": actions, "form": form})


@login_required
def action_create(request):
    if request.method == "POST":
        form = ActionForm(request.POST)
        if form.is_valid():
            try:
                action = form.save()
                messages.success(request, f"Action '{action.name}' created successfully.")
                return redirect("settings?tab=actions")
            except ValidationError as e:
                messages.error(request, str(e))
        else:
            # Form has errors - show them and redirect back
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
        return redirect("settings?tab=actions")
    else:
        # If accessed directly (not via drawer), redirect to settings
        return redirect("settings?tab=actions")


@login_required
def action_update(request, pk):
    action = get_object_or_404(Action, pk=pk)
    
    # Get all actions with the same name (case-insensitive) for user's accounts
    user_accounts = request.user.accounts.all() if request.user.is_authenticated else []
    actions_to_update = Action.objects.filter(
        name__iexact=action.name,
        account__in=user_accounts
    )
    
    if request.method == "POST":
        form = ActionForm(request.POST, instance=action)
        if form.is_valid():
            try:
                # Get the form data
                updated_action = form.save(commit=False)
                
                # Update all actions with the same name
                updated_count = 0
                for act in actions_to_update:
                    # Update fields that should be synced across all instances
                    act.instructions = updated_action.instructions
                    act.function = updated_action.function
                    act.mcp_tool_name = updated_action.mcp_tool_name
                    act.tool_description = updated_action.tool_description
                    act.save()
                    updated_count += 1
                
                messages.success(request, f"Action '{action.name}' updated successfully across {updated_count} account(s).")
                return redirect("{}?tab=actions".format(reverse("settings")))
            except ValidationError as e:
                messages.error(request, str(e))
    else:
        form = ActionForm(instance=action)
    return render(
        request, "actions/form.html", {"form": form, "action": action, "title": "Edit Action"}
    )


@login_required
@require_http_methods(["POST"])
def action_delete(request, pk):
    action = get_object_or_404(Action, pk=pk)
    name = action.name
    action.delete()
    messages.success(request, f"Action '{name}' deleted successfully.")
    return redirect("actions_list")




# Email Labels
@login_required
@require_http_methods(["POST"])
def email_label_add(request, email_id):
    email = get_object_or_404(EmailMessage, pk=email_id)
    label_id = request.POST.get("label_id")
    if label_id:
        label = get_object_or_404(Label, pk=label_id)
        EmailLabel.objects.get_or_create(email_message=email, label=label)
        messages.success(request, f"Label '{label.name}' added to email.")
    return redirect("{}?email={}".format(reverse("emails_list"), email.pk))


@login_required
@require_http_methods(["POST"])
def email_label_remove(request, email_id, label_id):
    email = get_object_or_404(EmailMessage, pk=email_id)
    label = get_object_or_404(Label, pk=label_id)
    EmailLabel.objects.filter(email_message=email, label=label).delete()
    messages.success(request, f"Label '{label.name}' removed from email.")
    return redirect("{}?email={}".format(reverse("emails_list"), email.pk))


# Settings
@login_required
def settings_view(request):
    """Settings page combining accounts, actions, and labels"""
    # Get data for each section
    tab = request.GET.get('tab', 'accounts')
    
    # Get user's accounts
    user_accounts = request.user.accounts.all() if request.user.is_authenticated else Account.objects.none()
    
    # Actions list - filter to show only actions for user's accounts
    actions_queryset = Action.objects.filter(account__in=user_accounts).select_related("account").order_by("name")
    
    # Group actions by name (case-insensitive)
    actions_by_name = {}
    for action in actions_queryset:
        name_key = action.name.lower()
        if name_key not in actions_by_name:
            actions_by_name[name_key] = {
                'name': action.name,
                'instances': [],
                'primary': action  # Use first instance as primary for display
            }
        actions_by_name[name_key]['instances'].append(action)
    
    # Convert to list of grouped actions and sort alphabetically by name
    actions = sorted(list(actions_by_name.values()), key=lambda x: x['name'].lower())
    
    # Labels list - filter to show labels available to user's accounts
    from django.db.models import Q
    labels_queryset = Label.objects.filter(
        Q(account__in=user_accounts) | Q(accounts__in=user_accounts)
    ).select_related("account").prefetch_related("actions", "accounts").distinct().order_by("name")
    
    # Group labels by name (case-insensitive)
    labels_by_name = {}
    for label in labels_queryset:
        name_key = label.name.lower()
        if name_key not in labels_by_name:
            labels_by_name[name_key] = {
                'name': label.name,
                'instances': [],
                'primary': label  # Use first instance as primary for display
            }
        labels_by_name[name_key]['instances'].append(label)
    
    # Convert to list of grouped labels and sort alphabetically by name
    labels = sorted(list(labels_by_name.values()), key=lambda x: x['name'].lower())
    
    # Accounts list - filter to show only user's accounts
    accounts = user_accounts.order_by("email")
    connected_account_count = user_accounts.filter(is_connected=True).count()
    
    # Check account connection status and token validity
    account_statuses = {}
    for account in accounts:
        has_token_error = False
        token_error_message = None
        
        if account.is_connected:
            # Check if token is valid (refresh logic will handle proactive refresh)
            try:
                if account.provider == 'gmail':
                    credentials = GmailOAuthService.get_valid_credentials(account)
                    if not credentials:
                        has_token_error = True
                        token_error_message = "Unable to get valid credentials. Please reconnect your account."
                elif account.provider == 'microsoft':
                    credentials = MicrosoftEmailOAuthService.get_valid_credentials(account)
                    if not credentials:
                        has_token_error = True
                        token_error_message = "Unable to get valid credentials. Please reconnect your account."
            except Exception as e:
                logger.warning("Error checking token for account %s: %s", account.pk, e)
                has_token_error = True
                token_error_message = "Unable to verify token. Please reconnect your account."
        
        account_statuses[account.pk] = {
            'has_token_error': has_token_error,
            'token_error_message': token_error_message or "Your account is not connected. Please reconnect to sync emails.",
        }
    
    # Forms for drawers
    action_form = ActionForm()
    label_form = LabelForm(user=request.user)
    
    # Get recommended labels and check which ones already exist
    from automation.recommended_labels import RECOMMENDED_LABELS, LABELS_BY_CATEGORY, CATEGORIES
    
    # Get existing label names for the user's accounts (case-insensitive)
    existing_label_names = set()
    if request.user.is_authenticated:
        existing_label_names = {
            label_name.lower() 
            for label_name in Label.objects.filter(account__in=user_accounts).values_list('name', flat=True)
        }
    
    # Mark which recommended labels already exist
    recommended_labels_with_status = []
    for label_data in RECOMMENDED_LABELS:
        label_data_copy = label_data.copy()
        label_data_copy['exists'] = label_data['name'].lower() in existing_label_names
        recommended_labels_with_status.append(label_data_copy)
    
    # Group by category with status
    recommended_by_category = {}
    for category in CATEGORIES:
        recommended_by_category[category] = [
            label for label in recommended_labels_with_status 
            if label['category'] == category
        ]
    
    return render(request, "settings.html", {
        "tab": tab,
        "actions": actions,
        "labels": labels,
        "accounts": accounts,
        "connected_account_count": connected_account_count,
        "account_statuses": account_statuses,
        "action_form": action_form,
        "label_form": label_form,
        "recommended_labels": recommended_labels_with_status,
        "recommended_by_category": recommended_by_category,
        "recommended_categories": CATEGORIES,
    })
