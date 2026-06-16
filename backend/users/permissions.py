from rest_framework.permissions import BasePermission


class IsSeller(BasePermission):
    message = "Доступ только для продавцов"

    def has_permission(self, request, view):
        profile = getattr(request.user, "profile", None)
        return bool(request.user and request.user.is_authenticated and profile and profile.role == "seller")


class IsEmailVerified(BasePermission):
    message = "Подтвердите email, чтобы продолжить"

    def has_permission(self, request, view):
        if request.user.is_staff:
            return True
        profile = getattr(request.user, "profile", None)
        return bool(profile and profile.email_verified)


class IsAdminUser(BasePermission):
    message = "Доступ только для администраторов"

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)
