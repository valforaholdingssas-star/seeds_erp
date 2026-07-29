import uuid
from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sellers", "0002_password_reset_and_monthly_goal"),
    ]

    operations = [
        migrations.CreateModel(
            name="SellerMonthlyGoal",
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
                ("year", models.PositiveIntegerField(db_index=True)),
                ("month", models.PositiveSmallIntegerField(db_index=True)),
                (
                    "amount",
                    models.DecimalField(
                        decimal_places=2, default=Decimal("0"), max_digits=14
                    ),
                ),
                (
                    "seller",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="monthly_goals",
                        to="sellers.vendedor",
                    ),
                ),
            ],
            options={
                "verbose_name": "Meta mensual comercial",
                "verbose_name_plural": "Metas mensuales comerciales",
                "ordering": ["seller__name", "year", "month"],
            },
        ),
        migrations.AddIndex(
            model_name="sellermonthlygoal",
            index=models.Index(fields=["year", "month"], name="sellers_sel_year_mo_idx"),
        ),
        migrations.AddConstraint(
            model_name="sellermonthlygoal",
            constraint=models.UniqueConstraint(
                fields=("seller", "year", "month"), name="uq_seller_monthly_goal"
            ),
        ),
    ]
