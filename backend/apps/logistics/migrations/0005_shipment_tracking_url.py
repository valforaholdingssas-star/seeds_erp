from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("logistics", "0004_alter_shipment_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="shipment",
            name="tracking_url",
            field=models.URLField(blank=True, max_length=512),
        ),
    ]
