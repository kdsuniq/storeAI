from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch

from products.models import Category, Product

from .models import AIInteraction
from .services import build_local_product_description, normalize_specs, parse_json_response


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

    def test_parse_json_response_ignores_empty_content(self):
        self.assertIsNone(parse_json_response(None))

    @patch("ai.services.ask_openrouter")
    def test_generate_description_falls_back_when_ai_content_is_empty(self, mocked_openrouter):
        async def fake_response(*args, **kwargs):
            return {"success": False, "fallback": "AI временно недоступен"}

        mocked_openrouter.side_effect = fake_response
        self._login()

        response = self.client.post(
            "/api/ai/generate-description/",
            {"name": "Тестовый товар", "category": "Outdoor", "specs": {}},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("description", response.data)
        self.assertIn("full_description", response.data["description"])

    @patch("ai.services.ask_openrouter")
    def test_generate_description_accepts_russian_payload_keys(self, mocked_openrouter):
        async def fake_response(*args, **kwargs):
            return {"success": False, "fallback": "AI временно недоступен"}

        mocked_openrouter.side_effect = fake_response
        self._login()

        response = self.client.post(
            "/api/ai/generate-description/",
            {"название": "сыворотка", "категория": "Корейская косметика", "характеристики": []},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        description = response.data["description"]
        self.assertIn("сыворотка", description["short_description"].lower())
        self.assertIn("Корейская косметика", description["full_description"])
        self.assertIn("Описание не выдумывает состав и свойства", description["advantages"])

    def test_normalize_specs_accepts_list_items(self):
        specs = normalize_specs([
            {"name": "Объём", "value": "30 мл"},
            "для вечернего ухода",
            {"title": "Тип кожи", "text": "сухая"},
        ])

        self.assertEqual(specs["Объём"], "30 мл")
        self.assertEqual(specs["Характеристика 2"], "для вечернего ухода")
        self.assertEqual(specs["Тип кожи"], "сухая")

    def test_local_product_description_uses_cosmetics_copy(self):
        description = build_local_product_description("сыворотка", "Корейская косметика", {})

        self.assertIn("ежедневного ухода", description["short_description"])
        self.assertIn("не содержит неподтверждённых обещаний", description["full_description"])
