from django.urls import path

from .views import (
    CartItemDeleteView,
    CartView,
    CheckoutView,
    MyOrdersView,
    MyProductsView,
    OrderStatusUpdateView,
)

urlpatterns = [
    path("my-products/", MyProductsView.as_view(), name="my-products"),
    path("my-orders/", MyOrdersView.as_view(), name="my-orders"),
    path("orders/<int:order_id>/status/", OrderStatusUpdateView.as_view(), name="order-status-update"),
    path("cart/", CartView.as_view(), name="cart"),
    path("cart/checkout/", CheckoutView.as_view(), name="cart-checkout"),
    path("cart/<int:item_id>/", CartItemDeleteView.as_view(), name="cart-item-delete"),
]
