# Generated manually for Shopify parallel channel

import django.db.models.deletion
import uuid
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0001_initial"),
        ("sales", "0003_fulfillment_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="consolidatedsale",
            name="source",
            field=models.CharField(
                choices=[
                    ("ECOMMERCE", "Ecommerce"),
                    ("SHOPIFY", "Shopify"),
                    ("KOMMO", "Kommo"),
                    ("FERIAS", "Ferias"),
                    ("MANUAL", "Manual"),
                ],
                db_index=True,
                max_length=16,
            ),
        ),
        migrations.CreateModel(
            name="ShopifySale",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("external_id", models.CharField(db_index=True, max_length=64)),
                ("deal_name", models.CharField(blank=True, max_length=255)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "total_value",
                    models.DecimalField(
                        decimal_places=2, default=Decimal("0"), max_digits=14
                    ),
                ),
                (
                    "amount_shipping",
                    models.DecimalField(
                        decimal_places=2, default=Decimal("0"), max_digits=14
                    ),
                ),
                ("payment_account", models.CharField(blank=True, max_length=128)),
                ("income_source", models.CharField(blank=True, max_length=32)),
                (
                    "status",
                    models.CharField(db_index=True, default="processing", max_length=64),
                ),
                ("stage", models.CharField(blank=True, max_length=128)),
                ("commercial_raw", models.CharField(blank=True, max_length=128)),
                ("customer_name", models.CharField(blank=True, max_length=255)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("phone", models.CharField(blank=True, max_length=64)),
                ("id_number", models.CharField(blank=True, max_length=64)),
                ("address_raw", models.CharField(blank=True, max_length=512)),
                ("city_raw", models.CharField(blank=True, max_length=128)),
                ("state_raw", models.CharField(blank=True, max_length=128)),
                ("qty_dorados", models.PositiveIntegerField(default=0)),
                ("qty_plateados", models.PositiveIntegerField(default=0)),
                ("tipo_dorados", models.CharField(blank=True, max_length=128)),
                ("tipo_plateados", models.CharField(blank=True, max_length=128)),
                ("symptoms", models.CharField(blank=True, max_length=255)),
                ("order_notes", models.TextField(blank=True)),
                ("age", models.CharField(blank=True, max_length=32)),
                ("extra", models.JSONField(blank=True, default=dict)),
                (
                    "requires_shipping",
                    models.BooleanField(
                        default=True,
                        help_text="Derivado de fulfillment_type: True solo si ENVIA.",
                    ),
                ),
                (
                    "fulfillment_type",
                    models.CharField(
                        choices=[
                            ("ENVIA", "Envia (guía)"),
                            ("DOMICILIO", "Domicilio fuera de Envia"),
                            ("OFICINA", "Visita / recoger en oficina"),
                        ],
                        db_index=True,
                        default="ENVIA",
                        help_text="ENVIA → guías Envia. DOMICILIO/OFICINA → no generan guía.",
                        max_length=16,
                    ),
                ),
                (
                    "consolidated_sale",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_sources",
                        to="sales.consolidatedsale",
                    ),
                ),
                (
                    "payment_method",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_sales",
                        to="sales.paymentmethod",
                    ),
                ),
                (
                    "raw_event",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_sales",
                        to="integrations.rawwebhookevent",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["status", "closed_at"],
                        name="sales_shopi_status_idx",
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("external_id",), name="uq_shopify_external_id"
                    )
                ],
            },
        ),
    ]
