from django.urls import path

from .views import (
    CartItemDeleteView,
    CartView,
    CheckoutView,
    MyOrdersView,
    MyProductsView,
    OrderStatusUpdateView,
    RepeatOrderView,
)

urlpatterns = [
    path("my-products/", MyProductsView.as_view(), name="my-products"),
    path("my-products/<uuid:product_id>/", MyProductsView.as_view(), name="my-product-update"),
    path("my-orders/", MyOrdersView.as_view(), name="my-orders"),
    path("orders/<int:order_id>/status/", OrderStatusUpdateView.as_view(), name="order-status-update"),
    path("orders/<int:order_id>/repeat/", RepeatOrderView.as_view(), name="order-repeat"),
    path("cart/", CartView.as_view(), name="cart"),
    path("cart/update/", CartView.as_view(), name="cart-update"),
    path("cart/checkout/", CheckoutView.as_view(), name="cart-checkout"),
    path("cart/<int:item_id>/", CartItemDeleteView.as_view(), name="cart-item-delete"),
]
