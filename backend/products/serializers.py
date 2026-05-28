from rest_framework import serializers

from .models import CartItem, Category, Order, OrderItem, Product


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"


class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), source="category", write_only=True)
    owner_username = serializers.CharField(source="owner.username", read_only=True)

    stock_status = serializers.SerializerMethodField()
    is_in_stock = serializers.SerializerMethodField()
    in_stock_display = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "description",
            "price",
            "category",
            "category_id",
            "image",
            "specs",
            "owner",
            "owner_username",
            "created_at",
            "stock",                    
            "low_stock_threshold",      
            "stock_status",           
            "is_in_stock",       
            "in_stock_display", 
        ]
        read_only_fields = ["id", "created_at", "category", "owner", "owner_username", "stock_status", "is_in_stock", "in_stock_display"]

    def get_stock_status(self, obj):
        """Возвращает текстовый статус наличия"""
        if obj.stock <= 0:
            return "out_of_stock"
        elif obj.stock <= obj.low_stock_threshold:
            return "low_stock"
        return "in_stock"
    
    def get_is_in_stock(self, obj):
        """Булево значение: есть ли товар в наличии"""
        return obj.stock > 0
    
    def get_in_stock_display(self, obj):
        """Текст для отображения пользователю"""
        if obj.stock <= 0:
            return "Нет в наличии"
        elif obj.stock <= obj.low_stock_threshold:
            return f"Осталось всего {obj.stock} шт."
        else:
            return f"В наличии ({obj.stock} шт.)"

class ProductCreateSerializer(serializers.ModelSerializer):
    """Специальный сериализатор для создания/обновления товаров"""
    
    class Meta:
        model = Product
        fields = [
            "name", "description", "price", "category", 
            "image", "specs", "stock", "low_stock_threshold"
        ]
    
    def validate_stock(self, value):
        if value < 0:
            raise serializers.ValidationError("Количество товара не может быть отрицательным")
        return value
    
    def validate_low_stock_threshold(self, value):
        if value < 0:
            raise serializers.ValidationError("Порог низкого остатка не может быть отрицательным")
        return value
    
    def create(self, validated_data):
        validated_data['owner'] = self.context['request'].user
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        # Для обновления можно менять количество
        return super().update(instance, validated_data)


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all(), source="product", write_only=True)
    
    def validate(self, data):
        if 'product' in data:
            product = data['product']
            quantity = data.get('quantity', 1)
            if not product.is_available(quantity):
                raise serializers.ValidationError(
                    f"Товар '{product.name}' недоступен в количестве {quantity}. В наличии: {product.stock} шт."
                )
        return data

    class Meta:
        model = CartItem
        fields = ["id", "product", "product_id", "quantity", "created_at"]
        read_only_fields = ["id", "created_at", "product"]


class CheckoutSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=255)
    phone = serializers.RegexField(regex=r"^[0-9+()\-\s]{7,20}$")
    city = serializers.CharField(max_length=120)
    address = serializers.CharField(max_length=255, min_length=10)
    comment = serializers.CharField(required=False, allow_blank=True)


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = OrderItem
        fields = ["id", "product", "product_name", "quantity", "price"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "full_name",
            "phone",
            "city",
            "address",
            "comment",
            "status",
            "total",
            "created_at",
            "items",
        ]


class OrderStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ["status"]
