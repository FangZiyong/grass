from django.urls import include, path

from . import schema

urlpatterns = [
    path("", include(schema.urlpatterns)),
]
