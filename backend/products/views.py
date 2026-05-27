from django.db import transaction
from django.db.models import F
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import filters, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .filters import ProductFilter
from .models import CartItem, Category, Order, OrderItem, Product
from .permissions import IsOwnerOrReadOnly
from .serializers import (
    CartItemSerializer,
    CategorySerializer,
    CheckoutSerializer,
    OrderSerializer,
    OrderStatusSerializer,
    ProductSerializer,
)


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related("category", "owner").order_by("-created_at")
    serializer_class = ProductSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ["name", "description"]
    ordering_fields = ["created_at", "price", "name"]
    permission_classes = [IsOwnerOrReadOnly]

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [permissions.IsAuthenticated(), IsOwnerOrReadOnly()]
        return [permissions.AllowAny()]

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.order_by("name")
    serializer_class = CategorySerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]


class MyProductsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        queryset = Product.objects.select_related("category", "owner").filter(owner=request.user).order_by("-created_at")
        return Response(ProductSerializer(queryset, many=True).data)


class CartView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        items = CartItem.objects.select_related("product", "product__category", "product__owner").filter(user=request.user)
        data = CartItemSerializer(items, many=True).data
        total = sum(float(item.product.price) * item.quantity for item in items)
        return Response({"items": data, "total": total})

    def post(self, request):
        serializer = CartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = serializer.validated_data["product"]
        quantity = serializer.validated_data.get("quantity", 1)

        item, created = CartItem.objects.get_or_create(user=request.user, product=product, defaults={"quantity": quantity})
        if not created:
            item.quantity = F("quantity") + quantity
            item.save(update_fields=["quantity"])
            item.refresh_from_db()

        return Response(CartItemSerializer(item).data, status=status.HTTP_201_CREATED)


class CartItemDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, item_id):
        deleted, _ = CartItem.objects.filter(id=item_id, user=request.user).delete()
        if not deleted:
            return Response({"error": "Элемент корзины не найден"}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CheckoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        examples=[
            OpenApiExample(
                "Checkout payload",
                value={
                    "full_name": "Иван Иванов",
                    "phone": "+79990001122",
                    "city": "Екатеринбург",
                    "address": "ул. Ленина, 10, кв. 5",
                    "comment": "Позвонить за час",
                },
                request_only=True,
            )
        ]
    )
    def post(self, request):
        checkout_serializer = CheckoutSerializer(data=request.data)
        checkout_serializer.is_valid(raise_exception=True)
        items = list(CartItem.objects.select_related("product").filter(user=request.user))
        if not items:
            return Response({"error": "Корзина пуста"}, status=status.HTTP_400_BAD_REQUEST)

        total = sum(item.product.price * item.quantity for item in items)

        with transaction.atomic():
            order = Order.objects.create(
                user=request.user,
                full_name=checkout_serializer.validated_data["full_name"],
                phone=checkout_serializer.validated_data["phone"],
                city=checkout_serializer.validated_data["city"],
                address=checkout_serializer.validated_data["address"],
                comment=checkout_serializer.validated_data.get("comment", ""),
                total=total,
                status=Order.STATUS_NEW,
            )
            OrderItem.objects.bulk_create(
                [
                    OrderItem(order=order, product=item.product, quantity=item.quantity, price=item.product.price)
                    for item in items
                ]
            )
            CartItem.objects.filter(user=request.user).delete()

        return Response({"message": "Заказ оформлен", "order": OrderSerializer(order).data}, status=status.HTTP_201_CREATED)


class MyOrdersView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        orders = Order.objects.filter(user=request.user).prefetch_related("items", "items__product").order_by("-created_at")
        return Response(OrderSerializer(orders, many=True).data)


class OrderStatusUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, order_id):
        order = Order.objects.filter(id=order_id, items__product__owner=request.user).distinct().first()
        if not order:
            return Response({"error": "Заказ не найден или нет прав"}, status=status.HTTP_404_NOT_FOUND)

        serializer = OrderStatusSerializer(order, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(OrderSerializer(order).data)
