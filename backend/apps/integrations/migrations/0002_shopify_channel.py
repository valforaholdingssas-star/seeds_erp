from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="integrationlog",
            name="provider",
            field=models.CharField(
                choices=[
                    ("WOOCOMMERCE", "WooCommerce"),
                    ("SHOPIFY", "Shopify"),
                    ("KOMMO", "Kommo"),
                    ("ENVIA", "Envia"),
                    ("ALEGRA", "Alegra"),
                    ("AI", "IA"),
                    ("INTERNAL", "Interno"),
                ],
                db_index=True,
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="rawwebhookevent",
            name="source",
            field=models.CharField(
                choices=[
                    ("WOOCOMMERCE", "WooCommerce"),
                    ("SHOPIFY", "Shopify"),
                    ("KOMMO", "Kommo"),
                    ("ENVIA", "Envia"),
                    ("ALEGRA", "Alegra"),
                    ("AI", "IA"),
                    ("INTERNAL", "Interno"),
                ],
                db_index=True,
                max_length=32,
            ),
        ),
    ]
