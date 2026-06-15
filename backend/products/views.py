from django.db import transaction
from django.db.models import F
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import filters, permissions, status, viewsets
from rest_framework.pagination import PageNumberPagination
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
    ProductCreateSerializer,
)


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 8
    page_size_query_param = "page_size"
    max_page_size = 48


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related("category", "owner").order_by("-created_at")
    serializer_class = ProductSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ["name", "description"]
    ordering_fields = ["created_at", "price", "name", "stock"]
    permission_classes = [IsOwnerOrReadOnly]
    pagination_class = StandardResultsSetPagination

    def get_serializer_class(self):
        """Разные сериализаторы для разных действий"""
        if self.action in ["create", "update", "partial_update"]:
            return ProductCreateSerializer
        return ProductSerializer

    def get_queryset(self):
        """Фильтруем товары: для неавторизованных - только в наличии"""
        queryset = super().get_queryset()
        
        # Для списка товаров (list action) - показываем только доступные
        if self.action == 'list' and not self.request.user.is_authenticated:
            queryset = queryset.filter(stock__gt=0)
        elif self.action == 'list' and self.request.user.is_authenticated:
            # Для авторизованных показываем все, но с пометкой о наличии
            pass
            
        return queryset

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
    
    def patch(self, request, product_id=None):
        """Частичное обновление товара (количество, цена, порог)"""
        try:
            product = Product.objects.get(id=product_id, owner=request.user)
        except Product.DoesNotExist:
            return Response({"error": "Товар не найден"}, status=status.HTTP_404_NOT_FOUND)

        serializer = ProductCreateSerializer(product, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        product = serializer.save()
        return Response(ProductSerializer(product).data)

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

        if not product.is_available(quantity):
            return Response(
                {"error": f"Недостаточно товара. Доступно: {product.stock} шт."},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            item, created = CartItem.objects.get_or_create(
                user=request.user, 
                product=product, 
                defaults={"quantity": quantity}
            )
            
            if not created:
                new_quantity = item.quantity + quantity
                if not product.is_available(new_quantity):
                    return Response(
                        {"error": f"Нельзя добавить. В корзине уже {item.quantity} шт., доступно {product.stock} шт."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                item.quantity = new_quantity
                item.save(update_fields=["quantity"])
                item.refresh_from_db()

        return Response(CartItemSerializer(item).data, status=status.HTTP_201_CREATED)

    def patch(self, request):
        product_id = request.data.get('product_id')
        quantity = request.data.get('quantity')
        
        if not product_id or quantity is None:
            return Response(
                {"error": "Необходимо указать product_id и quantity"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            return Response({"error": "Количество должно быть целым числом"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({"error": "Товар не найден"}, status=status.HTTP_404_NOT_FOUND)
        
        if quantity <= 0:
            # Удаляем товар из корзины
            CartItem.objects.filter(user=request.user, product=product).delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        
        if not product.is_available(quantity):
            return Response(
                {"error": f"Недостаточно товара. Доступно: {product.stock} шт."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        cart_item, created = CartItem.objects.get_or_create(
            user=request.user,
            product=product,
            defaults={'quantity': quantity}
        )
        
        if not created:
            cart_item.quantity = quantity
            cart_item.save(update_fields=['quantity'])
        
        return Response(CartItemSerializer(cart_item).data)


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

        for item in items:
            if not item.product.is_available(item.quantity):
                return Response(
                    {"error": f"Товар '{item.product.name}' недоступен в количестве {item.quantity} шт. В наличии: {item.product.stock} шт."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        total = sum(item.product.price * item.quantity for item in items)

        with transaction.atomic():
            # Создаем заказ
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
            
            # Создаем позиции заказа и уменьшаем остатки
            order_items = []
            for item in items:
                order_items.append(
                    OrderItem(
                        order=order, 
                        product=item.product, 
                        quantity=item.quantity, 
                        price=item.product.price
                    )
                )
                item.product.decrease_stock(item.quantity)
            
            OrderItem.objects.bulk_create(order_items)
            
            # Очищаем корзину
            CartItem.objects.filter(user=request.user).delete()

        return Response(
            {"message": "Заказ оформлен", "order": OrderSerializer(order).data}, 
            status=status.HTTP_201_CREATED
        )
    

class MyOrdersView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        orders = Order.objects.filter(user=request.user).prefetch_related("items", "items__product").order_by("-created_at")
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(orders, request, view=self)
        serializer = OrderSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class RepeatOrderView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, order_id):
        order = (
            Order.objects.filter(id=order_id, user=request.user)
            .prefetch_related("items", "items__product", "items__product__category", "items__product__owner")
            .first()
        )
        if not order:
            return Response({"error": "Заказ не найден"}, status=status.HTTP_404_NOT_FOUND)

        order_items = list(order.items.all())
        cart_items = {
            item.product_id: item
            for item in CartItem.objects.select_related("product").filter(user=request.user)
        }

        errors = []
        for item in order_items:
            in_cart = cart_items.get(item.product_id)
            requested_quantity = item.quantity + (in_cart.quantity if in_cart else 0)
            if item.product.stock < requested_quantity:
                errors.append(
                    {
                        "product_id": str(item.product_id),
                        "product_name": item.product.name,
                        "requested": requested_quantity,
                        "available": item.product.stock,
                    }
                )

        if errors:
            return Response(
                {"error": "Не удалось повторить заказ: недостаточно товара", "details": errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            for item in order_items:
                cart_item, created = CartItem.objects.get_or_create(
                    user=request.user,
                    product=item.product,
                    defaults={"quantity": item.quantity},
                )
                if not created:
                    cart_item.quantity = F("quantity") + item.quantity
                    cart_item.save(update_fields=["quantity"])

        items = CartItem.objects.select_related("product", "product__category", "product__owner").filter(user=request.user)
        total = sum(float(item.product.price) * item.quantity for item in items)
        return Response(
            {
                "message": "Товары из заказа добавлены в корзину",
                "items": CartItemSerializer(items, many=True).data,
                "total": total,
            }
        )


class OrderStatusUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, order_id):
        order = Order.objects.filter(id=order_id, items__product__owner=request.user).distinct().first()
        if not order:
            return Response({"error": "Заказ не найден или нет прав"}, status=status.HTTP_404_NOT_FOUND)

        old_status = order.status
        serializer = OrderStatusSerializer(order, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data.get('status')
        
        with transaction.atomic():
            serializer.save()
            
            # Если заказ отменяем - возвращаем товары
            if old_status != Order.STATUS_CANCELED and new_status == Order.STATUS_CANCELED:
                order_items = OrderItem.objects.filter(order=order)
                for item in order_items:
                    item.product.increase_stock(item.quantity)
            
            # Если заказ был отменен, а теперь меняем статус - не делаем ничего особенного
        
        return Response(OrderSerializer(order).data)
