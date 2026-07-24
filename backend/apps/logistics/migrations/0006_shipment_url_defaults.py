from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("logistics", "0005_shipment_tracking_url"),
    ]

    operations = [
        migrations.AlterField(
            model_name="shipment",
            name="tracking_url",
            field=models.URLField(blank=True, default="", max_length=512),
        ),
        migrations.AlterField(
            model_name="shipment",
            name="label_url",
            field=models.URLField(blank=True, default=""),
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE logistics_shipment "
                "ALTER COLUMN tracking_url SET DEFAULT ''; "
                "UPDATE logistics_shipment SET tracking_url = '' "
                "WHERE tracking_url IS NULL; "
                "ALTER TABLE logistics_shipment "
                "ALTER COLUMN label_url SET DEFAULT ''; "
                "UPDATE logistics_shipment SET label_url = '' "
                "WHERE label_url IS NULL;"
            ),
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
