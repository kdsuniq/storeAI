from django.urls import path
from .views import (
    AIChatView, 
    AIDescriptionView, 
    MarketInsightsView,
    AIRecommendationsView,  # Исправлено: правильное имя
)

urlpatterns = [
    path("chat/", AIChatView.as_view(), name="ai-chat"),
    path("generate-description/", AIDescriptionView.as_view(), name="ai-generate-description"),
    path("market-insights/", MarketInsightsView.as_view(), name="ai-market-insights"),
    path("recommend/", AIRecommendationsView.as_view(), name="ai-recommend"),  # Исправлено
]