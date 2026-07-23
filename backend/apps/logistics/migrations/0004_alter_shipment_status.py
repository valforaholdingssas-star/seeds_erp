from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("logistics", "0003_alter_batchjob_job_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="shipment",
            name="status",
            field=models.CharField(
                choices=[
                    ("POR_GENERAR", "Por generar guía"),
                    ("GUIA_FALLIDA", "Guía fallida"),
                    ("LISTO_PARA_ENVIAR", "Listo para enviar"),
                    ("ENVIADO", "Enviado"),
                    ("REVISAR", "Revisar / no enviar"),
                    ("CANCELADA", "Cancelada"),
                ],
                db_index=True,
                default="POR_GENERAR",
                max_length=24,
            ),
        ),
    ]
