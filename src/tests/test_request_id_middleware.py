from django.test import override_settings
from django.urls import path
from rest_framework.response import Response
from rest_framework.test import APIClient, APISimpleTestCase
from rest_framework.views import APIView


class RequestIdView(APIView):
    def get(self, request):
        return Response(
            {
                "request_id": request.request_id,
                "state_request_id": getattr(request.state, "request_id", None),
            }
        )


class ErrorView(APIView):
    def get(self, request):
        raise Exception("boom")


urlpatterns = [
    path("request-id", RequestIdView.as_view()),
    path("request-error", ErrorView.as_view()),
]


@override_settings(ROOT_URLCONF=__name__)
class RequestIdMiddlewareTests(APISimpleTestCase):
    client_class = APIClient

    def test_request_id_generated_and_set_on_request(self):
        response = self.client.get("/request-id")
        body = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(body["request_id"])
        self.assertEqual(body["request_id"], body["state_request_id"])
        self.assertEqual(response["X-Request-Id"], body["request_id"])

    def test_request_id_header_is_preserved(self):
        request_id = "req_test_middleware"

        response = self.client.get("/request-id", HTTP_X_REQUEST_ID=request_id)
        body = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["request_id"], request_id)
        self.assertEqual(body["state_request_id"], request_id)
        self.assertEqual(response["X-Request-Id"], request_id)

    def test_request_id_available_on_error_response(self):
        response = self.client.get("/request-error")
        body = response.json()

        self.assertEqual(response.status_code, 500)
        self.assertTrue(body["request_id"])
        self.assertEqual(response["X-Request-Id"], body["request_id"])
