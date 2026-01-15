from django.test import SimpleTestCase
from django.urls import reverse


class HealthzTests(SimpleTestCase):
    def test_healthz_returns_ok_shell(self):
        response = self.client.get(reverse("healthz"))

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["code"], "OK")
        self.assertEqual(body["message"], "OK")
        self.assertEqual(body["data"]["status"], "ok")
        self.assertIn("ts", body["data"])
        self.assertTrue(body["request_id"])
        self.assertEqual(response["X-Request-Id"], body["request_id"])

    def test_healthz_echoes_request_id_header(self):
        custom_request_id = "req_custom_123"

        response = self.client.get(reverse("healthz"), HTTP_X_REQUEST_ID=custom_request_id)
        body = response.json()

        self.assertEqual(body["request_id"], custom_request_id)
        self.assertEqual(response["X-Request-Id"], custom_request_id)
        self.assertEqual(body["code"], "OK")
        self.assertEqual(body["data"]["status"], "ok")
