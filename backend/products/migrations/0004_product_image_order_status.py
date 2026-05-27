from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0003_order_orderitem"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="image",
            field=models.ImageField(blank=True, null=True, upload_to="products/"),
        ),
        migrations.AddField(
            model_name="order",
            name="status",
            field=models.CharField(
                choices=[
                    ("new", "New"),
                    ("paid", "Paid"),
                    ("shipped", "Shipped"),
                    ("done", "Done"),
                    ("canceled", "Canceled"),
                ],
                default="new",
                max_length=20,
            ),
        ),
    ]
