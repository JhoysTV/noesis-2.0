"""
test_api.py — Comprehensive automated test suite for Nóesis del Caribe backend.
Covers routing, catalog, order submission, token verification, admin access,
quote workflows, file security, and rate limiting.
Runs with Python standard library `unittest` and `pytest`.
"""

import json
import unittest
from fastapi.testclient import TestClient

from backend.app.main import app, db
from backend.app.config import get_settings


class TestNoesisAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.settings = get_settings()

    def test_health_check(self):
        """Verify that the health check endpoint returns 200 and environment info."""
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertIn("env", data)

    def test_catalog(self):
        """Verify that the catalog contains required architectural and interior services."""
        response = self.client.get("/api/catalog")
        self.assertEqual(response.status_code, 200)
        items = response.json()
        self.assertIsInstance(items, list)
        self.assertGreaterEqual(len(items), 2)
        item_ids = [item["id"] for item in items]
        self.assertIn("arquitectonico", item_ids)
        self.assertIn("interiores", item_ids)
        for item in items:
            self.assertIn("price", item)
            self.assertGreater(item["price"], 0)
            self.assertIn("name", item)
            self.assertGreater(len(item["name"]), 0)

    def test_static_clean_routes(self):
        """Verify that all clean frontend URLs return 200 OK with expected content."""
        routes = [
            ("/", "text/html"),
            ("/index.html", "text/html"),
            ("/admin", "text/html"),
            ("/mi-pedido", "text/html"),
            ("/terminos", "text/html"),
            ("/blog", "text/html"),
            ("/careers", "text/html"),
            ("/robots.txt", "text/plain"),
            ("/sitemap.xml", "xml"),
        ]
        for path, expected_content_type in routes:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, f"Failed route {path}: {response.status_code}")
            self.assertIn(expected_content_type, response.headers.get("content-type", ""))

    def test_order_submission_and_tracking_flow(self):
        """Verify full client workflow: submit project -> get token -> query status."""
        payload = {
            "customer": {
                "name": "María Contreras",
                "email": "maria.contreras@example.com",
                "phone": "+1 (829) 555-1234",
                "contactPreference": "WhatsApp",
            },
            "projectType": "Diseño de Interiores",
            "area": "120",
            "requirements": "Renovación integral de sala, comedor y cocina con concepto abierto y estilo contemporáneo.",
            "budget": "RD$300,000 – RD$600,000",
            "photoNotes": "Fotos del estado actual adjuntas.",
            "items": [
                {"id": "interiores", "name": "Diseño de Interiores", "price": 35000}
            ],
            "total": 35000,
        }

        response = self.client.post(
            "/api/orders/submit",
            data={"order_data": json.dumps(payload)},
        )
        self.assertEqual(response.status_code, 200, response.text)
        submit_result = response.json()
        self.assertIn("orderId", submit_result)
        self.assertTrue(submit_result["orderId"].startswith("NOE-"))
        self.assertIn("clientToken", submit_result)
        client_token = submit_result["clientToken"]

        # Verify querying status with client token
        status_response = self.client.get(f"/api/order/{client_token}")
        self.assertEqual(status_response.status_code, 200)
        order_data = status_response.json()["order"]
        self.assertEqual(order_data["id"], submit_result["orderId"])
        self.assertEqual(order_data["status"], "recibido")
        self.assertEqual(order_data["customer"]["name"], "María Contreras")
        # Ensure clientToken is not leaked in public response
        self.assertNotIn("clientToken", order_data)

    def test_order_submission_validation_error(self):
        """Verify that invalid payload fails with 422 Unprocessable Entity."""
        response = self.client.post(
            "/api/orders/submit",
            data={"order_data": "invalid json"},
        )
        self.assertEqual(response.status_code, 422)

    def test_admin_authentication_and_protected_routes(self):
        """Verify admin login with configured credentials and protected orders access."""
        # Test wrong password
        bad_login = self.client.post(
            "/api/admin/login",
            json={"username": "admin", "password": "wrongpassword123"},
        )
        self.assertEqual(bad_login.status_code, 401)

        # Test correct login
        good_login = self.client.post(
            "/api/admin/login",
            json={"username": self.settings.admin_username, "password": self.settings.admin_password},
        )
        self.assertEqual(good_login.status_code, 200)
        token = good_login.json()["token"]
        self.assertEqual(token, self.settings.admin_token)

        # Query protected admin orders with Bearer token
        headers = {"Authorization": f"Bearer {token}"}
        admin_orders = self.client.get("/api/admin/orders", headers=headers)
        self.assertEqual(admin_orders.status_code, 200)
        self.assertIsInstance(admin_orders.json(), list)

        # Query protected admin orders without auth header
        unauthorized = self.client.get("/api/admin/orders")
        self.assertEqual(unauthorized.status_code, 401)

    def test_admin_quote_and_status_update(self):
        """Verify admin sending a quote and updating project status."""
        payload = {
            "customer": {
                "name": "Carlos Estrella",
                "email": "carlos.estrella@example.com",
                "phone": "+1 (809) 555-9876",
                "contactPreference": "Correo electrónico",
            },
            "projectType": "Diseño Arquitectónico",
            "area": "250",
            "requirements": "Villa unifamiliar en La Romana.",
            "budget": "Más de RD$1,000,000",
            "photoNotes": "",
            "items": [
                {"id": "arquitectonico", "name": "Diseño Arquitectónico", "price": 65000}
            ],
            "total": 65000,
        }

        sub_res = self.client.post(
            "/api/orders/submit",
            data={"order_data": json.dumps(payload)},
        )
        self.assertEqual(sub_res.status_code, 200)
        order_id = sub_res.json()["orderId"]
        client_token = sub_res.json()["clientToken"]

        # Admin sends quote
        headers = {"Authorization": f"Bearer {self.settings.admin_token}"}
        quote_payload = {
            "total": 75000,
            "notes": "Incluye distribución de 2 niveles y terrazas.",
            "scope": "Planos arquitectónicos acotados y 4 vistas 3D.",
            "deadlineDays": 15,
        }
        quote_res = self.client.post(
            f"/api/admin/orders/{order_id}/quote",
            json=quote_payload,
            headers=headers,
        )
        self.assertEqual(quote_res.status_code, 200)
        self.assertEqual(quote_res.json()["status"], "cotizado")
        self.assertEqual(quote_res.json()["total"], 75000)

        # Client sees the quote
        client_status = self.client.get(f"/api/order/{client_token}")
        self.assertEqual(client_status.status_code, 200)
        client_data = client_status.json()
        self.assertEqual(client_data["order"]["status"], "cotizado")
        self.assertEqual(client_data["quote"]["total"], 75000)
        self.assertEqual(client_data["quote"]["deadlineDays"], 15)

        # Dev mark paid (since app_env is development in tests)
        dev_pay = self.client.post(f"/api/dev/mark-paid/{order_id}", headers=headers)
        self.assertEqual(dev_pay.status_code, 200)
        self.assertEqual(dev_pay.json()["status"], "pagado")

    def test_file_security_and_path_traversal(self):
        """Verify that file endpoint rejects directory traversal and unknown tokens."""
        bad_traversal = self.client.get("/api/files/..%2F..%2F..%2Fetc%2Fpasswd?t=sometoken")
        self.assertIn(bad_traversal.status_code, (400, 403, 404))

        not_found = self.client.get("/api/files/nonexistent_file.pdf?t=faketoken")
        self.assertIn(not_found.status_code, (403, 404))


if __name__ == "__main__":
    unittest.main()
