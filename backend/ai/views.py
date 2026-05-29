import json
import logging
from django.db.models import Sum, F
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from products.models import CartItem, Product

from .services import (
    ask_ai_sync,
    build_market_insights_prompt,
    build_product_prompt,
    build_chat_prompt,
    parse_json_response
)

logger = logging.getLogger(__name__)


class AIChatView(APIView):
    """Общий чат с AI помощником - структурированный вывод"""
    
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
        response_format = request.data.get("format", "structured")  # structured или json
        
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
        
        prompt = build_chat_prompt(message, response_format)
        answer = ask_ai_sync(prompt, response_format=response_format)
        
        # Если запрошен JSON формат, пробуем распарсить
        if response_format == "json":
            parsed = parse_json_response(answer)
            if parsed:
                return Response({"answer": parsed, "format": "json"})
        
        return Response({
            "answer": answer,
            "format": response_format,
            "model": "openrouter/free"
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
        name = request.data.get("name", "")
        category = request.data.get("category", "")
        specs = request.data.get("specs", {})

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
        
        if specs and not isinstance(specs, dict):
            return Response(
                {"error": "specs must be JSON object"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        prompt = build_product_prompt(
            name=name.strip(), 
            category=category, 
            specs=specs
        )
        answer = ask_ai_sync(prompt, response_format="json")
        
        # Парсим JSON ответ
        parsed = parse_json_response(answer)
        if parsed:
            return Response({"description": parsed})
        
        # Fallback если не JSON
        return Response({
            "description": {
                "short_description": answer[:200],
                "full_description": answer,
                "advantages": ["Качественный товар", "Отличная цена", "Быстрая доставка"],
                "call_to_action": "Добавьте товар в корзину!"
            }
        })


class MarketInsightsView(APIView):
    """Аналитика рынка и рекомендации от AI - JSON формат"""
    
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        seller_products = Product.objects.filter(owner=request.user)
        seller_product_ids = list(seller_products.values_list("id", flat=True))
        
        # Статистика по добавлениям в корзину
        cart_stats = (
            CartItem.objects.filter(product_id__in=seller_product_ids)
            .values("product__name", "product__id")
            .annotate(total_qty=Sum("quantity"))
            .order_by("-total_qty")[:10]
        )
        
        # Общая статистика
        cart_items = CartItem.objects.filter(product_id__in=seller_product_ids)
        total_cart_additions = cart_items.aggregate(total=Sum("quantity"))["total"] or 0
        
        # Статистика по остаткам
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
        
        # Генерируем AI инсайты
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


class AIProductRecommendationView(APIView):
    """Рекомендация товаров на основе корзины пользователя"""
    
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Получаем товары из корзины пользователя
        cart_items = CartItem.objects.filter(user=request.user).select_related('product')
        
        if not cart_items.exists():
            return Response({
                "recommendations": [],
                "message": "Добавьте товары в корзину для получения рекомендаций"
            })
        
        # Формируем список товаров в корзине
        cart_products = [
            {
                "name": item.product.name,
                "category": item.product.category.name if item.product.category else "Unknown",
                "price": float(item.product.price)
            }
            for item in cart_items
        ]
        
        prompt = (
            f"Пользователь добавил в корзину: {json.dumps(cart_products, ensure_ascii=False)}\n\n"
            "Рекомендуй 3-5 похожих товаров, которые могут его заинтересовать.\n"
            "Верни JSON формата:\n"
            "{\n"
            '  "recommendations": [\n'
            '    {"name": "название", "reason": "почему рекомендуем"}\n'
            "  ],\n"
            '  "cross_sell": ["товар для дополнительной продажи"]\n'
            "}"
        )
        
        answer = ask_ai_sync(prompt, response_format="json")
        parsed = parse_json_response(answer)
        
        return Response(parsed or {
            "recommendations": [],
            "cross_sell": [],
            "message": "Рекомендации временно недоступны"
        })
    

# ai/views.py - добавить в конец файла

class AIRecommendationsView(APIView):
    """
    AI рекомендации товаров на основе запроса пользователя
    """
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
        
        # Простая заглушка для теста, пока не настроили полноценные рекомендации
        return Response({
            "recommendations": [],
            "summary": "Функция рекомендаций настраивается. Попробуйте позже.",
            "follow_up_question": "Что именно вы ищете?"
        })