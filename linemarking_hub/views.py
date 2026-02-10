import json
from datetime import datetime
from django.contrib import messages
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
from automation.models import Action, EmailLabel, Label
from jobs.models import Job, Task
from mail.models import Draft, DraftAttachment, EmailMessage, EmailThread
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
    
    # Get first available connected account for forms
    from accounts.models import Account
    account = Account.objects.filter(is_connected=True).first()
    
    # Initialize filter form with GET parameters
    filter_form = TaskFilterForm(request.GET, user=request.user, account=account)
    
    # Get all tasks
    tasks = Task.objects.select_related("account", "job", "email_message").prefetch_related(
        "email_message__labels__label"
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
                    email_q |= Q(email_message__from_address__icontains=email) | Q(email_message__from_name__icontains=email)
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
    
    form = TaskForm(user=request.user, account=account)
    
    return render(request, "tasks/list.html", {
        "tasks_by_priority": dict(tasks_by_priority),
        "all_tasks": all_tasks,
        "form": form,
        "filter_form": filter_form,
        "search_query": search_query
    })


@login_required
def task_detail(request, pk):
    # Redirect to tasks list with task parameter to open modal
    from django.shortcuts import redirect
    from django.urls import reverse
    return redirect(reverse("tasks_list") + f"?task={pk}", permanent=False)


@login_required
def task_create(request):
    # Get first available connected account
    from accounts.models import Account
    account = Account.objects.filter(is_connected=True).first()
    
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
    task = get_object_or_404(Task, pk=pk)
    # Get account from task or first available
    account = task.account if task.account else None
    if not account:
        from accounts.models import Account
        account = Account.objects.filter(is_connected=True).first()
    
    if request.method == "POST":
        form = TaskForm(request.POST, instance=task, user=request.user, account=account)
        if form.is_valid():
            try:
                task = form.save()
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
    task = get_object_or_404(Task, pk=pk)
    title = task.title or f"Task {task.pk}"
    task.delete()
    messages.success(request, f"Task '{title}' deleted successfully.")
    return redirect("tasks_list")


# Emails CRUD
@login_required
def emails_list(request):
    emails = EmailMessage.objects.select_related("account", "thread").prefetch_related(
        "labels__label"
    ).order_by("-date_sent", "-created_at")
    return render(request, "emails/list.html", {"emails": emails})


@login_required
def email_detail(request, pk):
    email = get_object_or_404(
        EmailMessage.objects.select_related("account", "thread").prefetch_related(
            "labels__label", "tasks"
        ),
        pk=pk,
    )
    
    # Get thread messages if account is connected
    thread_messages = []
    if email.account.is_connected and email.thread:
        try:
            from mail.services import GmailService
            gmail_service = GmailService()
            thread_messages = gmail_service.get_thread_messages(
                email.account, email.thread.external_thread_id
            )
            # Sort by date
            thread_messages.sort(key=lambda x: x.get("date_sent") or datetime.min, reverse=True)
        except Exception:
            pass
    
    # Get drafts for this email
    drafts = Draft.objects.filter(account=email.account, email_message=email).order_by("-updated_at")
    
    return render(
        request,
        "emails/detail.html",
        {
            "email": email,
            "thread_messages": thread_messages,
            "drafts": drafts,
        },
    )


@login_required
@require_http_methods(["POST"])
def email_delete(request, pk):
    email = get_object_or_404(EmailMessage, pk=pk)
    subject = email.subject or f"Email {email.pk}"
    
    # Delete from Gmail if connected
    if email.account.is_connected:
        try:
            from mail.services import GmailService
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
        return redirect("email_detail", pk=email.pk)
    
    try:
        from mail.services import GmailService
        gmail_service = GmailService()
        gmail_service.archive_message(email.account, email.external_message_id)
        messages.success(request, f"Email '{email.subject or 'Untitled'}' archived successfully.")
    except Exception as e:
        messages.error(request, f"Error archiving email: {str(e)}")
    
    return redirect("email_detail", pk=email.pk)


@login_required
def email_forward(request, pk):
    """Forward email - shows form or creates draft"""
    email = get_object_or_404(EmailMessage, pk=pk)
    
    if request.method == "POST":
        if not email.account.is_connected:
            messages.error(request, "Account is not connected to Gmail.")
            return redirect("email_detail", pk=email.pk)
        
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
            return redirect("draft_detail", pk=draft.pk)
        except Exception as e:
            messages.error(request, f"Error creating forward draft: {str(e)}")
            return redirect("email_detail", pk=email.pk)
    
    # GET request - show forward form
    return render(request, "emails/forward.html", {"email": email})


@login_required
@require_http_methods(["POST"])
def email_reply(request, pk):
    """Reply to email - creates a draft"""
    email = get_object_or_404(EmailMessage, pk=pk)
    
    if not email.account.is_connected:
        messages.error(request, "Account is not connected to Gmail.")
        return redirect("email_detail", pk=email.pk)
    
    # Create reply draft
    reply_subject = f"Re: {email.subject or 'No subject'}"
    reply_to = [email.from_address]
    
    # Include original message
    reply_body = f"""
<div>
  <p>On {email.date_sent.strftime('%Y-%m-%d %H:%M') if email.date_sent else 'date'}, {email.from_name or email.from_address} wrote:</p>
  <blockquote style="border-left: 2px solid #ccc; padding-left: 10px; margin-left: 0;">
    {email.body_html}
  </blockquote>
</div>
"""
    
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
    
    return redirect("email_detail", pk=email.pk)


@login_required
@require_http_methods(["POST"])
def draft_send(request, pk):
    """Send a draft via Gmail"""
    from mail.models import Draft
    
    draft = get_object_or_404(Draft, pk=pk)
    
    if not draft.account.is_connected:
        messages.error(request, "Account is not connected to Gmail.")
        return redirect("draft_detail", pk=draft.pk)
    
    try:
        from mail.services import GmailService
        gmail_service = GmailService()
        result = gmail_service.send_draft(draft.account, draft.pk)
        
        # Create EmailMessage record for sent email
        from mail.models import EmailMessage, EmailThread
        thread, _ = EmailThread.objects.get_or_create(
            account=draft.account,
            external_thread_id=result.get("threadId", ""),
        )
        
        EmailMessage.objects.create(
            account=draft.account,
            thread=thread,
            external_message_id=result["id"],
            subject=draft.subject or "",
            from_address=draft.account.email,
            to_addresses=draft.to_addresses or [],
            cc_addresses=draft.cc_addresses or [],
            bcc_addresses=draft.bcc_addresses or [],
            body_html=draft.body_html or "",
            date_sent=timezone.now(),
        )
        
        messages.success(request, f"Draft '{draft.subject or 'Untitled'}' sent successfully!")
        draft.delete()  # Remove draft after sending
        return redirect("drafts_list")
    except Exception as e:
        messages.error(request, f"Error sending draft: {str(e)}")
        return redirect("draft_detail", pk=draft.pk)


# Labels CRUD
@login_required
def labels_list(request):
    labels = Label.objects.select_related("account").prefetch_related("actions").order_by(
        "name"
    )
    form = LabelForm()
    return render(request, "labels/list.html", {"labels": labels, "form": form})


@login_required
def label_detail(request, pk):
    label = get_object_or_404(
        Label.objects.select_related("account").prefetch_related("actions"),
        pk=pk,
    )
    return render(request, "labels/detail.html", {"label": label})


@login_required
def label_create(request):
    if request.method == "POST":
        form = LabelForm(request.POST)
        if form.is_valid():
            try:
                label = form.save()
                messages.success(request, f"Label '{label.name}' created successfully.")
                return redirect("settings?tab=labels")
            except ValidationError as e:
                messages.error(request, str(e))
        else:
            # Form has errors - show them and redirect back
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
        return redirect("settings?tab=labels")
    else:
        # If accessed directly (not via drawer), redirect to settings
        return redirect("settings?tab=labels")


@login_required
def label_update(request, pk):
    label = get_object_or_404(Label, pk=pk)
    if request.method == "POST":
        form = LabelForm(request.POST, instance=label)
        if form.is_valid():
            try:
                label = form.save()
                messages.success(request, f"Label '{label.name}' updated successfully.")
                return redirect("label_detail", pk=label.pk)
            except ValidationError as e:
                messages.error(request, str(e))
    else:
        form = LabelForm(instance=label)
    return render(request, "labels/form.html", {"form": form, "label": label, "title": "Edit Label"})


@login_required
@require_http_methods(["POST"])
def label_delete(request, pk):
    label = get_object_or_404(Label, pk=pk)
    name = label.name
    label.delete()
    messages.success(request, f"Label '{name}' deleted successfully.")
    return redirect("labels_list")


# Accounts CRUD
@login_required
def accounts_list(request):
    accounts = Account.objects.all().order_by("provider", "email")
    form = AccountForm()
    return render(request, "accounts/list.html", {"accounts": accounts, "form": form})


@login_required
def account_detail(request, pk):
    account = get_object_or_404(Account, pk=pk)
    return render(request, "accounts/detail.html", {"account": account})


@login_required
def account_create(request):
    """Redirect directly to Gmail OAuth connection - email will be obtained from OAuth"""
    from django.shortcuts import redirect
    from django.urls import reverse
    from accounts.services import GmailOAuthService
    
    # Get authorization URL - we'll get the email from OAuth response
    # Force re-auth to ensure we get all required scopes
    redirect_uri = request.build_absolute_uri(reverse("gmail_oauth_callback"))
    try:
        auth_url, state = GmailOAuthService.get_authorization_url(redirect_uri, force_reauth=True)
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
        form = AccountForm(request.POST, instance=account)
        if form.is_valid():
            try:
                account = form.save()
                messages.success(request, f"Account '{account.email}' updated successfully.")
                return redirect("account_detail", pk=account.pk)
            except ValidationError as e:
                messages.error(request, str(e))
    else:
        form = AccountForm(instance=account)
    
    # If it's an AJAX request (for drawer), return just the form content
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.GET.get('drawer') == 'true':
        return render(request, "accounts/form_content.html", {"form": form, "form_url": "account_update", "drawer_id": f"edit-account-{pk}", "object_pk": pk})
    
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


# Drafts CRUD
@login_required
def drafts_list(request):
    drafts = Draft.objects.select_related("account", "email_message").prefetch_related(
        "attachments"
    ).order_by("-updated_at")
    accounts = Account.objects.all()
    emails = EmailMessage.objects.all()[:100]  # Limit for dropdown
    return render(request, "drafts/list.html", {"drafts": drafts, "accounts": accounts, "emails": emails})


@login_required
def draft_detail(request, pk):
    draft = get_object_or_404(
        Draft.objects.select_related("account", "email_message").prefetch_related("attachments"),
        pk=pk,
    )
    return render(request, "drafts/detail.html", {"draft": draft})


@login_required
def draft_create(request):
    if request.method == "POST":
        account_id = request.POST.get("account")
        email_message_id = request.POST.get("email_message") or None
        to_addresses = request.POST.get("to_addresses", "")
        subject = request.POST.get("subject", "")
        body_html = request.POST.get("body_html", "")

        try:
            account = Account.objects.get(pk=account_id)
            email_message = (
                EmailMessage.objects.get(pk=email_message_id) if email_message_id else None
            )

            # Parse JSON arrays
            to_list = json.loads(to_addresses) if to_addresses else []
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
            messages.success(request, f"Draft '{draft.subject or 'Untitled'}' created successfully.")
            return redirect("draft_detail", pk=draft.pk)
        except (Account.DoesNotExist, EmailMessage.DoesNotExist, json.JSONDecodeError) as e:
            messages.error(request, f"Error creating draft: {str(e)}")

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
        draft.to_addresses = json.loads(request.POST.get("to_addresses", "[]"))
        draft.cc_addresses = json.loads(request.POST.get("cc_addresses", "[]"))
        draft.bcc_addresses = json.loads(request.POST.get("bcc_addresses", "[]"))
        draft.subject = request.POST.get("subject", "")
        draft.body_html = request.POST.get("body_html", "")
        draft.save()
        messages.success(request, f"Draft '{draft.subject or 'Untitled'}' updated successfully.")
        return redirect("draft_detail", pk=draft.pk)

    accounts = Account.objects.all()
    emails = EmailMessage.objects.all()[:100]
    return render(
        request,
        "drafts/form.html",
        {"draft": draft, "accounts": accounts, "emails": emails, "title": "Edit Draft"},
    )


@login_required
@require_http_methods(["POST"])
def draft_delete(request, pk):
    draft = get_object_or_404(Draft, pk=pk)
    subject = draft.subject or f"Draft {draft.pk}"
    draft.delete()
    messages.success(request, f"Draft '{subject}' deleted successfully.")
    return redirect("drafts_list")


# Actions CRUD
@login_required
def actions_list(request):
    actions = Action.objects.select_related("account").order_by("name")
    form = ActionForm()
    return render(request, "actions/list.html", {"actions": actions, "form": form})


@login_required
def action_detail(request, pk):
    action = get_object_or_404(Action.objects.select_related("account"), pk=pk)
    # Get labels that use this action (now direct ManyToMany)
    labels = action.labels.all().order_by("-priority", "name")
    return render(request, "actions/detail.html", {"action": action, "labels": labels})


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
    if request.method == "POST":
        form = ActionForm(request.POST, instance=action)
        if form.is_valid():
            try:
                action = form.save()
                messages.success(request, f"Action '{action.name}' updated successfully.")
                return redirect("action_detail", pk=action.pk)
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
    return redirect("email_detail", pk=email.pk)


@login_required
@require_http_methods(["POST"])
def email_label_remove(request, email_id, label_id):
    email = get_object_or_404(EmailMessage, pk=email_id)
    label = get_object_or_404(Label, pk=label_id)
    EmailLabel.objects.filter(email_message=email, label=label).delete()
    messages.success(request, f"Label '{label.name}' removed from email.")
    return redirect("email_detail", pk=email.pk)


# Settings
@login_required
def settings_view(request):
    """Settings page combining accounts, actions, and labels"""
    # Get data for each section
    tab = request.GET.get('tab', 'accounts')
    
    # Actions list
    actions = Action.objects.select_related("account").order_by("name")
    
    # Labels list (now includes all SOP functionality)
    labels = Label.objects.select_related("account").prefetch_related("actions").order_by("-priority", "name")
    
    # Accounts list
    accounts = Account.objects.order_by("email")
    
    # Forms for drawers
    action_form = ActionForm()
    label_form = LabelForm()
    
    return render(request, "settings.html", {
        "tab": tab,
        "actions": actions,
        "labels": labels,
        "accounts": accounts,
        "action_form": action_form,
        "label_form": label_form,
    })
