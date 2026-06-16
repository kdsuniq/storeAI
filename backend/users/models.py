import uuid

from django.contrib.auth.models import User
from django.db import models


class UserProfile(models.Model):
    ROLE_BUYER = "buyer"
    ROLE_SELLER = "seller"
    ROLE_CHOICES = [
        (ROLE_BUYER, "Покупатель"),
        (ROLE_SELLER, "Продавец"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_BUYER)
    store_name = models.CharField(max_length=255, blank=True)
    email_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"


class EmailVerificationToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="verification_tokens")
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    used = models.BooleanField(default=False)

    def __str__(self):
        return f"Token for {self.user.username}"
