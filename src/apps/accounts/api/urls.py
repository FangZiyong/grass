from django.urls import path

from apps.accounts.api.views_auth import LoginView

urlpatterns = [
    path("auth/login", LoginView.as_view()),
]
