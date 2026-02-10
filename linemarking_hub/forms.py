from django import forms

from accounts.models import Account
from automation.models import Action, Label
from jobs.models import Job, Task, JobStatus, TaskStatus


class JobForm(forms.ModelForm):
    # User-friendly fields instead of JSON
    customer_names = forms.CharField(
        required=False,
        label="Customer Names",
        widget=forms.TextInput(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white", "placeholder": "John Doe, Jane Smith"}),
        help_text="Enter names separated by commas"
    )
    customer_emails = forms.CharField(
        required=False,
        label="Customer Emails",
        widget=forms.TextInput(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white", "placeholder": "john@example.com, jane@example.com"}),
        help_text="Enter emails separated by commas"
    )
    dates_input = forms.CharField(
        required=False,
        label="Dates",
        widget=forms.TextInput(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white", "type": "text", "placeholder": "2025-02-10, 2025-02-12"}),
        help_text="Enter dates in YYYY-MM-DD format, separated by commas"
    )
    
    class Meta:
        model = Job
        fields = [
            "title",
            "status",
            "site_address",
            "description",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white"}),
            "status": forms.Select(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white"}),
            "site_address": forms.Textarea(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white", "rows": 2}),
            "description": forms.Textarea(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white", "rows": 4}),
        }
    
    def __init__(self, *args, **kwargs):
        account = kwargs.pop('account', None)
        super().__init__(*args, **kwargs)
        # Set default status and make it optional
        if not self.instance.pk:
            self.fields['status'].initial = JobStatus.DRAFT
        
        # Make status optional
        self.fields['status'].required = False
        
        # Populate user-friendly fields from JSON if editing
        if self.instance.pk:
            if self.instance.customer_name:
                self.fields['customer_names'].initial = ', '.join(self.instance.customer_name) if isinstance(self.instance.customer_name, list) else ''
            if self.instance.customer_email:
                self.fields['customer_emails'].initial = ', '.join(self.instance.customer_email) if isinstance(self.instance.customer_email, list) else ''
            if self.instance.dates:
                dates_list = self.instance.dates if isinstance(self.instance.dates, list) else []
                self.fields['dates_input'].initial = ', '.join(dates_list)
        
        # Store account for save
        self.account = account
        
        # Reorder fields for better UX: title, description, customer info, site, dates, status
        field_order = ['title', 'description', 'customer_names', 'customer_emails', 'site_address', 'dates_input', 'status']
        # Get all fields in the desired order
        ordered_fields = {}
        for field_name in field_order:
            if field_name in self.fields:
                ordered_fields[field_name] = self.fields.pop(field_name)
        # Add any remaining fields
        ordered_fields.update(self.fields)
        self.fields = ordered_fields
    
    def clean_customer_names(self):
        names = self.cleaned_data.get('customer_names', '')
        if names:
            return [name.strip() for name in names.split(',') if name.strip()]
        return []
    
    def clean_customer_emails(self):
        emails = self.cleaned_data.get('customer_emails', '')
        if emails:
            return [email.strip() for email in emails.split(',') if email.strip()]
        return []
    
    def clean_dates_input(self):
        dates_str = self.cleaned_data.get('dates_input', '')
        if dates_str:
            dates = [date.strip() for date in dates_str.split(',') if date.strip()]
            # Validate date format
            from datetime import datetime
            validated_dates = []
            for date_str in dates:
                try:
                    datetime.strptime(date_str, "%Y-%m-%d")
                    validated_dates.append(date_str)
                except ValueError:
                    raise forms.ValidationError(f"Invalid date format: {date_str}. Use YYYY-MM-DD format.")
            return validated_dates
        return []
    
    def save(self, commit=True):
        job = super().save(commit=False)
        # Convert user-friendly fields to JSON
        job.customer_name = self.cleaned_data.get('customer_names', [])
        job.customer_email = self.cleaned_data.get('customer_emails', [])
        job.dates = self.cleaned_data.get('dates_input', [])
        # Set account automatically if not set
        if not job.account_id and self.account:
            job.account = self.account
        elif not job.account_id:
            # Fallback to first available account
            from accounts.models import Account
            account = Account.objects.filter(is_connected=True).first()
            if account:
                job.account = account
        if commit:
            job.save()
        return job


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = [
            "title",
            "description",
            "due_at",
            "priority",
            "status",
            "job",
        ]
        field_order = ["title", "description", "due_at", "priority", "status", "job"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white", "placeholder": "Task title"}),
            "description": forms.Textarea(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white", "rows": 4, "placeholder": "Task description"}),
            "due_at": forms.DateTimeInput(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white", "type": "datetime-local"}),
            "priority": forms.NumberInput(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white", "min": 1, "max": 5, "value": 1}),
            "status": forms.Select(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white"}),
            "job": forms.Select(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white"}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        account = kwargs.pop('account', None)
        email_message = kwargs.pop('email_message', None)
        super().__init__(*args, **kwargs)
        
        # Set default status and make it optional
        if not self.instance.pk:
            self.fields['status'].initial = TaskStatus.PENDING
            self.fields['priority'].initial = 1
        
        # Make status and priority optional
        self.fields['status'].required = False
        self.fields['priority'].required = False
        self.fields['title'].required = False
        self.fields['description'].required = False
        self.fields['due_at'].required = False
        
        # Get account from user or use provided account
        if account:
            account_obj = account
        elif user:
            # Try to get first available account for user
            from accounts.models import Account
            account_obj = Account.objects.filter(is_connected=True).first()
        else:
            account_obj = None
        
        # Store account and email_message for save
        self.account = account_obj
        self.email_message = email_message
        
        # Make job optional and only show if there are jobs
        self.fields['job'].required = False
        if account_obj:
            self.fields['job'].queryset = Job.objects.filter(account=account_obj).order_by('-created_at')
        else:
            self.fields['job'].queryset = Job.objects.none()
        
        # Hide job field if no jobs available and not editing existing task with job
        if not self.fields['job'].queryset.exists() and not self.instance.job_id:
            self.fields['job'].widget = forms.HiddenInput()
    
    def save(self, commit=True):
        task = super().save(commit=False)
        # Set account automatically if not set
        if not task.account_id and self.account:
            task.account = self.account
        elif not task.account_id:
            # Fallback to first available account
            from accounts.models import Account
            account = Account.objects.filter(is_connected=True).first()
            if account:
                task.account = account
        
        # Set email_message if provided
        if self.email_message and not task.email_message_id:
            task.email_message = self.email_message
        
        if commit:
            task.save()
        return task


class LabelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter actions by account if account is set
        if self.instance and self.instance.pk and self.instance.account:
            self.fields['actions'].queryset = Action.objects.filter(account=self.instance.account)
        elif 'account' in self.data:
            try:
                account_id = self.data.get('account')
                if account_id:
                    self.fields['actions'].queryset = Action.objects.filter(account_id=account_id)
            except (ValueError, TypeError):
                pass
    
    class Meta:
        model = Label
        fields = ["account", "name", "prompt", "instructions", "priority", "is_active", "actions"]
        widgets = {
            "account": forms.Select(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white"}),
            "name": forms.TextInput(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white"}),
            "prompt": forms.Textarea(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white", "rows": 4, "placeholder": "When this label applies (classification criteria)"}),
            "instructions": forms.Textarea(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white", "rows": 5, "placeholder": "What the AI should do when this label applies (business logic)"}),
            "priority": forms.NumberInput(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white", "min": 1, "max": 100, "value": 1}),
            "is_active": forms.CheckboxInput(attrs={"class": "h-4 w-4 rounded border-gray-300 text-cyan-600 focus:ring-cyan-500"}),
            "actions": forms.SelectMultiple(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white", "size": 5}),
        }


class AccountForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ["provider", "email", "signature_html", "writing_style"]
        widgets = {
            "provider": forms.Select(attrs={"class": "w-full px-4 py-3 rounded-xl border-2 border-slate-200 bg-white text-slate-900 focus:border-cyan-400 focus:ring-2 focus:ring-cyan-200 outline-none transition-all"}),
            "email": forms.EmailInput(attrs={"class": "w-full px-4 py-3 rounded-xl border-2 border-slate-200 bg-white text-slate-900 focus:border-cyan-400 focus:ring-2 focus:ring-cyan-200 outline-none transition-all"}),
            "signature_html": forms.Textarea(attrs={"class": "w-full px-4 py-3 rounded-xl border-2 border-slate-200 bg-white text-slate-900 focus:border-cyan-400 focus:ring-2 focus:ring-cyan-200 outline-none transition-all", "rows": 8}),
            "writing_style": forms.Textarea(attrs={"class": "w-full px-4 py-3 rounded-xl border-2 border-slate-200 bg-white text-slate-900 focus:border-cyan-400 focus:ring-2 focus:ring-cyan-200 outline-none transition-all", "rows": 5}),
        }


class ActionForm(forms.ModelForm):
    class Meta:
        model = Action
        fields = ["account", "name", "function", "instructions", "mcp_tool_name", "tool_description"]
        widgets = {
            "account": forms.Select(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white"}),
            "name": forms.TextInput(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white"}),
            "function": forms.Select(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white"}),
            "instructions": forms.Textarea(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white", "rows": 4}),
            "mcp_tool_name": forms.TextInput(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white", "placeholder": "Optional: custom tool name for MCP"}),
            "tool_description": forms.Textarea(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white", "rows": 3, "placeholder": "Description for AI when using this action"}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set function choices
        self.fields["function"].widget = forms.Select(choices=[
            ("draft_reply", "Draft Reply"),
            ("create_task", "Create Task"),
            ("notify", "Notify"),
            ("schedule", "Schedule"),
            ("forward", "Forward"),
            ("archive", "Archive"),
        ], attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white"})


