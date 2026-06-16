from django.contrib import admin

from .models import EmailVerificationToken, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "store_name", "email_verified", "created_at")
    list_filter = ("role", "email_verified")
    search_fields = ("user__username", "user__email", "store_name")


@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "token", "used", "created_at")
    list_filter = ("used",)
    search_fields = ("user__username", "user__email")
