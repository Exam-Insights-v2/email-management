from django import forms

from accounts.models import Account
from automation.models import Action, Label, LabelAction
from jobs.models import Job, Task, JobStatus, TaskStatus


class JobForm(forms.ModelForm):
    customer_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white", "placeholder": "[\"Name 1\", \"Name 2\"]"}),
        help_text="Enter as JSON array, e.g. [\"Name 1\", \"Name 2\"]"
    )
    customer_email = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white", "placeholder": "[\"email1@example.com\", \"email2@example.com\"]"}),
        help_text="Enter as JSON array, e.g. [\"email1@example.com\"]"
    )
    dates = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white", "placeholder": "[\"2025-02-10\", \"2025-02-12\"]"}),
        help_text="Enter as JSON array, e.g. [\"2025-02-10\", \"2025-02-12\"]"
    )
    
    class Meta:
        model = Job
        fields = [
            "account",
            "title",
            "status",
            "customer_name",
            "customer_email",
            "site_address",
            "description",
            "dates",
        ]
        widgets = {
            "account": forms.Select(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white"}),
            "title": forms.TextInput(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white"}),
            "status": forms.Select(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white"}),
            "site_address": forms.Textarea(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white", "rows": 2}),
            "description": forms.Textarea(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white", "rows": 4}),
        }


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = [
            "account",
            "job",
            "email_message",
            "status",
            "priority",
            "title",
            "description",
            "due_at",
        ]
        widgets = {
            "account": forms.Select(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white"}),
            "job": forms.Select(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white"}),
            "email_message": forms.Select(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white"}),
            "status": forms.Select(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white"}),
            "priority": forms.NumberInput(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white", "min": 1, "max": 4}),
            "title": forms.TextInput(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white"}),
            "description": forms.Textarea(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white", "rows": 4}),
            "due_at": forms.DateTimeInput(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white", "type": "datetime-local"}),
        }


class LabelForm(forms.ModelForm):
    class Meta:
        model = Label
        fields = ["account", "name", "prompt"]
        widgets = {
            "account": forms.Select(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white"}),
            "name": forms.TextInput(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white"}),
            "prompt": forms.Textarea(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white", "rows": 4}),
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
        fields = ["account", "name", "function", "instructions"]
        widgets = {
            "account": forms.Select(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white"}),
            "name": forms.TextInput(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white"}),
            "function": forms.TextInput(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white"}),
            "instructions": forms.Textarea(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white", "rows": 4}),
        }


class LabelActionForm(forms.ModelForm):
    class Meta:
        model = LabelAction
        fields = ["label", "action", "order"]
        widgets = {
            "label": forms.Select(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white"}),
            "action": forms.Select(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white"}),
            "order": forms.NumberInput(attrs={"class": "w-full px-3 py-2 border border-slate-300 rounded-md text-slate-900 bg-white", "min": 1}),
        }
