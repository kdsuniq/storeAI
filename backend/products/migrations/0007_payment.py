import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0006_product_low_stock_threshold_product_stock"),
    ]

    operations = [
        migrations.CreateModel(
            name="Payment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("external_id", models.CharField(blank=True, max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Pending"), ("succeeded", "Succeeded"), ("canceled", "Canceled")],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("confirmation_url", models.URLField(blank=True)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "order",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payment",
                        to="products.order",
                    ),
                ),
            ],
        ),
    ]
