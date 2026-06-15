from django.urls import path
from .views import (
    AIBundleView,
    AIChatView, 
    AIDescriptionView, 
    AIInteractionFeedbackView,
    AIPersonalRecommendationsView,
    MarketInsightsView,
    AIRecommendationsView,
    AIPriceAnalysisView,
    AISemanticSearchView,
    ProductViewTrackView,
)

urlpatterns = [
    path("chat/", AIChatView.as_view(), name="ai-chat"),
    path("generate-description/", AIDescriptionView.as_view(), name="ai-generate-description"),
    path("market-insights/", MarketInsightsView.as_view(), name="ai-market-insights"),
    path("recommend/", AIRecommendationsView.as_view(), name="ai-recommend"),
    path("semantic-search/", AISemanticSearchView.as_view(), name="ai-semantic-search"),
    path("personal-recommendations/", AIPersonalRecommendationsView.as_view(), name="ai-personal-recommendations"),
    path("bundle/", AIBundleView.as_view(), name="ai-bundle"),
    path("feedback/", AIInteractionFeedbackView.as_view(), name="ai-feedback"),
    path("track-view/", ProductViewTrackView.as_view(), name="ai-track-view"),
    path("price-analysis/", AIPriceAnalysisView.as_view(), name="ai-price-analysis"),
]
