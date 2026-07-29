# Generated for ShopifySale index name alignment

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0004_shopify_channel"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="shopifysale",
            new_name="sales_shopi_status_f66918_idx",
            old_name="sales_shopi_status_idx",
        ),
    ]
