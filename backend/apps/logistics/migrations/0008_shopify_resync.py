from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("logistics", "0007_alter_batchjob_job_type_sync_customers"),
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
                    ("SHOPIFY_RESYNC", "Resync Shopify"),
                    ("SYNC_CUSTOMERS", "Sincronizar clientes Alegra"),
                ],
                max_length=32,
            ),
        ),
    ]
