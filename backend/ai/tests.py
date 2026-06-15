from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from products.models import Category, Product

from .models import AIInteraction


class AIAssistantTests(APITestCase):
    def setUp(self):
        from . import services

        services.OPENROUTER_API_KEY = ""
        self.user = User.objects.create_user(username="buyer", password="password123")
        self.category = Category.objects.create(name="Outdoor", description="Товары для активного отдыха")
        self.product = Product.objects.create(
            owner=self.user,
            name="Легкий рюкзак для треккинга",
            description="Удобный рюкзак с мягкими лямками для походов и путешествий",
            price="3500.00",
            category=self.category,
            specs={"Вес": "800 г", "Объем": "30 л"},
            stock=5,
        )

    def _login(self):
        response = self.client.post("/api/auth/login/", {"username": "buyer", "password": "password123"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['tokens']['access']}")

    def test_semantic_search_returns_recommendations_and_logs_interaction(self):
        response = self.client.post("/api/ai/semantic-search/", {"query": "легкий рюкзак для треккинга"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("recommendations", response.data)
        self.assertIn("interaction_id", response.data)
        self.assertEqual(AIInteraction.objects.filter(kind=AIInteraction.KIND_SEARCH).count(), 1)

    def test_feedback_marks_interaction_for_prompt_review_when_not_helpful(self):
        interaction = AIInteraction.objects.create(kind=AIInteraction.KIND_SEARCH, query="test", response={})

        response = self.client.post(
            "/api/ai/feedback/",
            {"interaction_id": interaction.id, "helpful": False, "feedback_text": "Не нашёл товар"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        interaction.refresh_from_db()
        self.assertFalse(interaction.helpful)
        self.assertTrue(interaction.needs_prompt_review)

    def test_bundle_endpoint_returns_items(self):
        response = self.client.post("/api/ai/bundle/", {"query": "собрать комплект для похода"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("items", response.data)
        self.assertIn("interaction_id", response.data)
