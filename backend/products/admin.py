from django.contrib import admin
from .models import Product, Category

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'price', 'stock', 'low_stock_threshold', 'is_available_display', 'owner', 'created_at']
    list_filter = ['category', 'stock', 'created_at']
    search_fields = ['name', 'description']
    list_editable = ['stock', 'price']  # ⭐ Можно быстро редактировать остаток
    readonly_fields = ['id', 'created_at']
    
    def is_available_display(self, obj):
        return "✓" if obj.stock > 0 else "✗"
    is_available_display.short_description = "В наличии"
    is_available_display.boolean = True

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']
    search_fields = ['name']