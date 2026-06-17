import json
import logging
from django.db.models import Sum, F
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from products.models import CartItem, Product
from .models import AIInteraction, ProductViewEvent
from .services import (
    ask_ai_sync,
    build_local_product_description,
    build_bundle,
    build_market_insights_prompt,
    build_product_prompt,
    build_chat_prompt,
    get_personal_recommendations,
    parse_json_response,
    normalize_specs,
    SYSTEM_PROMPT_PRODUCT,
    get_price_analysis,
    semantic_search_products,
)

logger = logging.getLogger(__name__)


class AIChatView(APIView):
    """Чат с AI помощником: вопросы, сужение выбора и рекомендации"""
    
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        examples=[
            OpenApiExample(
                "Chat example",
                value={"message": "Какие товары сейчас лучше добавить в магазин техники?"},
                request_only=True,
            ),
            OpenApiExample(
                "Chat with format",
                value={"message": "Помоги выбрать ноутбук", "format": "json"},
                request_only=True,
            ),
        ]
    )
    def post(self, request):
        message = request.data.get("message")
        response_format = request.data.get("format", "structured")
        
        if not message:
            return Response(
                {"error": "message is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(message) > 2000:
            return Response(
                {"error": "Message too long (max 2000 characters)"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = request.user if request.user.is_authenticated else None
        semantic_result = semantic_search_products(message, user=user, limit=4)

        prompt = build_chat_prompt(message, response_format)
        answer = ask_ai_sync(prompt, response_format=response_format)
        
        if response_format == "json":
            parsed = parse_json_response(answer)
            if parsed:
                interaction = AIInteraction.objects.create(
                    user=user,
                    kind=AIInteraction.KIND_CHAT,
                    query=message,
                    response={**parsed, "semantic": semantic_result},
                    context=semantic_result.get("context", {}),
                )
                return Response(
                    {
                        "answer": parsed,
                        "format": "json",
                        "clarifying_questions": semantic_result.get("clarifying_questions", []),
                        "recommendations": semantic_result.get("recommendations", []),
                        "interaction_id": interaction.id,
                    }
                )

        recommendations = semantic_result.get("recommendations", [])
        questions = semantic_result.get("clarifying_questions", [])
        if questions:
            answer = f"{answer}\n\nУТОЧНЮ, ЧТОБЫ СУЗИТЬ ВЫБОР:\n" + "\n".join([f"- {question}" for question in questions[:3]])
        if recommendations:
            answer = f"{answer}\n\nПОДХОДЯЩИЕ ТОВАРЫ:\n" + "\n".join(
                [f"- {rec['name']} — {rec['price']} ₽. {rec.get('why_fits', '')}" for rec in recommendations[:4]]
            )

        interaction = AIInteraction.objects.create(
            user=user,
            kind=AIInteraction.KIND_CHAT,
            query=message,
            response={"answer": answer, "semantic": semantic_result},
            context=semantic_result.get("context", {}),
        )
        
        return Response({
            "answer": answer,
            "format": response_format,
            "model": "openrouter/free",
            "clarifying_questions": questions,
            "recommendations": recommendations,
            "interaction_id": interaction.id,
        })


class AIDescriptionView(APIView):
    """Генерация описания товара с помощью AI - JSON формат"""
    
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        examples=[
            OpenApiExample(
                "Generate description",
                value={
                    "name": "iPhone 15",
                    "category": "Смартфоны",
                    "specs": {"Память": "256 ГБ", "Цвет": "Черный"},
                },
                request_only=True,
            )
        ]
    )
    def post(self, request):
        name = request.data.get("name") or request.data.get("название") or ""
        category = request.data.get("category") or request.data.get("категория") or ""
        specs = request.data.get("specs", request.data.get("характеристики", {}))
        specs = normalize_specs(specs)

        if not name or not str(name).strip():
            return Response(
                {"error": "name is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(name) > 200:
            return Response(
                {"error": "name too long (max 200 characters)"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        prompt = build_product_prompt(
            name=name.strip(), 
            category=category, 
            specs=specs
        )
        answer = ask_ai_sync(
            prompt,
            response_format="json",
            temperature=0.45,
            system_prompt_override=SYSTEM_PROMPT_PRODUCT,
        )
        
        parsed = parse_json_response(answer)
        if parsed and isinstance(parsed, dict) and parsed.get("full_description"):
            return Response({"description": parsed})
        
        return Response({"description": build_local_product_description(name, category, specs)})


class MarketInsightsView(APIView):
    """Аналитика рынка и рекомендации от AI - JSON формат"""
    
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        seller_products = Product.objects.filter(owner=request.user)
        seller_product_ids = list(seller_products.values_list("id", flat=True))
        
        cart_stats = (
            CartItem.objects.filter(product_id__in=seller_product_ids)
            .values("product__name", "product__id")
            .annotate(total_qty=Sum("quantity"))
            .order_by("-total_qty")[:10]
        )
        
        cart_items = CartItem.objects.filter(product_id__in=seller_product_ids)
        total_cart_additions = cart_items.aggregate(total=Sum("quantity"))["total"] or 0
        
        products_low_stock = seller_products.filter(stock__gt=0, stock__lte=F('low_stock_threshold')).count()
        products_out_of_stock = seller_products.filter(stock=0).count()
        products_in_stock = seller_products.filter(stock__gt=0).count()
        
        raw_stats = {
            "seller_products_count": seller_products.count(),
            "products_in_stock": products_in_stock,
            "products_low_stock": products_low_stock,
            "products_out_of_stock": products_out_of_stock,
            "total_cart_additions": total_cart_additions,
            "top_products_by_cart": [
                {"product": row["product__name"], "qty": row["total_qty"] or 0} 
                for row in cart_stats
            ],
        }
        
        if seller_products.count() > 0:
            prompt = build_market_insights_prompt(raw_stats)
            ai_response = ask_ai_sync(prompt, response_format="json")
            parsed = parse_json_response(ai_response)
            
            insights = parsed if parsed else {
                "summary": "Аналитика временно недоступна",
                "recommendations": [
                    "Добавьте больше товаров в категории с высоким спросом",
                    "Обновите цены на популярные позиции",
                    "Увеличьте остатки востребованных товаров"
                ],
                "forecast": "Спрос стабильный, рекомендуется активное пополнение склада",
                "action_items": ["Проверить остатки", "Обновить цены"]
            }
        else:
            insights = {
                "summary": "У вас пока нет товаров",
                "recommendations": ["Добавьте первый товар, чтобы получить аналитику"],
                "forecast": "Нет данных для прогноза",
                "action_items": ["Создать категорию", "Добавить товар"]
            }
        
        return Response({
            "stats": raw_stats,
            "insights": insights
        })


class AIRecommendationsView(APIView):
    """AI рекомендации товаров на основе семантического запроса пользователя"""
    
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        user_query = request.data.get("query", "").strip()
        
        if not user_query:
            return Response(
                {"error": "query is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(user_query) > 500:
            return Response(
                {"error": "query too long (max 500 characters)"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = request.user if request.user.is_authenticated else None
        recommendations = semantic_search_products(user_query, user=user)
        interaction = AIInteraction.objects.create(
            user=user,
            kind=AIInteraction.KIND_SEARCH,
            query=user_query,
            response=recommendations,
            context=recommendations.get("context", {}),
        )
        recommendations["interaction_id"] = interaction.id
        return Response(recommendations, status=status.HTTP_200_OK)


class AISemanticSearchView(AIRecommendationsView):
    """Явный alias для семантического поиска"""


class AIPersonalRecommendationsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        recommendations = get_personal_recommendations(request.user)
        interaction = AIInteraction.objects.create(
            user=request.user,
            kind=AIInteraction.KIND_PERSONAL,
            query="personal_recommendations",
            response=recommendations,
            context=recommendations.get("context", {}),
        )
        recommendations["interaction_id"] = interaction.id
        return Response(recommendations)


class AIBundleView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        query = request.data.get("query", "").strip()
        if not query:
            return Response({"error": "query is required"}, status=status.HTTP_400_BAD_REQUEST)
        if len(query) > 500:
            return Response({"error": "query too long (max 500 characters)"}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user if request.user.is_authenticated else None
        bundle = build_bundle(query, user=user)
        interaction = AIInteraction.objects.create(
            user=user,
            kind=AIInteraction.KIND_BUNDLE,
            query=query,
            response=bundle,
            context=bundle.get("context", {}),
        )
        bundle["interaction_id"] = interaction.id
        return Response(bundle)


class AIInteractionFeedbackView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        interaction_id = request.data.get("interaction_id")
        helpful = request.data.get("helpful")
        feedback_text = request.data.get("feedback_text", "")
        if interaction_id is None or helpful is None:
            return Response({"error": "interaction_id and helpful are required"}, status=status.HTTP_400_BAD_REQUEST)

        interaction = AIInteraction.objects.filter(id=interaction_id).first()
        if not interaction:
            return Response({"error": "AI interaction not found"}, status=status.HTTP_404_NOT_FOUND)
        if interaction.user_id and interaction.user_id != getattr(request.user, "id", None):
            return Response({"error": "Нет прав оценивать этот ответ"}, status=status.HTTP_403_FORBIDDEN)

        if isinstance(helpful, str):
            helpful = helpful.lower() in ["1", "true", "yes", "да"]
        interaction.helpful = bool(helpful)
        interaction.feedback_text = feedback_text[:2000]
        interaction.needs_prompt_review = not interaction.helpful
        interaction.save(update_fields=["helpful", "feedback_text", "needs_prompt_review", "updated_at"])
        return Response({"message": "Спасибо, оценка сохранена"})


class ProductViewTrackView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        product_id = request.data.get("product_id")
        product = Product.objects.filter(id=product_id).first()
        if not product:
            return Response({"error": "Товар не найден"}, status=status.HTTP_404_NOT_FOUND)

        user = request.user if request.user.is_authenticated else None
        ProductViewEvent.objects.create(
            user=user,
            product=product,
            source=request.data.get("source") or ProductViewEvent.SOURCE_CATALOG,
            query=request.data.get("query", "")[:500],
        )
        return Response({"message": "Просмотр сохранен"})


class AIPriceAnalysisView(APIView):
    """Анализ ценового диапазона магазина"""
    
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        analysis = get_price_analysis()
        return Response(analysis, status=status.HTTP_200_OK)
