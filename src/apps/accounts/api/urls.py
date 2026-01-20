from django.urls import path

from apps.accounts.api.views_auth import LoginView

urlpatterns = [
    path("api/auth/login", LoginView.as_view()),
]
