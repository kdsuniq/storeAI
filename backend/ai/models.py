from django.conf import settings
from django.db import models

from products.models import Product


class ProductViewEvent(models.Model):
    SOURCE_CATALOG = "catalog"
    SOURCE_AI = "ai"
    SOURCE_CHOICES = [
        (SOURCE_CATALOG, "Catalog"),
        (SOURCE_AI, "AI"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="product_view_events",
        null=True,
        blank=True,
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="view_events")
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_CATALOG)
    query = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        username = self.user.username if self.user else "anonymous"
        return f"{username} viewed {self.product.name}"


class AIInteraction(models.Model):
    KIND_CHAT = "chat"
    KIND_SEARCH = "search"
    KIND_PERSONAL = "personal"
    KIND_BUNDLE = "bundle"
    KIND_CHOICES = [
        (KIND_CHAT, "Chat"),
        (KIND_SEARCH, "Search"),
        (KIND_PERSONAL, "Personal recommendations"),
        (KIND_BUNDLE, "Bundle"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="ai_interactions",
        null=True,
        blank=True,
    )
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    query = models.TextField()
    response = models.JSONField(default=dict, blank=True)
    context = models.JSONField(default=dict, blank=True)
    helpful = models.BooleanField(null=True, blank=True)
    feedback_text = models.TextField(blank=True)
    needs_prompt_review = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.kind}: {self.query[:60]}"
