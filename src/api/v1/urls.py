from django.urls import include, path

from . import schema

urlpatterns = [
    path("", include(schema.urlpatterns)),
    path("", include("apps.accounts.api.urls")),
    path("", include("apps.tenants.api.urls")),
]
