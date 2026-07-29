# Follow-up fields on ecommerce source sales (Woo + Shopify + others)

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def _add_follow_up(model_name: str) -> list:
    return [
        migrations.AddField(
            model_name=model_name,
            name="follow_up_status",
            field=models.CharField(
                choices=[
                    ("POR_CONTACTAR", "Por contactar"),
                    ("CONTACTADO", "Contactado"),
                    ("EN_SEGUIMIENTO", "En seguimiento"),
                    ("CERRADO", "Cerrado"),
                ],
                db_index=True,
                default="POR_CONTACTAR",
                help_text="Seguimiento comercial de pedidos no consolidados (fallidos/pendientes).",
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name=model_name,
            name="contacted_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name=model_name,
            name="contacted_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name=f"{model_name}_contacts",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name=model_name,
            name="follow_up_notes",
            field=models.TextField(blank=True),
        ),
    ]


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("sales", "0005_rename_shopify_status_idx"),
    ]

    operations = (
        _add_follow_up("ecommercesale")
        + _add_follow_up("shopifysale")
        + _add_follow_up("kommosale")
        + _add_follow_up("feriasale")
        + _add_follow_up("manualsale")
    )
