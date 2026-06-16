import uuid

from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.db import models


class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="products", null=True, blank=True)
    name = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="products")
    image = models.CharField(max_length=500, blank=True, null=True)
    specs = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    stock = models.PositiveIntegerField(default=0, help_text="Количество товара в наличии")
    low_stock_threshold = models.PositiveIntegerField(default=5, help_text="При каком остатке считать товар 'почти распродан'")

    def __str__(self):
        return self.name
    
    def is_available(self, quantity=1):
        """Проверка доступности товара"""
        return self.stock >= quantity
    
    def decrease_stock(self, quantity):
        """Уменьшить остаток (при продаже)"""
        if self.stock >= quantity:
            self.stock -= quantity
            self.save(update_fields=['stock'])
            return True
        return False
    
    def increase_stock(self, quantity):
        """Увеличить остаток (при возврате/пополнении)"""
        self.stock += quantity
        self.save(update_fields=['stock'])


class CartItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="cart_items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="in_carts")
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "product")

    def __str__(self):
        return f"{self.user.username} -> {self.product.name} ({self.quantity})"


class Order(models.Model):
    STATUS_NEW = "new"
    STATUS_PAID = "paid"
    STATUS_SHIPPED = "shipped"
    STATUS_DONE = "done"
    STATUS_CANCELED = "canceled"
    STATUS_CHOICES = [
        (STATUS_NEW, "New"),
        (STATUS_PAID, "Paid"),
        (STATUS_SHIPPED, "Shipped"),
        (STATUS_DONE, "Done"),
        (STATUS_CANCELED, "Canceled"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    full_name = models.CharField(max_length=255)
    phone = models.CharField(
        max_length=50,
        validators=[RegexValidator(regex=r"^[0-9+()\-\s]{7,20}$", message="Неверный формат телефона")],
    )
    city = models.CharField(max_length=120)
    address = models.CharField(max_length=255)
    comment = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.id} by {self.user.username}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.order_id} -> {self.product.name} ({self.quantity})"


class Payment(models.Model):
    STATUS_PENDING = "pending"
    STATUS_SUCCEEDED = "succeeded"
    STATUS_CANCELED = "canceled"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SUCCEEDED, "Succeeded"),
        (STATUS_CANCELED, "Canceled"),
    ]

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="payment")
    external_id = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    confirmation_url = models.URLField(blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment for order #{self.order_id} ({self.status})"
