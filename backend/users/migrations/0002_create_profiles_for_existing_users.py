from django.db import migrations


def create_profiles_for_existing_users(apps, schema_editor):
    User = apps.get_model("auth", "User")
    UserProfile = apps.get_model("users", "UserProfile")
    for user in User.objects.all():
        UserProfile.objects.get_or_create(
            user=user,
            defaults={
                "role": "seller" if user.products.exists() else "buyer",
                "email_verified": bool(user.email),
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0001_initial"),
        ("products", "0002_product_owner_cartitem"),
    ]

    operations = [
        migrations.RunPython(create_profiles_for_existing_users, migrations.RunPython.noop),
    ]
