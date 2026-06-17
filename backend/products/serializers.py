from rest_framework import serializers

from .models import CartItem, Category, Order, OrderItem, Product


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"

    def validate_name(self, value):
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError("Название категории должно быть не короче 2 символов")
        return value


class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), source="category", write_only=True)
    image = serializers.SerializerMethodField()
    owner_username = serializers.CharField(source="owner.username", read_only=True)
    store_name = serializers.SerializerMethodField()

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
            "store_name",
            "created_at",
            "stock",                    
            "low_stock_threshold",      
            "stock_status",           
            "is_in_stock",       
            "in_stock_display", 
        ]
        read_only_fields = ["id", "created_at", "category", "owner", "owner_username", "store_name", "stock_status", "is_in_stock", "in_stock_display"]

    def get_image(self, obj):
        if not obj.image:
            return ""
        image_name = str(obj.image)
        if image_name.startswith(("http://", "https://", "/")):
            return image_name
        try:
            url = obj.image.url
        except ValueError:
            return image_name
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request else url

    def get_store_name(self, obj):
        profile = getattr(obj.owner, "profile", None) if obj.owner else None
        if profile and profile.store_name:
            return profile.store_name
        return obj.owner.username if obj.owner else "магазин"

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
    image = serializers.FileField(required=False, allow_null=True)
    
    class Meta:
        model = Product
        fields = [
            "name", "description", "price", "category", 
            "image", "specs", "stock", "low_stock_threshold"
        ]

    def validate_name(self, value):
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError("Название товара должно быть не короче 2 символов")
        return value

    def validate_description(self, value):
        value = value.strip()
        if len(value) < 10:
            raise serializers.ValidationError("Описание должно быть не короче 10 символов")
        return value

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Цена должна быть больше нуля")
        return value
    
    def validate_stock(self, value):
        if value < 0:
            raise serializers.ValidationError("Количество товара не может быть отрицательным")
        return value
    
    def validate_low_stock_threshold(self, value):
        if value < 0:
            raise serializers.ValidationError("Порог низкого остатка не может быть отрицательным")
        return value

    def validate_specs(self, value):
        if isinstance(value, str):
            import json
            try:
                return json.loads(value) if value.strip() else {}
            except json.JSONDecodeError:
                raise serializers.ValidationError("Характеристики должны быть корректным JSON")
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
        quantity = data.get('quantity', 1)
        if quantity <= 0:
            raise serializers.ValidationError("Количество должно быть больше нуля")
        if 'product' in data:
            product = data['product']
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
    full_name = serializers.CharField(max_length=255, min_length=3)
    phone = serializers.RegexField(regex=r"^[0-9+()\-\s]{7,20}$")
    city = serializers.CharField(max_length=120, min_length=2)
    address = serializers.CharField(max_length=255, min_length=10)
    comment = serializers.CharField(required=False, allow_blank=True, max_length=1000)

    def validate_full_name(self, value):
        value = value.strip()
        if len(value.split()) < 2:
            raise serializers.ValidationError("Укажите имя и фамилию")
        return value

    def validate_city(self, value):
        return value.strip()

    def validate_address(self, value):
        return value.strip()


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
