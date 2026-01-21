from django import forms
from django.contrib import admin
from django.contrib.auth.hashers import make_password

from apps.accounts.models.sessions import AuthSession
from apps.accounts.models.users import GlobalUser


class GlobalUserAdminForm(forms.ModelForm):
    password = forms.CharField(
        label="Password",
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text="输入新密码将自动生成 hash；留空则不修改。",
    )

    class Meta:
        model = GlobalUser
        fields = (
            "login_name",
            "display_name",
            "email",
            "status",
            "is_platform_admin",
            "last_login_at",
            "last_tenant_id",
        )


@admin.register(GlobalUser)
class GlobalUserAdmin(admin.ModelAdmin):
    form = GlobalUserAdminForm
    list_display = (
        "user_id",
        "login_name",
        "email",
        "status",
        "is_platform_admin",
        "last_login_at",
    )
    search_fields = ("login_name", "email", "display_name")
    list_filter = ("status", "is_platform_admin")
    ordering = ("-user_id",)
    readonly_fields = ("last_login_at", "last_tenant_id", "created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        password = form.cleaned_data.get("password")
        if password:
            obj.password_hash = make_password(password)
        super().save_model(request, obj, form, change)


@admin.register(AuthSession)
class AuthSessionAdmin(admin.ModelAdmin):
    list_display = (
        "auth_session_id",
        "user_id",
        "status",
        "issued_at",
        "expires_at",
        "revoked_at",
    )
    search_fields = ("refresh_token_hash", "user__login_name", "user__email")
    list_filter = ("status",)
    ordering = ("-auth_session_id",)
    readonly_fields = ("created_at", "updated_at")
