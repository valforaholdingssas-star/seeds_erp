from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("logistics", "0006_shipment_url_defaults"),
    ]

    operations = [
        migrations.AlterField(
            model_name="batchjob",
            name="job_type",
            field=models.CharField(
                choices=[
                    ("GENERATE_SHIPMENTS", "Generar guías"),
                    ("FORMAT_ADDRESSES", "Formatear direcciones"),
                    ("MARK_SENT", "Marcar enviados"),
                    ("ISSUE_INVOICES", "Emitir facturas"),
                    ("WOO_RESYNC", "Resync WooCommerce"),
                    ("SYNC_CUSTOMERS", "Sincronizar clientes Alegra"),
                ],
                max_length=32,
            ),
        ),
    ]
