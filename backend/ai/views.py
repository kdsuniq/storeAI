from django.db.models import Sum
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from products.models import CartItem, Product

from .services import ask_ai, build_market_insights_prompt, build_product_prompt


class AIChatView(APIView):
    @extend_schema(
        examples=[
            OpenApiExample(
                "Chat example",
                value={"message": "Какие товары сейчас лучше добавить в магазин техники?"},
                request_only=True,
            )
        ]
    )
    def post(self, request):
        message = request.data.get("message")
        if not message:
            return Response({"error": "message is required"}, status=status.HTTP_400_BAD_REQUEST)

        answer = ask_ai(message)
        return Response({"answer": answer})


class AIDescriptionView(APIView):
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
            return Response({"error": "name is required"}, status=status.HTTP_400_BAD_REQUEST)
        if specs and not isinstance(specs, dict):
            return Response({"error": "specs must be JSON object"}, status=status.HTTP_400_BAD_REQUEST)

        prompt = build_product_prompt(name=name.strip(), category=category, specs=specs)
        answer = ask_ai(prompt)
        return Response({"description": answer})


class MarketInsightsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        seller_products = Product.objects.filter(owner=request.user)
        seller_product_ids = list(seller_products.values_list("id", flat=True))
        sales_rows = (
            CartItem.objects.filter(product_id__in=seller_product_ids)
            .values("product__name")
            .annotate(total_qty=Sum("quantity"))
            .order_by("-total_qty")[:10]
        )
        sales_stats = [{"product": row["product__name"], "qty": row["total_qty"] or 0} for row in sales_rows]

        raw_stats = {
            "seller_products_count": seller_products.count(),
            "total_cart_additions": sum(item["qty"] for item in sales_stats),
            "top_products": sales_stats[:3],
            "all_products_stats": sales_stats,
        }

        ai_text = ask_ai(build_market_insights_prompt(raw_stats))
        return Response({"stats": raw_stats, "insights": ai_text})
