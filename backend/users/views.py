from django.contrib.auth import authenticate
from django.db.models import F
from drf_spectacular.utils import OpenApiExample, extend_schema
from django.contrib.auth.models import User
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .email_service import send_verification_email
from .models import EmailVerificationToken, UserProfile
from .permissions import IsAdminUser
from .serializers import LoginSerializer, RegisterSerializer, UserSerializer


def tokens_for_user(user: User):
    refresh = RefreshToken.for_user(user)
    return {"refresh": str(refresh), "access": str(refresh.access_token)}


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        examples=[
            OpenApiExample(
                "Register buyer",
                value={"username": "buyer1", "email": "buyer@example.com", "password": "password123", "role": "buyer"},
                request_only=True,
            ),
            OpenApiExample(
                "Register seller",
                value={
                    "username": "seller1",
                    "email": "seller@example.com",
                    "password": "password123",
                    "role": "seller",
                    "store_name": "Мой магазин",
                },
                request_only=True,
            ),
        ]
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token = EmailVerificationToken.objects.create(user=user)
        email_sent = send_verification_email(user, token)
        return Response(
            {
                "tokens": tokens_for_user(user),
                "user": UserSerializer(user).data,
                "email_sent": email_sent,
                "message": "Аккаунт создан. Проверьте почту для подтверждения email.",
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        examples=[
            OpenApiExample(
                "Login payload",
                value={"username": "seller1", "password": "password123"},
                request_only=True,
            )
        ]
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )
        if not user:
            return Response({"error": "Неверный логин или пароль"}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"tokens": tokens_for_user(user), "user": UserSerializer(user).data})


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh = request.data.get("refresh")
        if not refresh:
            return Response({"error": "refresh is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            token = RefreshToken(refresh)
            token.blacklist()
        except Exception:
            return Response({"error": "invalid refresh token"}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")
        if not old_password or not new_password:
            return Response({"error": "old_password and new_password are required"}, status=status.HTTP_400_BAD_REQUEST)
        if len(new_password) < 8:
            return Response({"error": "new_password must be at least 8 characters"}, status=status.HTTP_400_BAD_REQUEST)
        if not request.user.check_password(old_password):
            return Response({"error": "old_password is incorrect"}, status=status.HTTP_400_BAD_REQUEST)

        request.user.set_password(new_password)
        request.user.save(update_fields=["password"])
        return Response({"message": "password changed"})


class ProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class VerifyEmailView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        token_value = request.data.get("token", "").strip()
        if not token_value:
            return Response({"error": "token is required"}, status=status.HTTP_400_BAD_REQUEST)

        token = EmailVerificationToken.objects.filter(token=token_value, used=False).select_related("user").first()
        if not token:
            return Response({"error": "Недействительная или уже использованная ссылка"}, status=status.HTTP_400_BAD_REQUEST)

        profile = token.user.profile
        profile.email_verified = True
        profile.save(update_fields=["email_verified"])
        token.used = True
        token.save(update_fields=["used"])

        return Response({"message": "Email успешно подтверждён", "user": UserSerializer(token.user).data})


class ResendVerificationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        profile = getattr(request.user, "profile", None)
        if not profile:
            return Response({"error": "Профиль не найден"}, status=status.HTTP_400_BAD_REQUEST)
        if profile.email_verified:
            return Response({"message": "Email уже подтверждён"})
        if not request.user.email:
            return Response({"error": "Email не указан в профиле"}, status=status.HTTP_400_BAD_REQUEST)

        token = EmailVerificationToken.objects.create(user=request.user)
        email_sent = send_verification_email(request.user, token)
        if not email_sent:
            return Response({"error": "Не удалось отправить письмо"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"message": "Письмо с подтверждением отправлено повторно"})


class AdminStatsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]

    def get(self, request):
        from django.db.models import Sum
        from products.models import Order, Product
        from ai.models import AIInteraction

        paid_revenue = Order.objects.filter(status__in=[Order.STATUS_PAID, Order.STATUS_SHIPPED, Order.STATUS_DONE]).aggregate(
            total=Sum("total")
        )["total"] or 0
        orders_by_status = {
            status_key: Order.objects.filter(status=status_key).count()
            for status_key, _ in Order.STATUS_CHOICES
        }
        recent_ai = AIInteraction.objects.order_by("-created_at").values("id", "kind", "query", "created_at")[:5]

        return Response(
            {
                "users_count": User.objects.count(),
                "sellers_count": UserProfile.objects.filter(role=UserProfile.ROLE_SELLER).count(),
                "buyers_count": UserProfile.objects.filter(role=UserProfile.ROLE_BUYER).count(),
                "unverified_users_count": UserProfile.objects.filter(email_verified=False).count(),
                "products_count": Product.objects.count(),
                "low_stock_products": Product.objects.filter(stock__gt=0, stock__lte=F("low_stock_threshold")).count(),
                "out_of_stock_products": Product.objects.filter(stock=0).count(),
                "orders_count": Order.objects.count(),
                "orders_paid": Order.objects.filter(status=Order.STATUS_PAID).count(),
                "orders_new": Order.objects.filter(status=Order.STATUS_NEW).count(),
                "paid_revenue": paid_revenue,
                "orders_by_status": orders_by_status,
                "ai_interactions": AIInteraction.objects.count(),
                "recent_ai": list(recent_ai),
            }
        )


class AdminUsersView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]

    def get(self, request):
        users = User.objects.select_related("profile").order_by("-date_joined")[:100]
        data = []
        for user in users:
            profile = getattr(user, "profile", None)
            data.append(
                {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": profile.role if profile else "buyer",
                    "store_name": profile.store_name if profile else "",
                    "email_verified": profile.email_verified if profile else False,
                    "is_staff": user.is_staff,
                    "date_joined": user.date_joined,
                }
            )
        return Response(data)


class AdminOrdersView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]

    def get(self, request):
        from products.serializers import OrderSerializer
        from products.models import Order

        orders = Order.objects.prefetch_related("items", "items__product").order_by("-created_at")[:100]
        return Response(OrderSerializer(orders, many=True).data)

    def patch(self, request, order_id):
        from products.models import Order
        from products.serializers import OrderStatusSerializer, OrderSerializer

        order = Order.objects.filter(id=order_id).first()
        if not order:
            return Response({"error": "Заказ не найден"}, status=status.HTTP_404_NOT_FOUND)

        serializer = OrderStatusSerializer(order, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(OrderSerializer(order).data)
