from django.db import IntegrityError
from django.http import Http404
from django.test import override_settings
from django.urls import path
from rest_framework.exceptions import NotAuthenticated, PermissionDenied, ValidationError
from rest_framework.test import APIClient, APISimpleTestCase
from rest_framework.views import APIView


class ValidationErrorView(APIView):
    def get(self, request):
        raise ValidationError({"field": ["invalid"]})


class UnauthenticatedView(APIView):
    def get(self, request):
        raise NotAuthenticated("Auth required")


class ForbiddenView(APIView):
    def get(self, request):
        raise PermissionDenied("Forbidden")


class NotFoundView(APIView):
    def get(self, request):
        raise Http404("Missing resource")


class ConflictView(APIView):
    def get(self, request):
        raise IntegrityError("duplicate key")


class ServerErrorView(APIView):
    def get(self, request):
        raise Exception("boom")


urlpatterns = [
    path("validation-error", ValidationErrorView.as_view()),
    path("unauthenticated", UnauthenticatedView.as_view()),
    path("forbidden", ForbiddenView.as_view()),
    path("not-found", NotFoundView.as_view()),
    path("conflict", ConflictView.as_view()),
    path("server-error", ServerErrorView.as_view()),
]


@override_settings(ROOT_URLCONF=__name__)
class ExceptionHandlerTests(APISimpleTestCase):
    client_class = APIClient

    def test_validation_error_returns_bad_request_shell(self):
        response = self.client.get("/validation-error")
        body = response.json()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(body["code"], "BAD_REQUEST")
        self.assertEqual(body["data"], {"field": ["invalid"]})
        self.assertTrue(body["message"])
        self.assertEqual(response["X-Request-Id"], body["request_id"])

    def test_not_authenticated_returns_401(self):
        response = self.client.get("/unauthenticated")
        body = response.json()

        self.assertEqual(response.status_code, 401)
        self.assertEqual(body["code"], "UNAUTHENTICATED")
        self.assertIn("Auth", body["message"])
        self.assertEqual(response["X-Request-Id"], body["request_id"])

    def test_permission_denied_respects_request_id(self):
        request_id = "req_test_permission"
        response = self.client.get("/forbidden", HTTP_X_REQUEST_ID=request_id)
        body = response.json()

        self.assertEqual(response.status_code, 403)
        self.assertEqual(body["code"], "PERMISSION_DENIED")
        self.assertEqual(body["request_id"], request_id)
        self.assertEqual(response["X-Request-Id"], request_id)

    def test_http404_returns_not_found_shell(self):
        response = self.client.get("/not-found")
        body = response.json()

        self.assertEqual(response.status_code, 404)
        self.assertEqual(body["code"], "NOT_FOUND")
        self.assertEqual(body["data"], None)

    def test_integrity_error_returns_conflict(self):
        response = self.client.get("/conflict")
        body = response.json()

        self.assertEqual(response.status_code, 409)
        self.assertEqual(body["code"], "CONFLICT")
        self.assertEqual(body["data"], None)

    def test_unhandled_exception_returns_internal_error(self):
        response = self.client.get("/server-error")
        body = response.json()

        self.assertEqual(response.status_code, 500)
        self.assertEqual(body["code"], "INTERNAL_ERROR")
        self.assertEqual(body["data"], None)
        self.assertTrue(body["message"])
