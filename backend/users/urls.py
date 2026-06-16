from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    AdminOrdersView,
    AdminStatsView,
    AdminUsersView,
    ChangePasswordView,
    LoginView,
    LogoutView,
    ProfileView,
    RegisterView,
    ResendVerificationView,
    VerifyEmailView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("me/", ProfileView.as_view(), name="profile"),
    path("verify-email/", VerifyEmailView.as_view(), name="verify-email"),
    path("resend-verification/", ResendVerificationView.as_view(), name="resend-verification"),
    path("admin/stats/", AdminStatsView.as_view(), name="admin-stats"),
    path("admin/users/", AdminUsersView.as_view(), name="admin-users"),
    path("admin/orders/", AdminOrdersView.as_view(), name="admin-orders"),
    path("admin/orders/<int:order_id>/", AdminOrdersView.as_view(), name="admin-order-update"),
]
