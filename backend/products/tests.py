from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Category, Order, Product


class StoreApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="seller", password="password123")
        self.other = User.objects.create_user(username="other", password="password123")
        self.category = Category.objects.create(name="Phones", description="Smartphones")
        self.product = Product.objects.create(
            owner=self.user,
            name="Phone",
            description="Good phone",
            price="1000.00",
            category=self.category,
            specs={"memory": "128gb"},
        )

    def _login(self, username="seller", password="password123"):
        response = self.client.post("/api/auth/login/", {"username": username, "password": password}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token = response.data["tokens"]["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_register_and_login_jwt(self):
        response = self.client.post(
            "/api/auth/register/",
            {"username": "newuser", "email": "n@example.com", "password": "password123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("tokens", response.data)

    def test_only_owner_can_update_product(self):
        self._login(username="other")
        response = self.client.patch(f"/api/products/{self.product.id}/", {"name": "Hacked"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_update_product(self):
        self._login()
        response = self.client.patch(f"/api/products/{self.product.id}/", {"name": "Updated"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_checkout_creates_order(self):
        self._login()
        add_resp = self.client.post(
            "/api/products/cart/",
            {"product_id": str(self.product.id), "quantity": 2},
            format="json",
        )
        self.assertEqual(add_resp.status_code, status.HTTP_201_CREATED)

        checkout_resp = self.client.post(
            "/api/products/cart/checkout/",
            {
                "full_name": "Ivan Ivanov",
                "phone": "+79990001122",
                "city": "Moscow",
                "address": "Lenina 1, apt 10",
                "comment": "call me",
            },
            format="json",
        )
        self.assertEqual(checkout_resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(checkout_resp.data["order"]["status"], "new")

    def test_my_orders_available(self):
        self._login()
        Order.objects.create(
            user=self.user,
            full_name="Ivan Ivanov",
            phone="+79990001122",
            city="Moscow",
            address="Lenina 1",
            total="100.00",
        )
        response = self.client.get("/api/products/my-orders/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
