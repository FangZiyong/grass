from django.urls import path

from apps.accounts.api.views_auth import LoginView, LogoutView, RefreshView

urlpatterns = [
    path("auth/login", LoginView.as_view()),
    path("auth/logout", LogoutView.as_view()),
    path("auth/refresh", RefreshView.as_view()),
]
