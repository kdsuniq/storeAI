from django.contrib import admin

from .models import AIInteraction, ProductViewEvent


@admin.register(ProductViewEvent)
class ProductViewEventAdmin(admin.ModelAdmin):
    list_display = ["user", "product", "source", "query", "created_at"]
    list_filter = ["source", "created_at"]
    search_fields = ["user__username", "product__name", "query"]
    readonly_fields = ["user", "product", "source", "query", "created_at"]


@admin.register(AIInteraction)
class AIInteractionAdmin(admin.ModelAdmin):
    list_display = ["id", "kind", "user", "helpful", "needs_prompt_review", "created_at"]
    list_filter = ["kind", "helpful", "needs_prompt_review", "created_at"]
    search_fields = ["query", "feedback_text", "user__username"]
    readonly_fields = ["user", "kind", "query", "response", "context", "created_at", "updated_at"]
