from django.contrib import admin

from .models import Account


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("provider", "email")
    search_fields = ("email",)
    ordering = ("provider", "email")
