"""
Tests for automation services (ensure_task_for_email, get_emails_to_process).
These are unit-testable without Celery, AI, or Gmail.
"""
from django.test import TestCase

from accounts.models import Account, Provider
from automation.task_from_email import ensure_task_for_email, get_emails_to_process
from jobs.models import Task
from mail.models import EmailMessage, EmailThread


class EnsureTaskForEmailTests(TestCase):
    """Test ensure_task_for_email without Celery or AI."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.account = Account.objects.create(
            email="test@example.com",
            provider=Provider.GMAIL,
            is_connected=True,
        )
        self.account.users.add(self.user)
        self.thread = EmailThread.objects.create(
            account=self.account,
            external_thread_id="thread-1",
        )
        self.email = EmailMessage.objects.create(
            account=self.account,
            thread=self.thread,
            external_message_id="msg-1",
            subject="Test",
            from_address="other@example.com",
            to_addresses=["test@example.com"],
            body_html="<p>Body</p>",
        )

    def test_creates_task_for_email(self):
        classification = {
            "task_title": "Test task",
            "task_description": "Description",
            "priority": 3,
            "due_at": None,
        }
        task = ensure_task_for_email(self.email, classification)
        self.assertIsNotNone(task.pk)
        self.assertEqual(task.account, self.account)
        self.assertEqual(task.email_message, self.email)
        self.assertEqual(task.thread, self.thread)
        self.assertEqual(task.title, "Test task")
        self.assertEqual(task.priority, 3)
        self.assertEqual(self.email.tasks.count(), 1)

    def test_get_emails_to_process_returns_emails_without_tasks(self):
        qs = get_emails_to_process(self.account, exclude_threads_with_tasks=True)
        self.assertIn(self.email, list(qs))
        ensure_task_for_email(
            self.email,
            {"task_title": "Done", "task_description": "", "priority": 1, "due_at": None},
        )
        qs2 = get_emails_to_process(self.account, exclude_threads_with_tasks=True)
        self.assertNotIn(self.email, list(qs2))
