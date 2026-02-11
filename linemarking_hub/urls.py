from django.contrib import admin
from django.urls import include, path
from rest_framework import routers

from accounts.views import (
    AccountViewSet,
    account_connect_gmail,
    account_connect_microsoft,
    account_disconnect,
    account_gmail_oauth_callback,
    account_microsoft_oauth_callback,
    account_sync,
)
from automation.views import ActionViewSet, EmailLabelViewSet, LabelViewSet
from jobs.views import JobViewSet, TaskViewSet
from linemarking_hub.auth_views import (
    google_oauth_callback,
    google_oauth_login,
    login_view,
    logout_view,
    microsoft_oauth_callback,
    microsoft_oauth_login,
)
from linemarking_hub.views import (
    labels_add_recommended,
    account_clear_signature,
    account_clear_writing_style,
    account_create,
    account_delete,
    account_detail,
    account_update,
    action_create,
    action_delete,
    action_update,
    actions_list,
    draft_create,
    draft_delete,
    draft_detail,
    draft_rewrite,
    draft_update,
    drafts_list,
    email_detail,
    email_delete,
    draft_send,
    email_archive,
    email_forward,
    email_label_add,
    email_label_remove,
    email_reply,
    emails_list,
    job_create,
    job_delete,
    job_detail,
    job_update,
    jobs_calendar,
    jobs_list,
    label_create,
    label_delete,
    label_update,
    settings_view,
    task_create,
    task_delete,
    task_detail,
    task_email_data,
    task_update,
    tasks_list,
)
from mail.views import DraftViewSet, EmailMessageViewSet, EmailThreadViewSet

router = routers.DefaultRouter()
router.register("accounts", AccountViewSet, basename="account")
router.register("jobs", JobViewSet, basename="job")
router.register("tasks", TaskViewSet, basename="task")
router.register("email-threads", EmailThreadViewSet, basename="emailthread")
router.register("emails", EmailMessageViewSet, basename="emailmessage")
router.register("drafts", DraftViewSet, basename="draft")
router.register("labels", LabelViewSet, basename="label")
router.register("actions", ActionViewSet, basename="action")
router.register("email-labels", EmailLabelViewSet, basename="emaillabel")

urlpatterns = [
    # Home
    path("", tasks_list, name="home"),
    # Jobs
    path("jobs/", jobs_list, name="jobs_list"),
    path("jobs/calendar/", jobs_calendar, name="jobs_calendar"),
    path("jobs/create/", job_create, name="job_create"),
    path("jobs/<int:pk>/", job_detail, name="job_detail"),
    path("jobs/<int:pk>/edit/", job_update, name="job_update"),
    path("jobs/<int:pk>/delete/", job_delete, name="job_delete"),
    # Tasks
    path("tasks/", tasks_list, name="tasks_list"),
    path("tasks/create/", task_create, name="task_create"),
    path("tasks/<int:pk>/", task_detail, name="task_detail"),
    path("tasks/<int:pk>/edit/", task_update, name="task_update"),
    path("tasks/<int:pk>/delete/", task_delete, name="task_delete"),
    path("tasks/<int:pk>/email-data/", task_email_data, name="task_email_data"),
    # Emails
    path("emails/", emails_list, name="emails_list"),
    path("emails/<int:pk>/", email_detail, name="email_detail"),  # Redirects to emails_list with modal
    path("emails/<int:pk>/delete/", email_delete, name="email_delete"),
    path("emails/<int:pk>/archive/", email_archive, name="email_archive"),
    path("emails/<int:pk>/reply/", email_reply, name="email_reply"),
    path("emails/<int:pk>/forward/", email_forward, name="email_forward"),
    path("emails/<int:pk>/forward/form/", email_forward, name="email_forward_form"),
    path("emails/<int:email_id>/labels/add/", email_label_add, name="email_label_add"),
    path("emails/<int:email_id>/labels/<int:label_id>/remove/", email_label_remove, name="email_label_remove"),
    # Labels
    path("labels/create/", label_create, name="label_create"),
    path("labels/add-recommended/", labels_add_recommended, name="labels_add_recommended"),
    path("labels/<int:pk>/edit/", label_update, name="label_update"),
    path("labels/<int:pk>/delete/", label_delete, name="label_delete"),
    # Accounts
    path("accounts/create/", account_create, name="account_create"),
    path("accounts/<int:pk>/", account_detail, name="account_detail"),
    path("accounts/<int:pk>/edit/", account_update, name="account_update"),
    path("accounts/<int:pk>/delete/", account_delete, name="account_delete"),
    path("accounts/<int:pk>/clear-signature/", account_clear_signature, name="account_clear_signature"),
    path("accounts/<int:pk>/clear-writing-style/", account_clear_writing_style, name="account_clear_writing_style"),
    path("accounts/connect/gmail/", account_connect_gmail, name="connect_gmail"),
    path("accounts/gmail/callback/", account_gmail_oauth_callback, name="gmail_oauth_callback"),
    path("accounts/connect/microsoft/", account_connect_microsoft, name="connect_microsoft"),
    path("accounts/microsoft/callback/", account_microsoft_oauth_callback, name="microsoft_email_oauth_callback"),
    path("accounts/<int:pk>/disconnect/", account_disconnect, name="disconnect_account"),
    path("accounts/<int:pk>/sync/", account_sync, name="sync_account"),
    # Drafts
    path("drafts/", drafts_list, name="drafts_list"),
    path("drafts/create/", draft_create, name="draft_create"),
    path("drafts/<int:pk>/", draft_detail, name="draft_detail"),
    path("drafts/<int:pk>/edit/", draft_update, name="draft_update"),
    path("drafts/<int:pk>/rewrite/", draft_rewrite, name="draft_rewrite"),
    path("drafts/<int:pk>/delete/", draft_delete, name="draft_delete"),
    path("drafts/<int:pk>/send/", draft_send, name="draft_send"),
    # Actions
    path("actions/", actions_list, name="actions_list"),
    path("actions/create/", action_create, name="action_create"),
    path("actions/<int:pk>/edit/", action_update, name="action_update"),
    path("actions/<int:pk>/delete/", action_delete, name="action_delete"),
    # Authentication
    path("auth/login/", login_view, name="login"),
    path("auth/logout/", logout_view, name="logout"),
    path("auth/google/login/", google_oauth_login, name="google_oauth_login"),
    path("auth/google/callback/", google_oauth_callback, name="google_oauth_callback"),
    path("auth/microsoft/login/", microsoft_oauth_login, name="microsoft_oauth_login"),
    path("auth/microsoft/callback/", microsoft_oauth_callback, name="microsoft_oauth_callback"),
    # Settings
    path("settings/", settings_view, name="settings"),
    # Admin & API
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),
    path("api-auth/", include("rest_framework.urls")),
]
