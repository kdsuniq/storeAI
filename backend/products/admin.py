from django.contrib import admin

from .models import CartItem, Category, Order, OrderItem, Payment, Product

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'price', 'stock', 'low_stock_threshold', 'is_available_display', 'owner', 'created_at']
    list_filter = ['category', 'stock', 'created_at']
    search_fields = ['name', 'description']
    list_editable = ['stock', 'price']
    readonly_fields = ['id', 'created_at']
    
    def is_available_display(self, obj):
        return "✓" if obj.stock > 0 else "✗"
    is_available_display.short_description = "В наличии"
    is_available_display.boolean = True

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']
    search_fields = ['name']


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['product', 'quantity', 'price']
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'full_name', 'phone', 'city', 'status', 'total', 'created_at']
    list_filter = ['status', 'city', 'created_at']
    search_fields = ['id', 'user__username', 'full_name', 'phone', 'city', 'address']
    list_editable = ['status']
    readonly_fields = ['user', 'full_name', 'phone', 'city', 'address', 'comment', 'total', 'created_at']
    inlines = [OrderItemInline]
    date_hierarchy = 'created_at'


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'quantity', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'product__name']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['order', 'external_id', 'status', 'amount', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['external_id', 'order__id']
    readonly_fields = ['order', 'external_id', 'amount', 'confirmation_url', 'created_at', 'updated_at']
