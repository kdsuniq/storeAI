from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import UserProfile


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    role = serializers.ChoiceField(choices=UserProfile.ROLE_CHOICES, default=UserProfile.ROLE_BUYER)
    store_name = serializers.CharField(required=False, allow_blank=True, max_length=255)

    class Meta:
        model = User
        fields = ["id", "username", "email", "password", "role", "store_name"]

    def validate_username(self, value):
        value = value.strip()
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Пользователь с таким логином уже существует")
        return value

    def validate_email(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Email обязателен для регистрации")
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Пользователь с таким email уже существует")
        return value

    def validate(self, attrs):
        if attrs.get("role") == UserProfile.ROLE_SELLER and not attrs.get("store_name", "").strip():
            raise serializers.ValidationError({"store_name": "Укажите название магазина"})
        return attrs

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def create(self, validated_data):
        role = validated_data.pop("role", UserProfile.ROLE_BUYER)
        store_name = validated_data.pop("store_name", "")
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
        )
        UserProfile.objects.create(
            user=user,
            role=role,
            store_name=store_name.strip(),
            email_verified=False,
        )
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class UserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    store_name = serializers.SerializerMethodField()
    email_verified = serializers.SerializerMethodField()
    is_staff = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "role", "store_name", "email_verified", "is_staff"]

    def _get_profile(self, obj):
        profile = getattr(obj, "profile", None)
        if profile:
            return profile
        profile, _ = UserProfile.objects.get_or_create(user=obj, defaults={"role": UserProfile.ROLE_BUYER})
        return profile

    def get_role(self, obj):
        return self._get_profile(obj).role

    def get_store_name(self, obj):
        return self._get_profile(obj).store_name

    def get_email_verified(self, obj):
        return self._get_profile(obj).email_verified
