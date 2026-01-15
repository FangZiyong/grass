from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

schema_urlpatterns = [
    path("schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="api-schema"), name="api-docs"),
]

urlpatterns = schema_urlpatterns
